"""Pose-only input contract for a future ContactVision-style canine model.

v1: 17 AP-10K joints, each [relative_x, relative_y, raw_score, observed],
followed by source delta_seconds (69 float32 channels). Relative coordinates
use the neck/tail-root midpoint and their projected distance. Raw scores are
uncalibrated responses, NOT probabilities. No interpolation or score clipping.

Model channels never establish anatomical/physical identity. This module only
builds features; the offline preparer supplies separately verified target masks.
Window indices use -1 for padding; padding_mask=True means ignore in attention.
Feature segments/windows alone do not assert physical-paw continuity.
"""
from __future__ import annotations

from fractions import Fraction
import math

import numpy as np

from .inference import NAMES

VERSION = "petlens.contact-features.v1"
PAWS = ("LF", "RF", "LH", "RH")
PAW_INDICES = (7, 10, 13, 16)
CHANNELS = tuple(f"{name}.{field}" for name in NAMES
                 for field in ("relative_x", "relative_y", "raw_score", "observed")) + ("delta_seconds",)
POLICY = dict(pointMinRawScore=0.50, neckMinRawScore=0.70,
              tailRootMinRawScore=0.80, minimumBodyLengthPixels=1e-6,
              maxGapSeconds=0.25, windowLength=128, windowStride=64,
              interpolation=False, scoreClipping=False,
              rawScoresAreProbabilities=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_timing(predictions, source):
    """Check every original integer PTS against the saved prediction timestamp.

    No frameIndex/FPS fallback. File identity/hashes are checked by the caller.
    Time bases are retained as rationals, rather than inferred from nominal FPS.
    """
    frames = predictions.get("frames")
    refs = source.get("frames")
    require(isinstance(frames, list) and frames and isinstance(refs, list),
            "Missing prediction/source frames")
    require(type(predictions.get("frameCount")) is int and
            len(frames) == predictions["frameCount"] == source.get("frameCount") == len(refs),
            "Source/prediction frame count mismatch")
    for field in ("frameWidth", "frameHeight"):
        require(type(source.get(field)) is int and source[field] > 0, "Invalid source dimensions")
    previous = -1.0
    for i, (frame, ref) in enumerate(zip(frames, refs)):
        require(type(frame.get("frameIndex")) is int and
                type(ref.get("frameIndex")) is int and frame["frameIndex"] == ref["frameIndex"] == i,
                "Frame indices must be consecutive and unique from zero")
        require(type(ref.get("originalPts")) is int and 0 <= ref["originalPts"] < 2**63,
                "Missing/invalid original integer PTS")
        base = ref.get("originalTimeBase")
        require(isinstance(base, str) and "/" in base, "Missing original rational time base")
        try:
            rational = Fraction(base)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("Invalid original time base") from exc
        require(rational > 0, "Invalid original time base")
        t = ref.get("timestampSeconds")
        require(finite(t) and t >= 0 and t > previous, "Invalid/nonmonotonic source timestamp")
        require(math.isclose(t, float(ref["originalPts"] * rational), rel_tol=0, abs_tol=1e-6),
                "Original PTS/time base disagrees with timestamp")
        require(finite(frame.get("timestampSeconds")) and
                math.isclose(frame["timestampSeconds"], t, rel_tol=0, abs_tol=1e-6),
                "Prediction/source timestamp mismatch")
        previous = t


def convert_sequence(predictions, source):
    """Return finite model features and separate reason-coded observation masks.

    Nonfinite/missing points are masked (not interpolated). Structural errors
    such as duplicate or foreign joints fail. Original numbers remain in the
    caller's unmodified JSON and precision-preserving audit artifact.
    """
    require(predictions.get("poseModel") == "OpenMMLab RTMPose-m AP-10K" and
            predictions.get("keypointSchema") == "AP-10K, 17 keypoints",
            "Expected saved RTMPose AP-10K predictions")
    validate_timing(predictions, source)
    count = predictions["frameCount"]
    features = np.zeros((count, 17, 4), dtype=np.float32)
    observed = np.zeros((count, 17), dtype=bool)
    reasons = np.full((count, 17), "missing_point", dtype="U40")
    reference_valid = np.zeros(count, dtype=bool)
    reference_reasons = np.full(count, "missing_body_reference", dtype="U40")
    centers = np.zeros((count, 2), dtype=np.float64)
    scales = np.zeros(count, dtype=np.float64)
    limit = float(np.finfo(np.float32).max)
    width, height = source["frameWidth"], source["frameHeight"]
    for i, frame in enumerate(predictions["frames"]):
        require(type(frame.get("detectionSuccess")) is bool, "Missing detection status")
        points = frame.get("keypoints")
        require(isinstance(points, list) and all(isinstance(p, dict) for p in points),
                "Invalid keypoint list")
        names = [p.get("name") for p in points]
        require(all(isinstance(n, str) and n in NAMES for n in names) and
                len(names) == len(set(names)), "Duplicate/unknown AP-10K keypoint")
        by_name = {p["name"]: p for p in points}
        for j, name in enumerate(NAMES):
            point = by_name.get(name)
            if point is None:
                continue
            score = point.get("rawScore")
            # Finite responses, including >1 and low scores, retain their value.
            if finite(score) and abs(score) <= limit:
                features[i, j, 2] = score
            if not all(finite(point.get(k)) for k in ("x", "y", "rawScore")):
                reason = "nonfinite_or_invalid_point"
            elif abs(score) > limit:
                reason = "score_not_float32_representable"
            elif not frame["detectionSuccess"]:
                reason = "detection_failed"
            elif not (0 <= point["x"] < width and 0 <= point["y"] < height):
                reason = "out_of_bounds"
            elif score < POLICY["pointMinRawScore"]:
                reason = "low_raw_score"
            else:
                reason = "observed"
                observed[i, j] = True
            reasons[i, j] = reason
        neck, tail = by_name.get("neck"), by_name.get("root_of_tail")
        if not (observed[i, 3] and observed[i, 4]):
            continue
        if neck["rawScore"] < POLICY["neckMinRawScore"] or tail["rawScore"] < POLICY["tailRootMinRawScore"]:
            reference_reasons[i] = "low_body_reference_score"
            continue
        # Promote the existing make_reference('B') midpoint/distance math only.
        center = ((neck["x"] + tail["x"]) / 2, (neck["y"] + tail["y"]) / 2)
        length = math.hypot(neck["x"] - tail["x"], neck["y"] - tail["y"])
        if not math.isfinite(length) or length <= POLICY["minimumBodyLengthPixels"]:
            reference_reasons[i] = "invalid_body_reference_scale"
            continue
        centers[i], scales[i] = center, length
        reference_valid[i], reference_reasons[i] = True, "valid"
        for j, name in enumerate(NAMES):
            if observed[i, j]:
                point = by_name[name]
                features[i, j, :2] = ((point["x"] - center[0]) / length,
                                       (point["y"] - center[1]) / length)
    features[:, :, 3] = observed
    times = np.array([f["timestampSeconds"] for f in source["frames"]], dtype=np.float64)
    deltas = np.concatenate(([0.0], np.diff(times)))
    require(np.all(deltas <= limit), "Elapsed time not float32 representable")
    matrix = np.column_stack((features.reshape(count, 68), deltas.astype(np.float32)))
    require(np.isfinite(matrix).all(), "Nonfinite derived feature")
    return dict(features=matrix, frame_indices=np.arange(count, dtype=np.int64),
                original_pts=np.array([f["originalPts"] for f in source["frames"]], dtype=np.int64),
                original_time_bases=np.array([f["originalTimeBase"] for f in source["frames"]]),
                timestamps=times, delta_seconds=deltas, observed_mask=observed,
                observation_reasons=reasons, reference_valid=reference_valid,
                reference_reasons=reference_reasons, body_centers=centers, body_scales=scales)


def make_windows(reference_valid, timestamps, identity_segments=None):
    """Index 128-frame windows inside valid source/identity/time segments.

    Called separately per source/dog/split. Identity -1 means unverified, never
    confirmed. A change in any supplied paw identity segment breaks the window.
    Missing body references and >250ms gaps break feature segments as well.
    """
    count = len(timestamps)
    require(len(reference_valid) == count, "Window mask length mismatch")
    require(np.isfinite(timestamps).all() and np.all(np.diff(timestamps) > 0),
            "Window timestamps must be finite and increasing")
    if identity_segments is not None:
        require(identity_segments.shape == (count, 4), "Identity segment shape mismatch")
    segment_ids = np.full(count, -1, dtype=np.int64)
    segments, start = [], None
    for i in range(count):
        changed = i > 0 and (timestamps[i] - timestamps[i-1] > POLICY["maxGapSeconds"] or
                            (identity_segments is not None and
                             np.any(identity_segments[i] != identity_segments[i-1])))
        if start is not None and (not reference_valid[i] or changed):
            segments.append((start, i))
            start = None
        if reference_valid[i] and start is None:
            start = i
    if start is not None:
        segments.append((start, count))
    indices, window_segments = [], []
    for sid, (first, end) in enumerate(segments):
        segment_ids[first:end] = sid
        offset = first
        while offset < end:
            stop = min(offset + POLICY["windowLength"], end)
            row = np.full(POLICY["windowLength"], -1, dtype=np.int64)
            row[:stop-offset] = np.arange(offset, stop)
            indices.append(row)
            window_segments.append(sid)
            if stop == end:
                break
            offset += POLICY["windowStride"]
    indices = np.array(indices, dtype=np.int64).reshape(-1, POLICY["windowLength"])
    return dict(segment_ids=segment_ids, window_indices=indices,
                padding_mask=indices == -1,
                window_segments=np.array(window_segments, dtype=np.int64))


def canonical_dog_id(value):
    return value.strip().casefold() if isinstance(value, str) and value.strip() else None


def validate_partitions(records):
    """Fail closed on dog, provenance group, source or derivative split leakage.

    Records must include all participating imports, not just training windows.
    Unknown/unassigned identities remain inspectable but cannot prove readiness.
    No fitted statistics exist in this adapter.
    """
    assigned, owners = {}, {}
    for record in records:
        split = record.get("split", "unassigned")
        require(split in ("train", "validation", "test", "exploratory_evaluation", "unassigned"),
                "Unsupported split")
        dog_id = canonical_dog_id(record.get("dogId"))
        for sha in record.get("lineageHashes", []):
            if dog_id:
                require(sha not in owners or owners[sha] == dog_id,
                        "Conflicting dog identities for the same source/derivative")
                owners[sha] = dog_id
        if split == "unassigned":
            continue
        keys = [("dog", dog_id),
                ("group", canonical_dog_id(record.get("provenanceGroup")))]
        keys += [("hash", h) for h in record.get("lineageHashes", [])]
        for kind, value in keys:
            if value is None:
                continue
            key = (kind, value)
            require(key not in assigned or assigned[key] == split,
                    f"Split leakage for {kind} {value}: {assigned.get(key)} / {split}")
            assigned[key] = split
    return assigned
