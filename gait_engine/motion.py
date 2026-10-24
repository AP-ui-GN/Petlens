"""Frame-to-frame motion signal for a video clip.

This module only needs OpenCV, so it runs when torch or the pose weights are
unavailable. It produces the movement time series that the feature layer turns
into measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

# Frames are downscaled before differencing. Small frames are enough for a
# whole-body movement signal and keep long clips fast.
ANALYSIS_WIDTH = 320
MOTION_TRACE_MAX_POINTS = 120


@dataclass(frozen=True)
class MotionSignal:
    """Per-frame movement measured from picture change alone."""

    fps: float
    frames_read: int
    duration_seconds: float
    # One value per frame pair, so this is `frames_read - 1` long. Each value is
    # the mean absolute grayscale change between two frames, scaled to 0-1.
    frame_motion: list[float]
    # Original pixel size of the first frame. 0 means the size was not read.
    width: int = 0
    height: int = 0
    # Mean brightness of the analysis frames, 0-1. None means it was not measured.
    brightness: float | None = None


def _to_analysis_frame(frame_bgr):
    """Downscale and blur a frame so small camera noise is not read as motion."""

    height, width = frame_bgr.shape[:2]
    if width > ANALYSIS_WIDTH:
        scale = ANALYSIS_WIDTH / width
        frame_bgr = cv2.resize(frame_bgr, (ANALYSIS_WIDTH, max(1, round(height * scale))))

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (5, 5), 0)


def compact_motion_trace(
    frame_motion: list[float],
    fps: float,
    *,
    max_points: int = MOTION_TRACE_MAX_POINTS,
) -> dict[str, object]:
    """Downsample frame-pair motion into timestamped means for visualization."""

    if max_points < 1:
        raise ValueError("max_points must be positive.")
    sample_count = len(frame_motion)
    if sample_count == 0:
        return {"sampleCount": 0, "points": []}
    if not fps or not 0 < fps <= 240:
        return {"sampleCount": sample_count, "points": []}

    point_count = min(sample_count, max_points)
    points: list[dict[str, float]] = []
    for point_index in range(point_count):
        start = point_index * sample_count // point_count
        end = (point_index + 1) * sample_count // point_count
        values = frame_motion[start:end]
        if not values:
            continue
        points.append(
            {
                "timeSeconds": round((start + end) / (2.0 * fps), 4),
                "movement": round(sum(values) / len(values), 6),
            }
        )
    return {"sampleCount": sample_count, "points": points}


def read_motion_signal(video_path: str | Path, *, max_frames: int = 600) -> MotionSignal:
    """Read a clip and return its frame-to-frame motion signal.

    Raises:
        FileNotFoundError: the path is not a file.
        ValueError: OpenCV could not open or decode the clip.
    """

    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")
    if max_frames < 2:
        raise ValueError("max_frames must be at least 2.")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(
            "This file could not be opened as a video. Try exporting it as MP4."
        )

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if fps <= 0 or fps != fps or fps > 240:  # `fps != fps` catches NaN
        fps = 0.0

    frame_motion: list[float] = []
    frames_read = 0
    previous = None
    width = 0
    height = 0
    brightness_sum = 0.0

    try:
        while frames_read < max_frames:
            success, frame = capture.read()
            if not success:
                break

            if frames_read == 0:
                height, width = frame.shape[:2]

            current = _to_analysis_frame(frame)
            brightness_sum += float(current.mean()) / 255.0
            if previous is not None:
                difference = cv2.absdiff(current, previous)
                frame_motion.append(float(difference.mean()) / 255.0)

            previous = current
            frames_read += 1
    finally:
        capture.release()

    if frames_read == 0:
        raise ValueError(
            "No video frames could be read from this file. It may be corrupted."
        )

    duration_seconds = round(frames_read / fps, 3) if fps else 0.0

    return MotionSignal(
        fps=round(fps, 3),
        frames_read=frames_read,
        duration_seconds=duration_seconds,
        frame_motion=frame_motion,
        width=int(width),
        height=int(height),
        brightness=round(brightness_sum / frames_read, 4) if frames_read else None,
    )
