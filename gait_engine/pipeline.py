"""End-to-end clip analysis.

    video -> frames -> (pose landmarks | picture motion) -> measurements
          -> factor scores -> overall indicator -> plain-language observation

The motion and detection path is the default. Experimental COCO-17 output is
available only after an explicit environment-variable opt-in:

* ``opencv-motion`` frame-to-frame picture change; dog detection metadata is
                    retained when detector dependencies and weights are available.
* ``coco-pose``     Opt-in RT-DETR dog boxes and ViTPose++ COCO-17 output. The
                    checkpoint has no AP-10K canine keypoint head, so gait metrics
                    that require that schema remain unavailable.

The returned dictionary matches the ``AnalyzeResult`` schema in
`lib/api-spec/openapi.yaml`, so the API server can validate it before replying.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .clip_quality import quality_notes
from .confidence import pose_is_trusted, summarize_keypoints, summarize_pose_coordinates
from .features import MOTION_FLOOR, motion_statistics
from .gait import compute_gait_metrics
from .motion import read_motion_signal
from .wellness import (
    DEFAULT_WEIGHTS,
    build_limitations,
    build_observation,
    concerning_change,
    historical_change_factor,
    overall_score,
    score_factors,
    weights_used,
)

# Motion is read for the whole clip so a long video can pick its busiest window.
# Pose sampling itself caps the analyzed span at 20 seconds.
MAX_MOTION_FRAMES = 20000

POSE_CONFIDENCE_THRESHOLD = 0.2

# Pose detections below this mean confidence are reported but not trusted enough
# to score stride symmetry from.
MIN_POSE_CONFIDENCE = 0.3

MIN_COMPARABLE_FRAMES = 5
EXPERIMENTAL_COCO_POSE_ENV = "PETLENS_ENABLE_EXPERIMENTAL_COCO_POSE"


def _experimental_coco_pose_enabled() -> bool:
    return os.getenv(EXPERIMENTAL_COCO_POSE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _model_info(
    pipeline: str,
    pose: dict | None,
    detection: dict | None = None,
) -> dict[str, str]:
    """Describe the model that produced this result. Inference stays on the server."""

    if pipeline in ("coco-pose", "dog-pose") and pose is not None:
        version = pose["pose_id"]
        if pose.get("pose_revision"):
            version = f"{version}@{pose['pose_revision']}"
        detector = pose["detector_id"]
        if pose.get("detector_revision"):
            detector = f"{detector}@{pose['detector_revision']}"
        return {
            "pipeline": pipeline,
            "modelName": f"RT-DETR ({detector}) + ViTPose++ COCO-17 output ({version}); canine pose unvalidated",
            "modelVersion": version,
            "runsOn": "server",
        }

    if detection is not None:
        detector = detection["detector_id"]
        if detection.get("detector_revision"):
            detector = f"{detector}@{detection['detector_revision']}"
        return {
            "pipeline": pipeline,
            "modelName": f"OpenCV frame difference + RT-DETR dog detection ({detector})",
            "modelVersion": detector,
            "runsOn": "server",
        }

    return {
        "pipeline": "opencv-motion",
        "modelName": "OpenCV frame difference",
        "modelVersion": cv2.__version__,
        "runsOn": "server",
    }


def ai_use_ids(pipeline: str, *, dog_detection: bool = False) -> list[str]:
    """Registry ids for the steps that produced one result.

    Frame-difference motion runs on every successful clip, including when
    pose also runs. ``development`` is a product fact, not a per-clip step.
    ``llm-rewrite`` is added by the API only when a validated rewrite is kept.
    The previous pipeline name is accepted so an old caller still gets a list.
    This pipeline does not emit that name.
    """

    shared = ["motion-fallback", "scoring", "observation-rules"]
    if pipeline in ("coco-pose", "dog-pose"):
        return ["dog-detector", "pose-model", *shared]
    if pipeline == "movenet":
        return ["pose-model", *shared]
    if dog_detection:
        return ["dog-detector", *shared]
    return shared


def _pose_sample(keypoints, boxes) -> list[dict[str, float | str]] | None:
    """One frame of checkpoint joints, normalized to that frame's dog box.

    Names come from ``MODEL_OUTPUT_KEYPOINTS``. For this checkpoint those
    names are COCO-17, not AP-10K.
    """

    from .pose_backend import KEYPOINT_MIN_SCORE, MODEL_OUTPUT_KEYPOINTS

    best_index = None
    best_count = 0
    for index, box in enumerate(boxes):
        if box is None:
            continue
        count = int(np.count_nonzero(keypoints[index, :, 2] >= KEYPOINT_MIN_SCORE))
        if count > best_count:
            best_index = index
            best_count = count
    if best_index is None:
        return None
    origin_x, origin_y, width, height = boxes[best_index]
    if width <= 1 or height <= 1:
        return None
    sample: list[dict[str, float | str]] = []
    for name, point in zip(MODEL_OUTPUT_KEYPOINTS, keypoints[best_index]):
        if not np.isfinite(point[0]) or not np.isfinite(point[1]):
            continue
        if float(point[2]) < KEYPOINT_MIN_SCORE:
            continue
        x = (float(point[0]) - float(origin_x)) / float(width)
        y = (float(point[1]) - float(origin_y)) / float(height)
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            continue
        sample.append({
            "name": name,
            "x": round(x, 4),
            "y": round(y, 4),
            "confidence": round(float(point[2]), 4),
        })
    return sample


def _clean_pet_name(pet_name: str | None) -> str | None:
    """Keep the display name short and free of line breaks before it enters text."""

    if not pet_name:
        return None
    cleaned = " ".join(pet_name.split())[:40]
    return cleaned or None


def _try_pose_and_detection(
    video_path: Path,
) -> tuple[Any | None, dict[str, Any] | None, str | None]:
    """Run experimental pose only by opt-in; otherwise retain dog detection."""

    try:
        from .pose_backend import get_pose_backend
        from .sampling import sample_video
    except ImportError as exc:
        return None, None, f"pose modules unavailable: {exc}"

    frames = []
    backend = None
    result = None
    pose_error = None
    try:
        frames = sample_video(video_path)
        backend = get_pose_backend()
        if _experimental_coco_pose_enabled():
            result = backend.process(frames)
            if result.keypoint_schema != "coco-17":
                raise ValueError(
                    f"Pose schema {result.keypoint_schema!r} is not enabled for application inference."
                )
        else:
            pose_error = (
                f"Experimental COCO-17 pose is disabled by default; set "
                f"{EXPERIMENTAL_COCO_POSE_ENV}=true to opt in"
            )
    except Exception as pose_exc:  # noqa: BLE001 - optional model failures must fall back
        pose_error = f"{type(pose_exc).__name__}: {pose_exc}"

    if pose_error is not None:
        try:
            if backend is None:
                backend = get_pose_backend()
            detection = backend.detect(frames)
        except Exception as detection_exc:  # noqa: BLE001 - detection is optional too
            return (
                None,
                None,
                f"{pose_error}; detector-only analysis unavailable: "
                f"{type(detection_exc).__name__}: {detection_exc}",
            )
        return (
            None,
            {
                "dog_frames_share": detection.dog_frames_share,
                "multiple_dogs": detection.multiple_dogs,
                "person_present": detection.person_present,
                "detector_id": detection.detector_id,
                "detector_revision": detection.detector_revision,
                "track_states": detection.track_states,
                "track_segment_ids": detection.track_segment_ids,
            },
            f"{pose_error}; pose unavailable, dog detection only",
        )

    assert result is not None
    return {
        "keypoints": result.keypoints,
        "dog_frames_share": result.dog_frames_share,
        "multiple_dogs": result.multiple_dogs,
        "person_present": result.person_present,
        "detector_id": result.detector_id,
        "pose_id": result.pose_id,
        "detector_revision": result.detector_revision,
        "pose_revision": result.pose_revision,
        "width": frames[0].width if frames else None,
        "height": frames[0].height if frames else None,
        "timestamps": result.timestamps_seconds,
        "boxes": result.boxes,
        "keypoint_schema": result.keypoint_schema,
        "track_states": result.track_states,
        "track_segment_ids": result.track_segment_ids,
    }, {
        "dog_frames_share": result.dog_frames_share,
        "multiple_dogs": result.multiple_dogs,
        "person_present": result.person_present,
        "detector_id": result.detector_id,
        "detector_revision": result.detector_revision,
        "track_states": result.track_states,
        "track_segment_ids": result.track_segment_ids,
    }, None


def _try_pose(video_path: Path) -> tuple[Any | None, str | None]:
    """Compatibility wrapper for callers that need only the pose result."""

    pose, _detection, reason = _try_pose_and_detection(video_path)
    return pose, reason


def _track_segment_count(pose: dict | None) -> int | None:
    if pose is None:
        return None
    ids = {segment for segment in pose.get("track_segment_ids") or [] if segment is not None}
    return len(ids)


def _ambiguous_track_frames(pose: dict | None) -> int | None:
    if pose is None:
        return None
    return sum(1 for state in pose.get("track_states") or [] if state == "ambiguous")


def _assess_signal(pipeline: str, measurements: dict) -> tuple[str, str]:
    """Decide how much the measurements from this clip can be trusted."""

    if measurements["frameCount"] < MIN_COMPARABLE_FRAMES:
        return (
            "unusable",
            "The clip was too short to compare enough frames.",
        )

    if measurements["motionMean"] < MOTION_FLOOR:
        return (
            "unusable",
            "Almost no movement was visible between frames, so there was nothing to measure.",
        )

    if pipeline == "opencv-motion":
        return (
            "limited",
            "No pet pose landmarks were available for this clip, so stride symmetry "
            "was not measured.",
        )

    if pipeline == "coco-pose":
        return (
            "limited",
            "The available pose head returns human COCO-17 landmarks, not validated canine "
            "landmarks, so stride measurements were not made.",
        )

    if not measurements["symmetryReliable"]:
        return (
            "limited",
            "Pose landmarks were found, but the leg detections were not confident enough "
            "to compare the two sides.",
        )

    return (
        "good",
        "Pose landmarks were confident enough to compare both sides of the body.",
    )


# The screen looks for this sentence when pose was stopped and motion was kept.
POSE_TIME_LIMIT_NOTE = (
    "Pose analysis exceeded its time limit. Picture motion was measured. "
    "Stride length and symmetry were not measured."
)


def analyze_clip(
    video_path: str | Path,
    *,
    pet_name: str | None = None,
    previous_overall: float | None = None,
    previous_pipeline: str | None = None,
    use_pose: bool = True,
    model_url: str | None = None,
    motion_ready: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    del model_url  # Older callers passed a pose URL. It is ignored.
    """Analyze one movement clip and return an ``AnalyzeResult`` dictionary.

    Raises:
        FileNotFoundError: the clip does not exist.
        ValueError: the clip could not be decoded as video.
    """

    path = Path(video_path)
    signal = read_motion_signal(path, max_frames=MAX_MOTION_FRAMES)
    motion_mean, motion_std, motion_coverage = motion_statistics(signal.frame_motion)

    measurements: dict[str, Any] = {
        "poseKeypoints": None,
        "frameCount": signal.frames_read,
        "durationSeconds": signal.duration_seconds,
        "meanKeypointConfidence": None,
        "leftAnkleMotion": None,
        "rightAnkleMotion": None,
        "strideSymmetry": None,
        "asymmetryPercent": None,
        "motionMean": motion_mean,
        "motionStd": motion_std,
        "motionCoverage": motion_coverage,
        "hipStability": None,
        "symmetryReliable": False,
    }

    pipeline = "opencv-motion"
    pose_skip_reason: str | None = "pose extraction was disabled for this run"
    model_confidence: float | None = None
    frames_used: int | None = None
    frames_total: int | None = None
    low_confidence = False

    pose_payload = None
    detection_payload = None

    def pack(note_override: str | None = None) -> dict[str, Any]:
        signal_quality, signal_note = _assess_signal(pipeline, measurements)
        if low_confidence and signal_quality != "unusable":
            signal_quality = "limited"
            signal_note = (
                "Pose landmarks were found, but confidence was too low to measure the legs. "
                "Try a clearer clip, filmed from the side with the whole body in frame."
            )
        if note_override is not None and signal_quality != "unusable":
            signal_quality = "limited"
            signal_note = note_override

        notes = quality_notes(
            frames_read=signal.frames_read,
            fps=signal.fps,
            duration_seconds=signal.duration_seconds,
            width=signal.width,
            height=signal.height,
            brightness=signal.brightness,
            motion_mean=motion_mean,
            motion_coverage=motion_coverage,
        )

        if signal_quality == "unusable":
            # Refuse to publish scores that were built from nothing.
            factors: dict[str, float | None] = {
                "movementConsistency": None,
                "symmetry": None,
                "mobility": None,
                "activity": None,
                "historicalChange": None,
            }
            overall = None
        else:
            factors = score_factors(measurements)
            overall = overall_score(factors)

        # Trends are only meaningful between clips measured the same way.
        comparable_previous = (
            previous_overall
            if previous_overall is not None and previous_pipeline == pipeline
            else None
        )

        # historical_change_factor returns None on a first walk. When that factor
        # has a weight, the overall indicator is recomputed so the comparison counts.
        if signal_quality != "unusable":
            factors["historicalChange"] = historical_change_factor(
                overall, comparable_previous
            )
            if "historicalChange" in DEFAULT_WEIGHTS:
                overall = overall_score(factors)

        concerning = concerning_change(overall, comparable_previous, measurements)
        observation = build_observation(
            pet_name=_clean_pet_name(pet_name),
            measurements=measurements,
            factors=factors,
            overall=overall,
            previous_overall=comparable_previous,
            signal_quality=signal_quality,
            signal_note=signal_note,
            concerning=concerning,
        )

        confidence = measurements["meanKeypointConfidence"]

        return {
            "ok": True,
            "pipeline": pipeline,
            "signalQuality": signal_quality,
            "signalNote": signal_note,
            "measurements": measurements,
            "factors": factors,
            "overallScore": overall,
            "strideSymmetryScore": factors["symmetry"],
            "asymmetryPercent": (
                measurements["asymmetryPercent"] if measurements["symmetryReliable"] else None
            ),
            "confidence": None if confidence is None else round(confidence * 100, 1),
            "observation": observation,
            "limitations": build_limitations(pipeline, signal_quality),
            "concerningChange": concerning,
            "usedLlm": False,
            "weightsUsed": weights_used(factors),
            "modelInfo": _model_info(pipeline, pose_payload, detection_payload),
            "modelConfidence": model_confidence,
            "framesUsed": frames_used,
            "framesTotal": frames_total,
            "lowConfidence": low_confidence,
            "qualityNotes": notes,
            "aiUse": ai_use_ids(pipeline, dog_detection=detection_payload is not None),
            "diagnostics": {
                "fps": signal.fps,
                "framePairs": len(signal.frame_motion),
                "poseSkipReason": pose_skip_reason,
                "trackSegments": _track_segment_count(detection_payload),
                "ambiguousTrackFrames": _ambiguous_track_frames(detection_payload),
                "dogFramesShare": (
                    None
                    if detection_payload is None
                    else detection_payload["dog_frames_share"]
                ),
                "multipleDogs": (
                    None
                    if detection_payload is None
                    else detection_payload["multiple_dogs"]
                ),
                "personPresent": (
                    None
                    if detection_payload is None
                    else detection_payload["person_present"]
                ),
                "configuredWeights": DEFAULT_WEIGHTS,
                "comparedToPrevious": comparable_previous is not None,
            },
        }

    # Motion is already measured. Save it before pose starts so a deadline
    # during model load can keep this result instead of failing the clip.
    if use_pose and motion_ready is not None:
        motion_ready(pack(POSE_TIME_LIMIT_NOTE))

    if use_pose:
        pose_payload, detection_payload, pose_skip_reason = _try_pose_and_detection(path)
        if detection_payload is not None:
            measurements["subject"] = {
                "dogFramesShare": detection_payload["dog_frames_share"],
                "multipleDogs": detection_payload["multiple_dogs"],
                "personPresent": detection_payload["person_present"],
            }
        if pose_payload is not None:
            pipeline = "coco-pose"
            keypoints = pose_payload["keypoints"]
            summary = summarize_keypoints(
                keypoints,
                frame_threshold=MIN_POSE_CONFIDENCE,
            )
            model_confidence = summary["modelConfidence"]
            frames_used = summary["framesUsed"]
            frames_total = summary["framesTotal"]
            measurements["poseKeypoints"] = summarize_pose_coordinates(
                keypoints,
                frame_threshold=MIN_POSE_CONFIDENCE,
                keypoint_threshold=POSE_CONFIDENCE_THRESHOLD,
                frame_width=pose_payload["width"],
                frame_height=pose_payload["height"],
            )
            measurements["meanKeypointConfidence"] = model_confidence
            from .pose_backend import SCHEMA_LIMIT

            if pose_payload["keypoint_schema"] != "ap10k":
                # These channels are not an AP-10K array. Running the stride
                # math would treat the right ear as the base of the tail.
                measurements["notMeasuredReasons"] = [SCHEMA_LIMIT]
                measurements["symmetryReliable"] = False
            else:
                gait = compute_gait_metrics(
                    keypoints,
                    timestamps=pose_payload["timestamps"],
                    boxes=pose_payload["boxes"],
                    dog_frames_share=pose_payload["dog_frames_share"],
                )
                measurements["strideSymmetry"] = gait["strideSymmetry"]
                measurements["asymmetryPercent"] = gait["asymmetryPercent"]
                measurements["symmetryReliable"] = gait["symmetryReliable"]
                measurements["view"] = gait["view"]
                measurements["strides"] = gait["strides"]
                measurements["limbSymmetry"] = gait["limbSymmetry"]
                measurements["strideLengthBodyLengths"] = gait["strideLengthBodyLengths"]
                measurements["cadenceStridesPerMinute"] = gait["cadenceStridesPerMinute"]
                measurements["strideTimeCv"] = gait["strideTimeCv"]
                measurements["headVerticalOscillation"] = gait["headVerticalOscillation"]
                measurements["pelvisVerticalOscillation"] = gait["pelvisVerticalOscillation"]
                measurements["headBobAsymmetry"] = gait["headBobAsymmetry"]
                measurements["pelvisAsymmetry"] = gait["pelvisAsymmetry"]
                measurements["notMeasuredReasons"] = gait["notMeasuredReasons"]
            measurements["subject"] = {
                "dogFramesShare": pose_payload["dog_frames_share"],
                "multipleDogs": pose_payload["multiple_dogs"],
                "personPresent": pose_payload["person_present"],
            }
            measurements["poseSample"] = _pose_sample(
                keypoints,
                pose_payload["boxes"],
            )
            # Below the trust line the limb numbers stay, but the result is
            # marked so the screen can say the pose was not confident.
            # A missing stride value is already None. It is not rewritten to 0.
            if not pose_is_trusted(summary, minimum=MIN_POSE_CONFIDENCE):
                low_confidence = True

    return pack()
