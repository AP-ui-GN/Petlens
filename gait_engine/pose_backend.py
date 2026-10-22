"""Dog detection and the checkpoint's COCO-17 pose head.

The detector is RT-DETR (``PekingU/rtdetr_r50vd_coco_o365``, Apache-2.0).
The pose model is ViTPose++ (``usyd-community/vitpose-plus-base``). The
Transformers docs list dataset index 3 as an AP-10K backbone expert. The
checkpoint's only keypoint head is the 17-channel COCO head in
``config.id2label``. Index 4 of that head is the right ear. The AP-10K name
``root_of_tail`` is index 4 of a different schema and is not this channel.

Pose quality on pet dogs is unproven until a labeled clip set is measured.
A failure to load weights or run pose must be caught by the pipeline and
must not fail the request.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .sampling import DETECT_EVERY_N_FRAMES, SampledFrame
from .tracking import associate_tracks, choose_initial_dog, choose_tracked_dog

DETECTOR_ID = "PekingU/rtdetr_r50vd_coco_o365"
POSE_ID = "usyd-community/vitpose-plus-base"
# Hugging Face docs (transformers model_doc/vitpose), read October 21, 2026:
# 0 COCO, 1 AiC, 2 MPII, 3 AP-10K, 4 APT-36K, 5 COCO-WholeBody.
AP10K_DATASET_INDEX = 3
DOG_DETECT_THRESHOLD = 0.3
KEYPOINT_MIN_SCORE = 0.3
CROP_EXPAND = 0.25
POSE_BATCH = 8

# AP-10K order. Do not read this from the human checkpoint labels.
AP10K_KEYPOINTS: tuple[str, ...] = (
    "left_eye",
    "right_eye",
    "nose",
    "neck",
    "root_of_tail",
    "left_shoulder",
    "left_elbow",
    "left_front_paw",
    "right_shoulder",
    "right_elbow",
    "right_front_paw",
    "left_hip",
    "left_knee",
    "left_back_paw",
    "right_hip",
    "right_knee",
    "right_back_paw",
)

LEFT_EYE = 0
RIGHT_EYE = 1
NOSE = 2
NECK = 3
ROOT_OF_TAIL = 4
LEFT_SHOULDER = 5
LEFT_ELBOW = 6
LEFT_FRONT_PAW = 7
RIGHT_SHOULDER = 8
RIGHT_ELBOW = 9
RIGHT_FRONT_PAW = 10
LEFT_HIP = 11
LEFT_KNEE = 12
LEFT_BACK_PAW = 13
RIGHT_HIP = 14
RIGHT_KNEE = 15
RIGHT_BACK_PAW = 16

# Left/right counterparts. Applied when a frame is mirrored, not on every
# detection. The model is asked for the AP-10K order above.
AP10K_SWAP_PAIRS: tuple[tuple[int, int], ...] = (
    (LEFT_EYE, RIGHT_EYE),
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_ELBOW, RIGHT_ELBOW),
    (LEFT_FRONT_PAW, RIGHT_FRONT_PAW),
    (LEFT_HIP, RIGHT_HIP),
    (LEFT_KNEE, RIGHT_KNEE),
    (LEFT_BACK_PAW, RIGHT_BACK_PAW),
)

# Channels emitted by usyd-community/vitpose-plus-base. This matches
# config.id2label and config.edges on the checkpoint. dataset_index selects
# a backbone expert only. The original ViTPose++ training config has a
# separate AP-10K keypoint head, and that head is not in this checkpoint.
# Do not read these indices as AP-10K names. Index 4 is the right ear, not
# the base of the tail.
COCO17_KEYPOINTS: tuple[str, ...] = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)
COCO17_EDGES: tuple[tuple[int, int], ...] = (
    (15, 13),
    (13, 11),
    (16, 14),
    (14, 12),
    (11, 12),
    (5, 11),
    (6, 12),
    (5, 6),
    (5, 7),
    (6, 8),
    (7, 9),
    (8, 10),
    (1, 2),
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (3, 5),
    (4, 6),
)
MODEL_OUTPUT_SCHEMA = "coco-17"
MODEL_OUTPUT_KEYPOINTS = COCO17_KEYPOINTS
MODEL_OUTPUT_EDGES = COCO17_EDGES
SCHEMA_LIMIT = (
    "This pose head outputs 17 human COCO joints. It does not output the neck "
    "or the base of the tail, so stride length and symmetry were not measured."
)

# Anatomical links for an AP-10K array. These are not the checkpoint edges.
AP10K_SKELETON_EDGES: tuple[tuple[int, int], ...] = (
    (LEFT_EYE, NOSE),
    (RIGHT_EYE, NOSE),
    (NOSE, NECK),
    (NECK, ROOT_OF_TAIL),
    (NECK, LEFT_SHOULDER),
    (LEFT_SHOULDER, LEFT_ELBOW),
    (LEFT_ELBOW, LEFT_FRONT_PAW),
    (NECK, RIGHT_SHOULDER),
    (RIGHT_SHOULDER, RIGHT_ELBOW),
    (RIGHT_ELBOW, RIGHT_FRONT_PAW),
    (ROOT_OF_TAIL, LEFT_HIP),
    (LEFT_HIP, LEFT_KNEE),
    (LEFT_KNEE, LEFT_BACK_PAW),
    (ROOT_OF_TAIL, RIGHT_HIP),
    (RIGHT_HIP, RIGHT_KNEE),
    (RIGHT_KNEE, RIGHT_BACK_PAW),
)


def hf_home() -> Path:
    """Directory for Hugging Face weights. Defaults to ``models/hf``."""

    configured = os.environ.get("HF_HOME")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "models" / "hf"


def swap_left_right(keypoints: np.ndarray) -> np.ndarray:
    """Exchange the AP-10K left/right pairs. ``keypoints`` is (..., 17, 3)."""

    swapped = np.array(keypoints, copy=True)
    for left, right in AP10K_SWAP_PAIRS:
        swapped[..., left, :], swapped[..., right, :] = (
            swapped[..., right, :].copy(),
            swapped[..., left, :].copy(),
        )
    return swapped


@dataclass(frozen=True)
class PoseResult:
    """Pose for the sampled frames.

    ``keypoints`` is ``(frames, 17, 3)`` of ``(x_px, y_px, score)`` in the
    source frame after rotation. A missing point is NaN in x and y with
    score 0. ``boxes`` is one COCO ``(x, y, w, h)`` per frame, or None when
    that frame had no dog box. ``timestamps_seconds`` lines up with frames.
    """

    keypoints: np.ndarray
    boxes: list[tuple[float, float, float, float] | None]
    timestamps_seconds: np.ndarray
    dog_frames_share: float
    multiple_dogs: bool
    person_present: bool
    detector_id: str
    pose_id: str
    detector_revision: str | None
    pose_revision: str | None
    keypoint_schema: str = MODEL_OUTPUT_SCHEMA
    track_states: tuple[str, ...] = ()
    track_segment_ids: tuple[int | None, ...] = ()


class PoseBackend(ABC):
    """One pose implementation. ``process`` does not catch its own failures."""

    @abstractmethod
    def process(self, frames: list[SampledFrame]) -> PoseResult:
        """Return keypoints for already-sampled frames."""


def crop_from_keypoints(
    keypoints: np.ndarray,
    width: int,
    height: int,
    *,
    min_score: float = KEYPOINT_MIN_SCORE,
    expand: float = CROP_EXPAND,
) -> tuple[float, float, float, float] | None:
    """COCO box around valid keypoints, expanded by ``expand`` on each side."""

    if keypoints.shape != (len(MODEL_OUTPUT_KEYPOINTS), 3):
        return None
    valid = np.isfinite(keypoints[:, 0]) & np.isfinite(keypoints[:, 1]) & (keypoints[:, 2] >= min_score)
    if int(np.count_nonzero(valid)) < 2:
        return None
    xs = keypoints[valid, 0]
    ys = keypoints[valid, 1]
    x1, x2 = float(np.min(xs)), float(np.max(xs))
    y1, y2 = float(np.min(ys)), float(np.max(ys))
    box_w = max(1.0, x2 - x1)
    box_h = max(1.0, y2 - y1)
    x1 -= box_w * expand
    x2 += box_w * expand
    y1 -= box_h * expand
    y2 += box_h * expand
    x1 = min(max(0.0, x1), max(0, width - 1))
    y1 = min(max(0.0, y1), max(0, height - 1))
    x2 = min(max(x1 + 1.0, x2), float(width))
    y2 = min(max(y1 + 1.0, y2), float(height))
    return (x1, y1, x2 - x1, y2 - y1)


def normalize_to_box(
    x: float, y: float, box: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Map a source-frame pixel into a COCO box, as fractions of that box."""

    origin_x, origin_y, width, height = box
    return (x - origin_x) / width, (y - origin_y) / height


def denormalize_from_box(
    x: float, y: float, box: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Map a box fraction back to a source-frame pixel."""

    origin_x, origin_y, width, height = box
    return origin_x + x * width, origin_y + y * height


def dog_boxes_from_detections(
    labels,
    scores,
    xyxy,
    *,
    dog_id: int,
    person_id: int | None,
    threshold: float,
) -> tuple[list[tuple[float, float, float, float]], int, bool]:
    """Keep dog boxes. A person box is recorded and is not returned as the dog."""

    dogs: list[tuple[float, float, float, float]] = []
    dog_count = 0
    saw_person = False
    for label, score, box in zip(labels, scores, xyxy):
        if float(score) < threshold:
            continue
        coco = (
            float(box[0]),
            float(box[1]),
            float(box[2] - box[0]),
            float(box[3] - box[1]),
        )
        if int(label) == int(dog_id):
            dog_count += 1
            if coco[2] > 1 and coco[3] > 1:
                dogs.append(coco)
        elif person_id is not None and int(label) == int(person_id):
            saw_person = True
    return dogs, dog_count, saw_person


def _empty_keypoints(count: int) -> np.ndarray:
    array = np.full((count, len(MODEL_OUTPUT_KEYPOINTS), 3), np.nan, dtype=np.float32)
    array[:, :, 2] = 0.0
    return array


class VitPoseCoco17Backend(PoseBackend):
    """Top-down pose from the COCO-17 head. Models load once per process.

    Dataset index 3 selects a backbone expert. It does not switch this
    checkpoint to an AP-10K keypoint head.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._device = "cpu"
        self._detector = None
        self._detector_processor = None
        self._pose = None
        self._pose_processor = None
        self._dog_id: int | None = None
        self._person_id: int | None = None
        self._detector_revision: str | None = None
        self._pose_revision: str | None = None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        home = hf_home()
        home.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(home)

        import torch
        from transformers import (
            RTDetrForObjectDetection,
            RTDetrImageProcessor,
            VitPoseForPoseEstimation,
            VitPoseImageProcessor,
        )

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._detector_processor = RTDetrImageProcessor.from_pretrained(DETECTOR_ID)
        self._detector = RTDetrForObjectDetection.from_pretrained(DETECTOR_ID)
        self._detector.to(self._device)
        self._detector.eval()
        labels = {value: key for key, value in self._detector.config.id2label.items()}
        self._dog_id = labels["dog"]
        self._person_id = labels.get("person")

        self._pose_processor = VitPoseImageProcessor.from_pretrained(POSE_ID)
        self._pose = VitPoseForPoseEstimation.from_pretrained(POSE_ID)
        self._pose.to(self._device)
        self._pose.eval()
        self._detector_revision = _revision(DETECTOR_ID)
        self._pose_revision = _revision(POSE_ID)
        self._loaded = True

    def process(self, frames: list[SampledFrame]) -> PoseResult:
        if not frames:
            raise ValueError("No frames were sampled.")
        self._ensure_loaded()

        keypoints = _empty_keypoints(len(frames))
        observations: list[list[tuple[float, float, float, float]]] = []
        multiple_dogs = False
        person_present = False

        # The detector runs on a fixed stride. Frames in between are empty
        # observations. Tracking does not copy the last box into that gap.
        for index, frame in enumerate(frames):
            if index % DETECT_EVERY_N_FRAMES != 0:
                observations.append([])
                continue
            detected, dog_count, saw_person = self._detect(frame)
            multiple_dogs = multiple_dogs or dog_count > 1
            person_present = person_present or saw_person
            observations.append(detected)

        decisions = associate_tracks(observations)
        if any(decision.state == "ambiguous" for decision in decisions):
            multiple_dogs = True
        boxes: list[tuple[float, float, float, float] | None] = [
            decision.box if decision.state in ("tracked", "new_segment") else None
            for decision in decisions
        ]
        ready = [index for index, box in enumerate(boxes) if box is not None]
        for start in range(0, len(ready), POSE_BATCH):
            self._pose_chunk(frames, boxes, ready[start : start + POSE_BATCH], keypoints)

        dog_frames = sum(1 for box in boxes if box is not None)
        share = dog_frames / len(frames)

        return PoseResult(
            keypoints=keypoints,
            boxes=boxes,
            timestamps_seconds=np.asarray(
                [frame.timestamp_seconds for frame in frames], dtype=np.float64
            ),
            dog_frames_share=round(share, 4),
            multiple_dogs=multiple_dogs,
            person_present=person_present,
            detector_id=DETECTOR_ID,
            pose_id=POSE_ID,
            detector_revision=self._detector_revision,
            pose_revision=self._pose_revision,
            keypoint_schema=MODEL_OUTPUT_SCHEMA,
            track_states=tuple(decision.state for decision in decisions),
            track_segment_ids=tuple(decision.segment_id for decision in decisions),
        )

    def _pose_chunk(
        self,
        frames: list[SampledFrame],
        boxes: list[tuple[float, float, float, float] | None],
        indexes: list[int],
        keypoints: np.ndarray,
    ) -> None:
        from PIL import Image

        images = [Image.fromarray(frames[index].image_bgr[:, :, ::-1]) for index in indexes]
        chunk_boxes = [boxes[index] for index in indexes]
        if any(box is None for box in chunk_boxes):
            return
        self._run_pose_batch(images, chunk_boxes, indexes, keypoints)  # type: ignore[arg-type]

    def _detect(
        self, frame: SampledFrame
    ) -> tuple[list[tuple[float, float, float, float]], int, bool]:
        import torch
        from PIL import Image

        assert self._detector is not None
        assert self._detector_processor is not None
        assert self._dog_id is not None
        image = Image.fromarray(frame.image_bgr[:, :, ::-1])
        inputs = self._detector_processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        with torch.inference_mode():
            outputs = self._detector(**inputs)
        results = self._detector_processor.post_process_object_detection(
            outputs,
            target_sizes=[(frame.height, frame.width)],
            threshold=DOG_DETECT_THRESHOLD,
        )[0]
        labels = results["labels"].detach().cpu().numpy()
        scores = results["scores"].detach().cpu().numpy()
        xyxy = results["boxes"].detach().cpu().numpy()
        return dog_boxes_from_detections(
            labels,
            scores,
            xyxy,
            dog_id=int(self._dog_id),
            person_id=None if self._person_id is None else int(self._person_id),
            threshold=DOG_DETECT_THRESHOLD,
        )

    def _run_pose_batch(
        self,
        images: list,
        boxes: list[tuple[float, float, float, float]],
        indexes: list[int],
        keypoints: np.ndarray,
    ) -> None:
        import torch

        assert self._pose is not None
        assert self._pose_processor is not None
        box_array = np.asarray(boxes, dtype=np.float32)
        # One box per image. The processor wants a list of boxes per image.
        per_image = [[list(map(float, box))] for box in boxes]
        inputs = self._pose_processor(images, boxes=per_image, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        dataset_index = torch.full(
            (len(images),),
            AP10K_DATASET_INDEX,
            dtype=torch.long,
            device=self._device,
        )
        with torch.inference_mode():
            outputs = self._pose(**inputs, dataset_index=dataset_index)
        processed = self._pose_processor.post_process_pose_estimation(
            outputs, boxes=per_image
        )
        for index, poses in zip(indexes, processed):
            parsed = _first_pose(poses)
            if parsed is None:
                continue
            keypoints[index] = parsed


def _first_pose(poses) -> np.ndarray | None:
    """Read the first pose dict into ``(17, 3)`` pixel coordinates."""

    if not poses:
        return None
    pose = poses[0] if isinstance(poses, list) else poses
    if not isinstance(pose, dict):
        return None
    raw = pose.get("keypoints")
    if raw is None:
        return None
    array = np.asarray(raw.detach().cpu() if hasattr(raw, "detach") else raw, dtype=np.float32)
    scores = pose.get("scores")
    if scores is not None:
        score_array = np.asarray(
            scores.detach().cpu() if hasattr(scores, "detach") else scores,
            dtype=np.float32,
        ).reshape(-1)
    elif array.ndim == 2 and array.shape[-1] >= 3:
        score_array = array[:, 2]
        array = array[:, :2]
    else:
        return None
    if array.ndim != 2 or array.shape[0] < len(MODEL_OUTPUT_KEYPOINTS) or array.shape[1] < 2:
        return None
    points = np.zeros((len(MODEL_OUTPUT_KEYPOINTS), 3), dtype=np.float32)
    count = len(MODEL_OUTPUT_KEYPOINTS)
    points[:, 0] = array[:count, 0]
    points[:, 1] = array[:count, 1]
    if score_array.shape[0] >= count:
        points[:, 2] = score_array[:count]
    low = points[:, 2] < KEYPOINT_MIN_SCORE
    points[low, 0] = np.nan
    points[low, 1] = np.nan
    return points


def _revision(model_id: str) -> str | None:
    """Commit hash of a cached snapshot, or None when it was not recorded."""

    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None
    resolved = try_to_load_from_cache(model_id, "config.json")
    if not isinstance(resolved, str):
        return None
    # .../snapshots/<revision>/config.json
    parts = Path(resolved).parts
    if "snapshots" not in parts:
        return None
    return parts[parts.index("snapshots") + 1]


_BACKEND: VitPoseCoco17Backend | None = None


def get_pose_backend() -> VitPoseCoco17Backend:
    """Return the process-wide backend. Weights load on the first ``process``."""

    global _BACKEND
    if _BACKEND is None:
        _BACKEND = VitPoseCoco17Backend()
    return _BACKEND
