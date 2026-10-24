"""Unit-agnostic paired symmetry indices with explicit missing-data behavior."""

from __future__ import annotations

import math


def symmetry_indices(
    left: float | None,
    right: float | None,
) -> tuple[float | None, float | None]:
    """Return signed SI and absolute SI for a non-negative paired measure.

    The sign is positive when the left value is larger. Inputs must use the
    same units; a missing, non-finite, negative, or zero-sum pair is unmeasured.
    """

    if left is None or right is None:
        return None, None
    left_value = float(left)
    right_value = float(right)
    if (
        not math.isfinite(left_value)
        or not math.isfinite(right_value)
        or left_value < 0
        or right_value < 0
    ):
        return None, None
    total = left_value + right_value
    if total <= 0:
        return None, None
    signed = 200.0 * (left_value - right_value) / total
    return signed, abs(signed)


def joint_angle_2d_degrees(
    first: tuple[float, float] | None,
    vertex: tuple[float, float] | None,
    last: tuple[float, float] | None,
) -> float | None:
    """Return a 2-D included angle in degrees, or None for invalid geometry."""

    if first is None or vertex is None or last is None:
        return None
    try:
        ax, ay = float(first[0]) - float(vertex[0]), float(first[1]) - float(vertex[1])
        bx, by = float(last[0]) - float(vertex[0]), float(last[1]) - float(vertex[1])
    except (IndexError, TypeError, ValueError):
        return None
    if not all(map(math.isfinite, (ax, ay, bx, by))):
        return None
    first_length = math.hypot(ax, ay)
    last_length = math.hypot(bx, by)
    if first_length <= 0 or last_length <= 0:
        return None
    cosine = (ax * bx + ay * by) / (first_length * last_length)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
