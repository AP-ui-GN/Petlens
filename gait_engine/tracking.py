"""Associate dog boxes across frames.

This module does not load a model, read a video, or copy pixels. A frame
without an accepted box stays empty. The previous box is never written
forward to fill a gap.

``MAX_CONTINUOUS_GAP`` is counted in frames. A later box can stay on the same
segment only when the gap is still inside that limit and the overlap clears
``MIN_TRACK_IOU``. A longer gap starts a new segment. Two boxes that both
fit the open segment, and two boxes when no segment is open, are
``ambiguous`` and produce no box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

Box = tuple[float, float, float, float]

# A box with no real overlap is a different animal, not the dog we were following.
MIN_TRACK_IOU = 0.1

# Frames since the last accepted box. Detector samples are 5 frames apart,
# so 5 still continues a segment. 6 or more does not.
MAX_CONTINUOUS_GAP = 5

# When two boxes both clear the overlap floor, the leader must win by this
# much. A smaller lead is not an identity.
AMBIGUITY_MARGIN = 0.15

ACCEPTED_STATES = frozenset({"tracked", "new_segment"})


@dataclass(frozen=True)
class TrackDecision:
    """One frame of the tracker. ``box`` is None unless a real observation was accepted."""

    frame_index: int
    box: Box | None
    segment_id: int | None
    state: str


def box_iou(a: Box, b: Box) -> float:
    """Intersection over union for COCO ``(x, y, width, height)`` boxes."""

    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    union = aw * ah + bw * bh - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _center_distance(box: Box, width: int, height: int) -> float:
    x, y, w, h = box
    cx, cy = x + w / 2.0, y + h / 2.0
    return ((cx - width / 2.0) ** 2 + (cy - height / 2.0) ** 2) ** 0.5


def choose_initial_dog(
    boxes: Sequence[Box],
    width: int,
    height: int,
) -> Box | None:
    """Largest dog box, then the one closest to the image center."""

    if not boxes:
        return None
    return min(boxes, key=lambda box: (-(box[2] * box[3]), _center_distance(box, width, height)))


def choose_tracked_dog(
    boxes: Sequence[Box],
    previous: Box | None,
    width: int,
    height: int,
) -> Box | None:
    """One frame of overlap. A disjoint box is rejected.

    The first frame, with no previous box, uses size and center. Later frames
    keep the best overlap only when it clears ``MIN_TRACK_IOU``. Sequence
    identity, gaps, and ambiguous pairs are ``associate_tracks``.
    """

    if previous is None:
        return choose_initial_dog(boxes, width, height)
    if not boxes:
        return None
    best = max(boxes, key=lambda box: box_iou(box, previous))
    if box_iou(best, previous) < MIN_TRACK_IOU:
        return None
    return best


def _matching(boxes: Sequence[Box], previous: Box, min_iou: float) -> list[tuple[float, Box]]:
    scored = sorted(((box_iou(box, previous), box) for box in boxes), key=lambda item: item[0], reverse=True)
    return [(score, box) for score, box in scored if score >= min_iou]


def associate_tracks(
    frames: Sequence[Sequence[Box]],
    *,
    min_iou: float = MIN_TRACK_IOU,
    max_continuous_gap: int = MAX_CONTINUOUS_GAP,
    ambiguity_margin: float = AMBIGUITY_MARGIN,
) -> list[TrackDecision]:
    """Walk synthetic or detected boxes in time and return one decision per frame.

    ``frames[i]`` is the dog boxes seen on that frame. An empty list is a
    frame with no dog box. Coordinates from an earlier frame are not reused.
    """

    if max_continuous_gap < 1:
        raise ValueError("max_continuous_gap must be at least 1")

    decisions: list[TrackDecision] = []
    segment_id = 0
    last_box: Box | None = None
    last_frame: int | None = None

    for index, raw_boxes in enumerate(frames):
        boxes = list(raw_boxes)
        gap = None if last_frame is None else index - last_frame
        continuous = last_box is not None and gap is not None and gap <= max_continuous_gap

        if continuous:
            assert last_box is not None
            matched = _matching(boxes, last_box, min_iou)
            if len(matched) >= 2 and matched[0][0] - matched[1][0] < ambiguity_margin:
                decisions.append(TrackDecision(index, None, segment_id, "ambiguous"))
                continue
            if matched:
                chosen = matched[0][1]
                decisions.append(TrackDecision(index, chosen, segment_id, "tracked"))
                last_box = chosen
                last_frame = index
                continue
            decisions.append(TrackDecision(index, None, segment_id, "missing"))
            continue

        last_box = None
        last_frame = None
        if not boxes:
            decisions.append(TrackDecision(index, None, None, "no_dog"))
            continue
        if len(boxes) == 1:
            segment_id += 1
            chosen = boxes[0]
            decisions.append(TrackDecision(index, chosen, segment_id, "new_segment"))
            last_box = chosen
            last_frame = index
            continue
        decisions.append(TrackDecision(index, None, None, "ambiguous"))

    return decisions
