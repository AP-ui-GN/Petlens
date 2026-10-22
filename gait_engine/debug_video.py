"""Draw a debug clip for the command line. The API does not call this."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .pose_backend import (
    KEYPOINT_MIN_SCORE,
    MODEL_OUTPUT_EDGES,
    MODEL_OUTPUT_KEYPOINTS,
    get_pose_backend,
)
from .sampling import sample_video


def write_debug_video(video_path: str | Path, output_path: str | Path) -> None:
    """Write skeleton, dog box, and stride-peak markers. Does not return video bytes."""

    frames = sample_video(video_path)
    if not frames:
        raise ValueError("No frames were sampled.")
    result = get_pose_backend().process(frames)
    # Stride peaks are defined on an AP-10K array. This head is COCO-17, so
    # those peaks are not drawn. Low-confidence joints stay as open circles.
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].image_bgr.shape[:2]
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        15,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"Could not write {output}")
    try:
        for index, frame in enumerate(frames):
            image = frame.image_bgr.copy()
            box = result.boxes[index]
            if box is not None:
                x, y, w, h = [int(round(value)) for value in box]
                cv2.rectangle(image, (x, y), (x + w, y + h), (40, 180, 60), 2)
            points = result.keypoints[index]
            for start, end in MODEL_OUTPUT_EDGES:
                if points[start, 2] < KEYPOINT_MIN_SCORE or points[end, 2] < KEYPOINT_MIN_SCORE:
                    continue
                if not np.isfinite(points[start, 0]) or not np.isfinite(points[end, 0]):
                    continue
                p1 = (int(round(points[start, 0])), int(round(points[start, 1])))
                p2 = (int(round(points[end, 0])), int(round(points[end, 1])))
                cv2.line(image, p1, p2, (30, 90, 200), 2)
        for name, point in zip(MODEL_OUTPUT_KEYPOINTS, points):
            if not np.isfinite(point[0]):
                continue
            center = (int(round(point[0])), int(round(point[1])))
            if float(point[2]) >= KEYPOINT_MIN_SCORE:
                cv2.circle(image, center, 3, (20, 20, 20), -1)
            else:
                cv2.circle(image, center, 5, (0, 0, 180), 1)
            cv2.putText(
                image,
                name,
                (center[0] + 3, center[1] - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                name,
                (center[0] + 3, center[1] - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )
        writer.write(image)
    finally:
        writer.release()
