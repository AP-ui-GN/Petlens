"""Stride measurements from an AP-10K keypoint array.

NumPy and SciPy only. This module does not import a pose model.

Several cutoffs are placeholders to calibrate on labeled clips:
peak prominence, the 0.4 s minimum spacing, the 0.4–2.5 s stride window,
and the 0.35–0.65 anti-phase band. They are named below and listed in
docs/GAIT_METRICS.md.

A missing measurement is None. It is never 0 and never 1.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.signal import find_peaks, medfilt, savgol_filter

from .pose_backend import (
    LEFT_BACK_PAW,
    LEFT_FRONT_PAW,
    LEFT_HIP,
    LEFT_SHOULDER,
    NECK,
    NOSE,
    RIGHT_BACK_PAW,
    RIGHT_FRONT_PAW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    ROOT_OF_TAIL,
)

KEYPOINT_MIN_SCORE = 0.3
MIN_SIDE_ON_RATIO = 0.6
MIN_STRIDES = 3
# Placeholders. Calibrate these on labeled clips before treating them as fixed.
PEAK_PROMINENCE_BODY_LENGTHS = 0.15
MIN_PEAK_SPACING_SECONDS = 0.4
STRIDE_INTERVAL_MIN_SECONDS = 0.4
STRIDE_INTERVAL_MAX_SECONDS = 2.5
ANTI_PHASE_LOW = 0.35
ANTI_PHASE_HIGH = 0.65
MIN_VALID_FRAME_SHARE = 0.6
MAX_INTERPOLATED_GAP = 3
SMOOTH_WINDOW = 5
SMOOTH_POLYORDER = 2
MIN_DOG_FRAMES_SHARE = 0.6

SIDE_ON_REASON = "Film from the side with the whole dog in frame."
IN_PHASE_REASON = "Left and right legs could not be told apart."
FRONT_STRIDE_REASON = "Not enough strides were visible on the front legs."
REAR_STRIDE_REASON = "Not enough strides were visible on the rear legs."
FRONT_VISIBLE_REASON = "The front paws were not visible in enough of the clip."
REAR_VISIBLE_REASON = "The rear paws were not visible in enough of the clip."

PAW_INDEX = {
    "frontLeft": LEFT_FRONT_PAW,
    "frontRight": RIGHT_FRONT_PAW,
    "rearLeft": LEFT_BACK_PAW,
    "rearRight": RIGHT_BACK_PAW,
}
FRONT_PAWS = ("frontLeft", "frontRight")
REAR_PAWS = ("rearLeft", "rearRight")


def _empty_result(reasons: list[str], *, side_on: bool | None) -> dict:
    paws = {
        name: {"strideCount": None, "excursion": None}
        for name in PAW_INDEX
    }
    return {
        "view": {"sideOn": side_on, "reason": None if side_on else SIDE_ON_REASON},
        "strides": paws,
        "limbSymmetry": {"front": None, "rear": None},
        "strideSymmetry": None,
        "asymmetryPercent": None,
        "strideLengthBodyLengths": {"front": None, "rear": None},
        "cadenceStridesPerMinute": None,
        "strideTimeCv": None,
        "headVerticalOscillation": None,
        "pelvisVerticalOscillation": None,
        "headBobAsymmetry": None,
        "pelvisAsymmetry": None,
        "symmetryReliable": False,
        "notMeasuredReasons": reasons,
        "bodyLengthPixels": None,
    }


def _interpolate_short_gaps(series: np.ndarray, max_gap: int = MAX_INTERPOLATED_GAP) -> np.ndarray:
    filled = np.array(series, dtype=np.float64, copy=True)
    count = len(filled)
    index = 0
    while index < count:
        if np.isfinite(filled[index]):
            index += 1
            continue
        end = index
        while end < count and not np.isfinite(filled[end]):
            end += 1
        if end - index <= max_gap and index > 0 and end < count:
            filled[index:end] = np.interp(
                np.arange(index, end),
                [index - 1, end],
                [filled[index - 1], filled[end]],
            )
        index = end
    return filled


def _smooth_segments(series: np.ndarray) -> np.ndarray:
    smoothed = np.array(series, dtype=np.float64, copy=True)
    count = len(smoothed)
    index = 0
    while index < count:
        if not np.isfinite(smoothed[index]):
            index += 1
            continue
        end = index
        while end < count and np.isfinite(smoothed[end]):
            end += 1
        if end - index >= SMOOTH_WINDOW:
            smoothed[index:end] = savgol_filter(
                smoothed[index:end],
                SMOOTH_WINDOW,
                SMOOTH_POLYORDER,
                mode="interp",
            )
        index = end
    return smoothed


def _prepare_points(keypoints: np.ndarray) -> np.ndarray:
    points = np.array(keypoints[:, :, :2], dtype=np.float64, copy=True)
    scores = np.asarray(keypoints[:, :, 2], dtype=np.float64)
    points[scores < KEYPOINT_MIN_SCORE] = np.nan
    points[~np.isfinite(scores)] = np.nan
    for joint in range(points.shape[1]):
        for axis in range(2):
            filled = _interpolate_short_gaps(points[:, joint, axis])
            points[:, joint, axis] = _smooth_segments(filled)
    return points


def _median_axis(points: np.ndarray) -> tuple[np.ndarray, float | None]:
    neck = points[:, NECK, :]
    tail = points[:, ROOT_OF_TAIL, :]
    delta = neck - tail
    valid = np.isfinite(delta).all(axis=1)
    lengths = np.linalg.norm(delta[valid], axis=1) if np.any(valid) else np.array([])
    if lengths.size == 0 or not np.isfinite(np.median(lengths)) or float(np.median(lengths)) <= 1.0:
        return np.full_like(delta, np.nan), None
    body_length = float(np.median(lengths))
    forward = np.full_like(delta, np.nan)
    forward[valid] = delta[valid] / np.linalg.norm(delta[valid], axis=1)[:, None]
    if int(np.count_nonzero(valid)) >= SMOOTH_WINDOW:
        for axis in range(2):
            series = forward[:, axis].copy()
            finite = np.isfinite(series)
            # medfilt turns NaN into a number. Filter only the finite run by
            # filling edges with the nearest finite value, then restore gaps.
            if np.count_nonzero(finite) >= SMOOTH_WINDOW:
                filled = series.copy()
                good = np.flatnonzero(finite)
                filled[: good[0]] = series[good[0]]
                filled[good[-1] + 1 :] = series[good[-1]]
                for left, right in zip(good[:-1], good[1:]):
                    if right > left + 1:
                        filled[left:right] = series[left]
                filtered = medfilt(filled, kernel_size=SMOOTH_WINDOW)
                series[finite] = filtered[finite]
                forward[:, axis] = series
        norms = np.linalg.norm(forward, axis=1)
        usable = np.isfinite(norms) & (norms > 1e-6)
        forward[usable] = forward[usable] / norms[usable, None]
    return forward, body_length


def _side_on(points: np.ndarray, boxes: list | None) -> tuple[bool, float | None]:
    neck = points[:, NECK, :]
    tail = points[:, ROOT_OF_TAIL, :]
    ratios = []
    for index in range(len(points)):
        if not (np.isfinite(neck[index]).all() and np.isfinite(tail[index]).all()):
            continue
        if not boxes or index >= len(boxes) or boxes[index] is None:
            continue
        height = float(boxes[index][3])
        if not math.isfinite(height) or height <= 1.0:
            continue
        along_x = abs(float(neck[index, 0] - tail[index, 0]))
        ratios.append(along_x / height)
    if not ratios:
        return False, None
    ratio = float(np.median(ratios))
    return ratio >= MIN_SIDE_ON_RATIO, ratio


def _reference(points: np.ndarray, left: int, right: int) -> np.ndarray:
    pair = np.stack([points[:, left, :], points[:, right, :]], axis=1)
    with np.errstate(invalid="ignore"):
        return np.nanmean(pair, axis=1)


def _paw_signal(points: np.ndarray, paw: int, reference: np.ndarray, forward: np.ndarray, body_length: float) -> np.ndarray:
    delta = points[:, paw, :] - reference
    valid = np.isfinite(delta).all(axis=1) & np.isfinite(forward).all(axis=1)
    signal = np.full(len(points), np.nan)
    signal[valid] = np.sum(delta[valid] * forward[valid], axis=1) / body_length
    return signal


def _timestamps(count: int, timestamps: np.ndarray | None, fps: float | None) -> np.ndarray | None:
    if timestamps is not None:
        stamps = np.asarray(timestamps, dtype=np.float64)
        if stamps.shape[0] == count and np.isfinite(stamps).all():
            return stamps
    if fps is not None and fps > 0:
        return np.arange(count, dtype=np.float64) / float(fps)
    return None


def _sample_step(stamps: np.ndarray) -> float | None:
    if len(stamps) < 2:
        return None
    diffs = np.diff(stamps)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if diffs.size == 0:
        return None
    return float(np.median(diffs))


def _peak_intervals(signal: np.ndarray, stamps: np.ndarray, step: float) -> tuple[list[float], list[float]]:
    finite = np.isfinite(signal)
    if np.count_nonzero(finite) < 5:
        return [], []
    filled = signal.copy()
    # find_peaks cannot see NaN. Gaps stay out by using a very low sentinel
    # only where the point was missing, then rejecting peaks on those samples.
    filled[~finite] = np.nanmin(signal[finite]) - 1.0
    distance = max(1, int(round(MIN_PEAK_SPACING_SECONDS / step)))
    peaks, _ = find_peaks(
        filled,
        prominence=PEAK_PROMINENCE_BODY_LENGTHS,
        distance=distance,
    )
    peaks = [int(peak) for peak in peaks if finite[int(peak)]]
    intervals: list[float] = []
    excursions: list[float] = []
    for left, right in zip(peaks, peaks[1:]):
        elapsed = float(stamps[right] - stamps[left])
        if not (STRIDE_INTERVAL_MIN_SECONDS <= elapsed <= STRIDE_INTERVAL_MAX_SECONDS):
            continue
        between = signal[left : right + 1]
        if not np.isfinite(between).all():
            continue
        trough = float(np.min(between))
        peak_height = max(float(signal[left]), float(signal[right]))
        intervals.append(elapsed)
        excursions.append(peak_height - trough)
    return intervals, excursions


def _symmetry(left_excursion: float | None, right_excursion: float | None) -> tuple[float | None, float | None]:
    if left_excursion is None or right_excursion is None:
        return None, None
    total = left_excursion + right_excursion
    if total <= 0:
        return None, None
    score = 1.0 - abs(left_excursion - right_excursion) / total
    score = float(np.clip(score, 0.0, 1.0))
    return score, (1.0 - score) * 100.0


def _phase_is_alternating(left: np.ndarray, right: np.ndarray, period_seconds: float, step: float) -> bool:
    valid = np.isfinite(left) & np.isfinite(right)
    if np.count_nonzero(valid) < 8 or period_seconds <= 0 or step <= 0:
        return False
    period = max(2, int(round(period_seconds / step)))
    a = np.where(valid, left, 0.0)
    b = np.where(valid, right, 0.0)
    a = a - np.mean(a[valid])
    b = b - np.mean(b[valid])
    correlation = np.correlate(a, b, mode="full")
    lags = np.arange(-len(b) + 1, len(a))
    window = (lags >= 0) & (lags < period)
    if not np.any(window):
        return False
    lag = int(lags[window][int(np.argmax(correlation[window]))])
    phase = lag / period
    return ANTI_PHASE_LOW <= phase <= ANTI_PHASE_HIGH


def _pair(
    name_left: str,
    name_right: str,
    signals: dict[str, np.ndarray],
    intervals: dict[str, list[float]],
    excursions: dict[str, list[float]],
    stamps: np.ndarray,
    step: float,
) -> tuple[float | None, float | None, float | None, str | None]:
    left_signal = signals[name_left]
    right_signal = signals[name_right]
    both = np.isfinite(left_signal) & np.isfinite(right_signal)
    if both.size == 0 or float(np.mean(both)) < MIN_VALID_FRAME_SHARE:
        reason = FRONT_VISIBLE_REASON if name_left.startswith("front") else REAR_VISIBLE_REASON
        return None, None, None, reason
    if len(intervals[name_left]) < MIN_STRIDES or len(intervals[name_right]) < MIN_STRIDES:
        reason = FRONT_STRIDE_REASON if name_left.startswith("front") else REAR_STRIDE_REASON
        return None, None, None, reason
    left_excursion = float(np.median(excursions[name_left]))
    right_excursion = float(np.median(excursions[name_right]))
    period = float(np.median(intervals[name_left] + intervals[name_right]))
    if not _phase_is_alternating(left_signal, right_signal, period, step):
        return None, None, None, IN_PHASE_REASON
    symmetry, asymmetry = _symmetry(left_excursion, right_excursion)
    length = (left_excursion + right_excursion) / 2.0
    return symmetry, asymmetry, length, None


def _moving_average(series: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return series.copy()
    kernel = np.ones(window) / window
    valid = np.isfinite(series).astype(np.float64)
    filled = np.where(np.isfinite(series), series, 0.0)
    numerator = np.convolve(filled, kernel, mode="same")
    denominator = np.convolve(valid, kernel, mode="same")
    averaged = np.full_like(series, np.nan)
    keep = denominator >= 0.5
    averaged[keep] = numerator[keep] / denominator[keep]
    return averaged


def _vertical_metrics(series: np.ndarray, body_length: float, step: float) -> tuple[float | None, float | None]:
    finite = np.isfinite(series)
    if np.count_nonzero(finite) < SMOOTH_WINDOW or step is None or step <= 0:
        return None, None
    window = max(1, int(round(1.0 / step)))
    centered = series / body_length
    residual = centered - _moving_average(centered, window)
    usable = residual[np.isfinite(residual)]
    if usable.size < 5:
        return None, None
    oscillation = float(np.std(usable))
    filled = residual.copy()
    filled[~np.isfinite(filled)] = np.nanmin(usable) - 1.0
    distance = max(1, int(round(0.25 / step)))
    peaks, properties = find_peaks(filled, distance=distance, prominence=0.01)
    kept = [index for index, peak in enumerate(peaks) if np.isfinite(residual[int(peak)])]
    if len(kept) < 6:
        return oscillation, None
    # Prominence is how far each downward dip stands out from its neighbors.
    # Image y grows downward, so a dip is a peak in this signal.
    amplitudes = np.asarray(properties["prominences"], dtype=np.float64)[kept]
    if amplitudes.size < 6:
        return oscillation, None
    odd = amplitudes[0::2]
    even = amplitudes[1::2]
    pairs = min(len(odd), len(even))
    if pairs == 0:
        return oscillation, None
    odd = odd[:pairs]
    even = even[:pairs]
    mean_amplitude = float(np.mean(np.concatenate([odd, even])))
    if mean_amplitude <= 0:
        return oscillation, None
    asymmetry = float(np.mean(np.abs(odd - even)) / mean_amplitude)
    return oscillation, asymmetry


def foot_strike_frames(
    keypoints: np.ndarray,
    *,
    timestamps: np.ndarray | None = None,
    boxes: list | None = None,
    fps: float | None = None,
) -> dict[str, list[int]]:
    """Frame indexes of pawX peaks. These are the stride events drawn in debug video.

    They are not a separate ground-contact detector.
    """

    array = np.asarray(keypoints, dtype=np.float64)
    points = _prepare_points(array)
    forward, body_length = _median_axis(points)
    stamps = _timestamps(len(points), timestamps, fps)
    step = None if stamps is None else _sample_step(stamps)
    empty = {name: [] for name in PAW_INDEX}
    if body_length is None or stamps is None or step is None:
        return empty
    if not _side_on(points, boxes)[0]:
        return empty
    front_reference = _reference(points, LEFT_SHOULDER, RIGHT_SHOULDER)
    rear_reference = _reference(points, LEFT_HIP, RIGHT_HIP)
    signals = {
        "frontLeft": _paw_signal(points, LEFT_FRONT_PAW, front_reference, forward, body_length),
        "frontRight": _paw_signal(points, RIGHT_FRONT_PAW, front_reference, forward, body_length),
        "rearLeft": _paw_signal(points, LEFT_BACK_PAW, rear_reference, forward, body_length),
        "rearRight": _paw_signal(points, RIGHT_BACK_PAW, rear_reference, forward, body_length),
    }
    strikes: dict[str, list[int]] = {}
    for name, signal in signals.items():
        finite = np.isfinite(signal)
        if np.count_nonzero(finite) < 5:
            strikes[name] = []
            continue
        filled = signal.copy()
        filled[~finite] = np.nanmin(signal[finite]) - 1.0
        distance = max(1, int(round(MIN_PEAK_SPACING_SECONDS / step)))
        peaks, _ = find_peaks(filled, prominence=PEAK_PROMINENCE_BODY_LENGTHS, distance=distance)
        strikes[name] = [int(peak) for peak in peaks if finite[int(peak)]]
    return strikes


def compute_gait_metrics(
    keypoints: np.ndarray,
    *,
    timestamps: np.ndarray | None = None,
    boxes: list | None = None,
    fps: float | None = None,
    dog_frames_share: float | None = None,
) -> dict:
    """Measure one clip from ``(frames, 17, 3)`` AP-10K points.

    Coordinates are ``(x_px, y_px, score)``. ``boxes`` are COCO
    ``(x, y, w, h)`` or None per frame.
    """

    array = np.asarray(keypoints, dtype=np.float64)
    if array.ndim != 3 or array.shape[1:] != (17, 3):
        raise ValueError(f"keypoints must have shape (frames, 17, 3); received {array.shape}.")
    if array.shape[0] == 0:
        raise ValueError("At least one frame is required.")

    points = _prepare_points(array)
    forward, body_length = _median_axis(points)
    reasons: list[str] = []
    if body_length is None:
        reasons.append("The neck and the base of the tail were not visible often enough to scale the walk.")
        result = _empty_result(reasons, side_on=None)
        return result

    side_on, _ratio = _side_on(points, boxes)
    result = _empty_result([], side_on=side_on)
    result["bodyLengthPixels"] = round(body_length, 3)

    stamps = _timestamps(len(points), timestamps, fps)
    step = None if stamps is None else _sample_step(stamps)
    head = points[:, NOSE, 1]
    pelvis = points[:, ROOT_OF_TAIL, 1]
    if step is not None:
        head_osc, head_asym = _vertical_metrics(head, body_length, step)
        pelvis_osc, pelvis_asym = _vertical_metrics(pelvis, body_length, step)
        result["headVerticalOscillation"] = None if head_osc is None else round(head_osc, 4)
        result["pelvisVerticalOscillation"] = None if pelvis_osc is None else round(pelvis_osc, 4)
        result["headBobAsymmetry"] = None if head_asym is None else round(head_asym, 4)
        result["pelvisAsymmetry"] = None if pelvis_asym is None else round(pelvis_asym, 4)
    else:
        reasons.append("The clip has no usable timestamps, so timing was not measured.")

    if not side_on:
        reasons.append(SIDE_ON_REASON)
        result["notMeasuredReasons"] = reasons
        return result
    if stamps is None or step is None:
        result["notMeasuredReasons"] = reasons
        return result

    front_reference = _reference(points, LEFT_SHOULDER, RIGHT_SHOULDER)
    rear_reference = _reference(points, LEFT_HIP, RIGHT_HIP)
    signals = {
        "frontLeft": _paw_signal(points, LEFT_FRONT_PAW, front_reference, forward, body_length),
        "frontRight": _paw_signal(points, RIGHT_FRONT_PAW, front_reference, forward, body_length),
        "rearLeft": _paw_signal(points, LEFT_BACK_PAW, rear_reference, forward, body_length),
        "rearRight": _paw_signal(points, RIGHT_BACK_PAW, rear_reference, forward, body_length),
    }
    intervals: dict[str, list[float]] = {}
    excursions: dict[str, list[float]] = {}
    for name, signal in signals.items():
        kept, sizes = _peak_intervals(signal, stamps, step)
        intervals[name] = kept
        excursions[name] = sizes
        result["strides"][name] = {
            "strideCount": len(kept) if kept else None,
            "excursion": None if not sizes else round(float(np.median(sizes)), 4),
        }

    front_s, front_a, front_len, front_reason = _pair(
        "frontLeft", "frontRight", signals, intervals, excursions, stamps, step
    )
    rear_s, rear_a, rear_len, rear_reason = _pair(
        "rearLeft", "rearRight", signals, intervals, excursions, stamps, step
    )
    if front_reason:
        reasons.append(front_reason)
    if rear_reason and rear_reason != front_reason:
        reasons.append(rear_reason)
    result["limbSymmetry"] = {
        "front": None if front_s is None else round(front_s, 4),
        "rear": None if rear_s is None else round(rear_s, 4),
    }
    result["strideLengthBodyLengths"] = {
        "front": None if front_len is None else round(front_len, 4),
        "rear": None if rear_len is None else round(rear_len, 4),
    }
    measured = [value for value in (front_s, rear_s) if value is not None]
    if measured:
        worst = min(measured)
        result["strideSymmetry"] = round(worst, 4)
        result["asymmetryPercent"] = round((1.0 - worst) * 100.0, 3)
        used_names = []
        if front_s is not None:
            used_names.extend(FRONT_PAWS)
        if rear_s is not None:
            used_names.extend(REAR_PAWS)
        pooled = [value for name in used_names for value in intervals[name]]
        if pooled:
            median_interval = float(np.median(pooled))
            if median_interval > 0:
                result["cadenceStridesPerMinute"] = round(60.0 / median_interval, 2)
            if len(pooled) >= 2 and float(np.mean(pooled)) > 0:
                result["strideTimeCv"] = round(float(np.std(pooled) / np.mean(pooled)), 4)
    share_ok = dog_frames_share is None or dog_frames_share >= MIN_DOG_FRAMES_SHARE
    if dog_frames_share is not None and dog_frames_share < MIN_DOG_FRAMES_SHARE:
        reasons.append("The dog was not in enough of the frames to trust a symmetry score.")
    result["symmetryReliable"] = bool(side_on and share_ok and measured)
    result["notMeasuredReasons"] = reasons
    return result
