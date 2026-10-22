"""Movement features derived from the raw signals.

Everything here is a plain measurement. Nothing in this module decides whether a
value is good or bad; that judgement belongs to `wellness.py`.
"""

from __future__ import annotations

import statistics

# A frame pair below this mean change is treated as "no visible movement". It is
# roughly half a grayscale level out of 255, which sits above camera noise on the
# blurred, downscaled frames produced by motion.py.
MOTION_FLOOR = 0.002


def motion_statistics(frame_motion: list[float]) -> tuple[float, float, float]:
    """Return (mean, standard deviation, coverage) of a motion signal.

    Coverage is the share of frame pairs that showed movement above MOTION_FLOOR,
    so it answers "how much of the clip actually contained movement".
    """

    if not frame_motion:
        return 0.0, 0.0, 0.0

    mean = statistics.fmean(frame_motion)
    deviation = statistics.stdev(frame_motion) if len(frame_motion) > 1 else 0.0
    moving_frames = sum(1 for value in frame_motion if value >= MOTION_FLOOR)
    coverage = moving_frames / len(frame_motion)

    return round(mean, 6), round(deviation, 6), round(coverage, 4)


def movement_consistency(motion_mean: float, motion_std: float) -> float | None:
    """Score how steady the frame-to-frame movement was, from 0 to 1.

    A steady walk produces a similar amount of movement in every frame, so the
    coefficient of variation (standard deviation / mean) stays low. Returns None
    when the clip has too little movement to describe.
    """

    if motion_mean < MOTION_FLOOR:
        return None

    coefficient_of_variation = motion_std / motion_mean
    return round(max(0.0, min(1.0, 1.0 - coefficient_of_variation)), 6)
