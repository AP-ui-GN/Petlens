"""Conservative, gap-aware recovery for experimental canine paw tracking.

Every usable run has independent identities. Never connect identities
across unavailable observations or imply anatomical left/right identity.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryRules:
    minimum_ambiguous_frames: int = 3
    minimum_clear_frames: int = 3


def propose_restarts(associated_frames, rules=RecoveryRules()):
    """Propose restart points after unavailable or unresolved observations."""
    proposals = []
    was_usable = False
    for frame in associated_frames:
        usable = all(
            track["status"] == "associated"
            for track in frame["physicalTracks"]
        )
        if usable and not was_usable and proposals:
            proposals.append(frame["frameIndex"])
        elif usable and not was_usable:
            proposals.append(frame["frameIndex"])
        was_usable = usable
    return proposals[1:]


def recover_segments(
    frames,
    width,
    height,
    associate_fn,
    minimum_segment_frames=12,
    minimum_coverage=0.40,
):
    """Associate independent runs without joining identities across gaps."""
    if not frames:
        return {"segments": [], "restartAccepted": False}

    frames = sorted(frames, key=lambda frame: frame["frameIndex"])
    runs = []
    current = []

    def has_observations(frame):
        points = {
            point["name"]: point
            for point in frame.get("keypoints", [])
        }
        required = (
            ("neck", 0.7),
            ("root_of_tail", 0.8),
            ("left_back_paw", 0.0),
            ("right_back_paw", 0.0),
        )
        return all(
            name in points
            and points[name].get("rawScore", 0) > threshold
            for name, threshold in required
        )

    for frame in frames:
        contiguous = (
            current
            and frame["frameIndex"] == current[-1]["frameIndex"] + 1
        )
        if not has_observations(frame):
            if current:
                runs.append(current)
                current = []
            continue
        if current and not contiguous:
            runs.append(current)
            current = []
        current.append(frame)

    if current:
        runs.append(current)

    segments = []
    for run in runs:
        if len(run) < minimum_segment_frames:
            continue

        result = associate_fn(run, width, height)
        tracks = [
            track
            for frame in result["frames"]
            for track in frame["physicalTracks"]
        ]
        coverage = (
            sum(track["status"] == "associated" for track in tracks)
            / len(tracks)
            if tracks else 0.0
        )
        if coverage < minimum_coverage:
            continue

        segments.append({
            "segmentId": len(segments),
            "startFrame": run[0]["frameIndex"],
            "endFrame": run[-1]["frameIndex"],
            "result": result,
            "coverage": coverage,
        })

    return {
        "segments": segments,
        "restartAccepted": len(segments) > 1,
        "restartFrame": segments[1]["startFrame"]
        if len(segments) > 1 else None,
    }
