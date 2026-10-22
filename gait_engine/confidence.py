"""Pose confidence summary.

A keypoint below the per-point threshold is already ignored inside each metric.
This module decides whether the pose result as a whole is trustworthy enough to
publish. A missing confidence is None, never zero.

Keypoints are ``(frames, 17, 3)`` in the checkpoint order
(``MODEL_OUTPUT_KEYPOINTS``): ``(x_px, y_px, score)``.
"""

from __future__ import annotations

import math

import numpy as np

from .pose_backend import MODEL_OUTPUT_KEYPOINTS


def summarize_keypoints(keypoints, *, frame_threshold: float) -> dict:
    """Return modelConfidence (0-1 or None), framesUsed, and framesTotal.

    A frame is counted in framesUsed when the mean confidence of its keypoints
    is at least ``frame_threshold``. framesTotal is every frame that was run.
    modelConfidence is the mean of finite keypoint confidences. It is None when
    no finite confidence was stored.
    """

    array = np.asarray(keypoints, dtype=np.float32)
    if array.ndim != 3 or array.shape[-1] < 3:
        raise ValueError("keypoints must have shape (frames, points, 3).")
    if not 0.0 <= frame_threshold <= 1.0:
        raise ValueError("frame_threshold must be between 0 and 1.")

    confidence = array[:, :, 2]
    frames_total = int(confidence.shape[0])
    finite = np.isfinite(confidence)
    if not np.any(finite):
        return {
            "modelConfidence": None,
            "framesUsed": 0,
            "framesTotal": frames_total,
        }

    frame_means: list[float] = []
    for frame in confidence:
        usable = frame[np.isfinite(frame)]
        if usable.size == 0:
            frame_means.append(0.0)
            continue
        frame_means.append(float(np.mean(usable)))

    frames_used = sum(1 for value in frame_means if value >= frame_threshold)
    mean = float(np.mean(confidence[finite]))
    if not math.isfinite(mean):
        model_confidence = None
    else:
        model_confidence = round(max(0.0, min(1.0, mean)), 4)

    return {
        "modelConfidence": model_confidence,
        "framesUsed": frames_used,
        "framesTotal": frames_total,
    }


def summarize_pose_coordinates(
    keypoints,
    *,
    frame_threshold: float,
    keypoint_threshold: float,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> list[dict[str, float | str]]:
    """Average source-frame coordinates over confident pose frames.

    Stored keypoints are pixels. When the frame size is known, x and y in the
    summary are fractions of that frame, from 0 to 1. They are not letterboxed.
    """

    array = np.asarray(keypoints, dtype=np.float32)
    if array.ndim != 3 or array.shape[-1] < 3:
        raise ValueError("keypoints must have shape (frames, points, 3).")
    if array.shape[1] != len(MODEL_OUTPUT_KEYPOINTS):
        raise ValueError(f"keypoints must contain {len(MODEL_OUTPUT_KEYPOINTS)} points.")
    if not 0.0 <= frame_threshold <= 1.0:
        raise ValueError("frame_threshold must be between 0 and 1.")
    if not 0.0 <= keypoint_threshold <= 1.0:
        raise ValueError("keypoint_threshold must be between 0 and 1.")
    if (frame_width is None) != (frame_height is None):
        raise ValueError("frame_width and frame_height must be provided together.")

    confidences = array[:, :, 2]
    usable_frames = []
    for frame, frame_confidence in zip(array, confidences):
        finite = np.isfinite(frame_confidence)
        if not np.any(finite) or float(np.mean(frame_confidence[finite])) < frame_threshold:
            continue
        usable_frames.append(frame)

    if not usable_frames:
        return []

    usable = np.stack(usable_frames)
    if frame_width and frame_height and frame_width > 0 and frame_height > 0:
        usable = usable.copy()
        usable[:, :, 0] = usable[:, :, 0] / float(frame_width)
        usable[:, :, 1] = usable[:, :, 1] / float(frame_height)

    result: list[dict[str, float | str]] = []
    for index, name in enumerate(MODEL_OUTPUT_KEYPOINTS):
        points = usable[:, index, :]
        valid = (
            np.isfinite(points).all(axis=1)
            & (points[:, 2] >= keypoint_threshold)
            & (points[:, 0] >= 0.0)
            & (points[:, 0] <= 1.0 if frame_width else True)
            & (points[:, 1] >= 0.0)
            & (points[:, 1] <= 1.0 if frame_height else True)
        )
        if frame_width is None:
            valid = np.isfinite(points).all(axis=1) & (points[:, 2] >= keypoint_threshold)
        if not np.any(valid):
            continue

        result.append({
            "name": name,
            "x": round(float(np.mean(points[valid, 0])), 4),
            "y": round(float(np.mean(points[valid, 1])), 4),
            "confidence": round(float(np.mean(points[valid, 2])), 4),
        })

    return result


def pose_is_trusted(summary: dict, *, minimum: float) -> bool:
    """True when the pose mean is high enough and at least one frame was used."""

    confidence = summary.get("modelConfidence")
    frames_used = summary.get("framesUsed")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        return False
    if not isinstance(frames_used, int) or isinstance(frames_used, bool):
        return False
    return confidence >= minimum and frames_used > 0
