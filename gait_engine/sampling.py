"""Choose the frames a pose model actually sees.

Container timestamps come from ``CAP_PROP_POS_MSEC`` when that clock is
strictly increasing. A missing or backwards reading stays NaN. It is not
replaced with ``index / fps`` inside an otherwise real clock, and a time gap
is not filled with a "stopped" sample. ``index / fps`` is used only when the
file has no usable container clock, and that series is an estimate.
The clip is resampled to ``TARGET_ANALYSIS_FPS``. A clip longer than
``MAX_ANALYZED_SECONDS`` keeps the 20-second window with the highest OpenCV
motion coverage. Frames are not taken as "the first 120".

Phone rotation is applied only when the container reports an orientation and
OpenCV is not already rotating the decoded frame. This was not checked on a
real phone file in this environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .features import MOTION_FLOOR
from .motion import ANALYSIS_WIDTH, _to_analysis_frame

TARGET_ANALYSIS_FPS = 15
MAX_ANALYZED_SECONDS = 20
DETECT_EVERY_N_FRAMES = 5


@dataclass(frozen=True)
class SampledFrame:
    """One frame chosen for pose, in source pixels after rotation."""

    image_bgr: np.ndarray
    timestamp_seconds: float
    width: int
    height: int
    # Motion against the previous decoded frame, 0-1. None on the first frame.
    motion: float | None
    # "container" is observed. "frame-index-estimate" is index/fps for a file
    # with no usable container clock. "unmeasured" means neither clock exists.
    timestamp_source: str = "container"


def _orientation_degrees(capture: cv2.VideoCapture) -> int:
    """Return 0, 90, 180, or 270 from container metadata. 0 when unknown."""

    prop = getattr(cv2, "CAP_PROP_ORIENTATION_META", None)
    if prop is None:
        return 0
    raw = float(capture.get(prop))
    if not np.isfinite(raw):
        return 0
    quarter = int(round(raw / 90.0)) % 4
    return quarter * 90


def _auto_rotation_enabled(capture: cv2.VideoCapture) -> bool:
    prop = getattr(cv2, "CAP_PROP_ORIENTATION_AUTO", None)
    if prop is None:
        return False
    return float(capture.get(prop)) != 0.0


def apply_rotation(frame_bgr: np.ndarray, degrees: int) -> np.ndarray:
    """Rotate a decoded frame clockwise by a container orientation."""

    if degrees == 90:
        return cv2.rotate(frame_bgr, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(frame_bgr, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(frame_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame_bgr


def assemble_timestamps(reported_seconds: list[float], fps: float) -> tuple[np.ndarray, str]:
    """Separate an observed container clock from an index/fps estimate.

    A usable container reading is finite, not negative, and strictly later
    than the previous observed time. The first reading may be 0. A later
    missing, non-finite, or non-increasing reading stays NaN. Those gaps are
    not filled, and they are not evidence that the dog stopped.

    ``index / fps`` is returned only when the file has no increasing container
    clock. That array is an estimate. When neither clock exists, every value
    is NaN.
    """

    count = len(reported_seconds)
    observed = np.full(count, np.nan, dtype=np.float64)
    previous: float | None = None
    for index, value in enumerate(reported_seconds):
        if not np.isfinite(value) or value < 0:
            continue
        if previous is not None and value <= previous:
            continue
        observed[index] = float(value)
        previous = float(value)

    finite = observed[np.isfinite(observed)]
    if finite.size >= 2 and float(finite[-1]) > float(finite[0]):
        return observed, "container"
    if fps > 0:
        return np.arange(count, dtype=np.float64) / float(fps), "frame-index-estimate"
    return np.full(count, np.nan, dtype=np.float64), "unmeasured"


def _best_window(timestamps: np.ndarray, motions: np.ndarray) -> tuple[float, float]:
    """Return (start, end) seconds of the busiest 20-second span.

    Frames with a NaN timestamp are left out of the window. A gap is not
    counted as a zero-motion sample.
    """

    finite_times = timestamps[np.isfinite(timestamps)]
    if finite_times.size == 0:
        return 0.0, 0.0
    start_time = float(finite_times[0])
    end_time = float(finite_times[-1])
    span = end_time - start_time
    if span <= MAX_ANALYZED_SECONDS or motions.size == 0:
        return start_time, end_time

    # Slide by one source frame. Coverage uses the pairs inside the window.
    best_start = start_time
    best_coverage = -1.0
    for origin in finite_times:
        window_end = float(origin) + MAX_ANALYZED_SECONDS
        if window_end > end_time + 1e-6:
            break
        # Pair i sits between frame i and frame i+1. Both times must be
        # observed and inside the window. A NaN end is a gap, not stillness.
        left = timestamps[:-1]
        right = timestamps[1:]
        inside = np.isfinite(left) & np.isfinite(right) & (left >= origin) & (right <= window_end)
        if not np.any(inside):
            coverage = 0.0
        else:
            coverage = float(np.mean(motions[inside] >= MOTION_FLOOR))
        if coverage > best_coverage:
            best_coverage = coverage
            best_start = float(origin)
    return best_start, best_start + MAX_ANALYZED_SECONDS


def _select_indices(timestamps: np.ndarray, window: tuple[float, float]) -> list[int]:
    """Pick frames about 1/TARGET_ANALYSIS_FPS apart inside the window."""

    start, end = window
    inside = np.flatnonzero((timestamps >= start) & (timestamps <= end + 1e-6))
    if inside.size == 0:
        return []
    chosen = [int(inside[0])]
    step = 1.0 / TARGET_ANALYSIS_FPS
    next_time = float(timestamps[chosen[0]]) + step
    for index in inside[1:]:
        stamp = float(timestamps[index])
        if stamp + 1e-6 < next_time:
            continue
        chosen.append(int(index))
        next_time = stamp + step
        if stamp >= end:
            break
    return chosen


def sample_video(video_path: str | Path) -> list[SampledFrame]:
    """Read a clip and return the frames the pose model should see.

    Raises:
        FileNotFoundError: the path is not a file.
        ValueError: OpenCV could not open the clip or it has no frames.
    """

    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(
            "This file could not be opened as a video. Try exporting it as MP4."
        )

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not np.isfinite(fps) or fps <= 0 or fps > 240:
        fps = 0.0
    degrees = 0 if _auto_rotation_enabled(capture) else _orientation_degrees(capture)

    reported_seconds: list[float] = []
    motions: list[float] = []
    previous = None
    index = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            frame = apply_rotation(frame, degrees)
            msec = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if np.isfinite(msec) and msec >= 0:
                reported_seconds.append(msec / 1000.0)
            else:
                reported_seconds.append(float("nan"))
            current = _to_analysis_frame(frame)
            if previous is not None:
                difference = cv2.absdiff(current, previous)
                motions.append(float(difference.mean()) / 255.0)
            previous = current
            index += 1
    finally:
        capture.release()

    if index == 0:
        raise ValueError(
            "No video frames could be read from this file. It may be corrupted."
        )

    stamps, timestamp_source = assemble_timestamps(reported_seconds, fps)

    motion = np.asarray(motions, dtype=np.float64)
    window = _best_window(stamps, motion)
    chosen = _select_indices(stamps, window)
    if not chosen:
        chosen = [0]

    wanted = set(chosen)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(
            "This file could not be opened as a video. Try exporting it as MP4."
        )
    samples: list[SampledFrame] = []
    previous = None
    index = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            frame = apply_rotation(frame, degrees)
            current = _to_analysis_frame(frame)
            motion_value = None
            if previous is not None:
                difference = cv2.absdiff(current, previous)
                motion_value = float(difference.mean()) / 255.0
            if index in wanted:
                height, width = frame.shape[:2]
                samples.append(
                    SampledFrame(
                        image_bgr=frame,
                        timestamp_seconds=(
                            float(stamps[index]) if np.isfinite(stamps[index]) else float("nan")
                        ),
                        width=int(width),
                        height=int(height),
                        motion=motion_value,
                        timestamp_source=timestamp_source,
                    )
                )
            previous = current
            index += 1
            if len(samples) == len(chosen):
                break
    finally:
        capture.release()

    return samples


def motion_coverage(samples: list[SampledFrame]) -> float:
    """Share of sampled frame pairs above the motion floor. 0 when unknown."""

    values = [sample.motion for sample in samples if sample.motion is not None]
    if not values:
        return 0.0
    return sum(1 for value in values if value >= MOTION_FLOOR) / len(values)


# Re-exported so callers do not need the private motion width.
__all__ = [
    "ANALYSIS_WIDTH",
    "MAX_ANALYZED_SECONDS",
    "SampledFrame",
    "TARGET_ANALYSIS_FPS",
    "apply_rotation",
    "sample_video",
]
