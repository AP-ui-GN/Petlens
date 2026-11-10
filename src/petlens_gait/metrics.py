"""Exploratory body-relative canine hind-paw movement metrics."""

import math


def midpoint(a, b):
    return (
        (a["x"] + b["x"]) / 2,
        (a["y"] + b["y"]) / 2,
    )


def body_reference(frame):
    """Return a body center using four torso keypoints."""
    points = {
        p["name"]: p
        for p in frame.get("keypoints", [])
    }

    required = [
        "left_shoulder",
        "right_shoulder",
        "left_hip",
        "right_hip",
    ]

    if any(name not in points for name in required):
        return None

    values = [points[name] for name in required]

    if not all(
        math.isfinite(p["x"]) and math.isfinite(p["y"])
        for p in values
    ):
        return None

    return (
        sum(p["x"] for p in values) / 4,
        sum(p["y"] for p in values) / 4,
    )


def calculate_body_relative_metrics(prediction_frames, tracking_frames):
    """Calculate movement for two segment-local physical paw identities."""
    predictions = {
        f["frameIndex"]: f
        for f in prediction_frames
    }

    previous = {}
    measurements = []

    for frame in tracking_frames:
        index = frame["frameIndex"]
        source = predictions.get(index)

        if source is None:
            previous.clear()
            continue

        center = body_reference(source)
        timestamp = frame.get(
            "timestampSeconds",
            source.get("timestampSeconds"),
        )

        for track in frame["physicalTracks"]:
            identity = track["identity"]
            point = track.get("point")

            valid = (
                track["status"] == "associated"
                and point is not None
                and center is not None
                and timestamp is not None
                and all(
                    math.isfinite(value)
                    for value in (
                        point["x"],
                        point["y"],
                        timestamp,
                    )
                )
            )

            if not valid:
                previous.pop(identity, None)
                continue

            relative_x = point["x"] - center[0]
            relative_y = point["y"] - center[1]

            measurement = {
                "frameIndex": index,
                "timestampSeconds": timestamp,
                "identity": identity,
                "relativeX": relative_x,
                "relativeY": relative_y,
                "speedPixelsPerSecond": None,
            }

            earlier = previous.get(identity)

            if earlier is not None:
                previous_index, previous_time, px, py = earlier
                dt = timestamp - previous_time

                # Never bridge missing frames or tracking gaps.
                if index == previous_index + 1 and dt > 0:
                    displacement = math.hypot(
                        relative_x - px,
                        relative_y - py,
                    )
                    measurement["speedPixelsPerSecond"] = (
                        displacement / dt
                    )

            previous[identity] = (
                index,
                timestamp,
                relative_x,
                relative_y,
            )

            measurements.append(measurement)

    return measurements


def anatomical_reference(frame):
    """Estimate pelvis and torso orientation in image coordinates."""
    points = {
        p["name"]: p
        for p in frame.get("keypoints", [])
    }

    required = (
        "left_shoulder",
        "right_shoulder",
        "left_hip",
        "right_hip",
    )

    if any(name not in points for name in required):
        return None

    if not all(
        math.isfinite(points[name][axis])
        for name in required
        for axis in ("x", "y")
    ):
        return None

    shoulder = midpoint(
        points["left_shoulder"],
        points["right_shoulder"],
    )
    hip = midpoint(
        points["left_hip"],
        points["right_hip"],
    )

    dx = shoulder[0] - hip[0]
    dy = shoulder[1] - hip[1]
    length = math.hypot(dx, dy)

    if length < 1:
        return None

    forward = (dx / length, dy / length)
    perpendicular = (-forward[1], forward[0])

    return {
        "hip": hip,
        "torsoLengthPixels": length,
        "forward": forward,
        "perpendicular": perpendicular,
    }


def calculate_metrics(prediction_frames, tracking_frames):
    """Extend existing measurements with anatomical coordinates."""
    measurements = calculate_body_relative_metrics(
        prediction_frames,
        tracking_frames,
    )

    predictions = {
        f["frameIndex"]: f
        for f in prediction_frames
    }

    references = {
        index: anatomical_reference(frame)
        for index, frame in predictions.items()
    }

    tracks = {
        (frame["frameIndex"], track["identity"]): track
        for frame in tracking_frames
        for track in frame["physicalTracks"]
    }

    for measurement in measurements:
        index = measurement["frameIndex"]
        identity = measurement["identity"]
        reference = references.get(index)
        track = tracks.get((index, identity))

        measurement.update({
            "hipRelativeX": None,
            "hipRelativeY": None,
            "bodyAxisPosition": None,
            "bodyVerticalPosition": None,
            "normalizedBodyAxisPosition": None,
            "normalizedBodyVerticalPosition": None,
            "torsoLengthPixels": None,
        })

        if reference is None or track is None:
            continue

        point = track.get("point")
        if point is None:
            continue

        dx = point["x"] - reference["hip"][0]
        dy = point["y"] - reference["hip"][1]

        forward = reference["forward"]
        perpendicular = reference["perpendicular"]
        length = reference["torsoLengthPixels"]

        along = dx * forward[0] + dy * forward[1]
        across = dx * perpendicular[0] + dy * perpendicular[1]

        measurement.update({
            "hipRelativeX": dx,
            "hipRelativeY": dy,
            "bodyAxisPosition": along,
            "bodyVerticalPosition": across,
            "normalizedBodyAxisPosition": along / length,
            "normalizedBodyVerticalPosition": across / length,
            "torsoLengthPixels": length,
        })

    return measurements
