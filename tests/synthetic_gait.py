"""A side-on walking dog as an AP-10K keypoint array.

The dog is geometry, not a recording. Paws are sinusoids. Head and pelvis
get two downward dips per stride. Nothing here is a clinical label.
"""

from __future__ import annotations

import math

import numpy as np

from gait_engine.pose_backend import (
    LEFT_BACK_PAW,
    LEFT_ELBOW,
    LEFT_EYE,
    LEFT_FRONT_PAW,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    NECK,
    NOSE,
    RIGHT_BACK_PAW,
    RIGHT_ELBOW,
    RIGHT_EYE,
    RIGHT_FRONT_PAW,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    ROOT_OF_TAIL,
)

STRIDE_HZ = 1.0


def walking_dog(
    *,
    seconds: float = 8.0,
    fps: float = 15.0,
    body_length: float = 120.0,
    box_height: float = 80.0,
    amplitude: float = 0.30,
    limb_scale: dict[str, float] | None = None,
    heading: float = 0.0,
    translation: tuple[float, float] = (0.0, 0.0),
    scale: float = 1.0,
    noise: float = 0.0,
    score: float = 0.95,
    dip_pixels: float = 10.0,
    even_dip_scale: float = 1.0,
    in_phase_rear: bool = False,
    in_phase_front: bool = False,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, list[tuple[float, float, float, float]]]:
    """Return ``(keypoints, timestamps, boxes)``.

    ``limb_scale`` keys are frontLeft, frontRight, rearLeft, rearRight.
    ``heading`` is radians from image +x. ``scale`` multiplies the drawing.
    """

    scales = {
        "frontLeft": 1.0,
        "frontRight": 1.0,
        "rearLeft": 1.0,
        "rearRight": 1.0,
    }
    if limb_scale:
        scales.update(limb_scale)
    count = max(2, int(round(seconds * fps)))
    timestamps = np.arange(count, dtype=np.float64) / fps
    forward = np.array([math.cos(heading), math.sin(heading)], dtype=np.float64)
    # Image y grows downward. Up stays image-up when the dog turns around.
    up = np.array([0.0, -1.0], dtype=np.float64)
    origin = np.array(translation, dtype=np.float64)

    def place(along: float, above: float) -> np.ndarray:
        return origin + scale * (along * forward + above * up)

    phases = {
        "rearLeft": 0.0,
        "frontLeft": 0.25,
        "rearRight": 0.0 if in_phase_rear else 0.5,
        "frontRight": 0.25 if in_phase_front else 0.75,
    }
    paw_along = {
        "rearLeft": 0.18 * body_length,
        "rearRight": 0.18 * body_length,
        "frontLeft": 0.72 * body_length,
        "frontRight": 0.72 * body_length,
    }
    paw_index = {
        "rearLeft": LEFT_BACK_PAW,
        "rearRight": RIGHT_BACK_PAW,
        "frontLeft": LEFT_FRONT_PAW,
        "frontRight": RIGHT_FRONT_PAW,
    }

    keypoints = np.zeros((count, 17, 3), dtype=np.float32)
    keypoints[:, :, 2] = score
    boxes: list[tuple[float, float, float, float]] = []
    rng = np.random.default_rng(seed)

    for index, time in enumerate(timestamps):
        cycle = (time * STRIDE_HZ) % 1.0
        dip_scale = even_dip_scale if (time * STRIDE_HZ * 2.0) % 2.0 >= 1.0 else 1.0
        dip = dip_pixels * dip_scale * (1.0 + math.cos(4.0 * math.pi * STRIDE_HZ * time)) / 2.0
        # above is negative image-y when facing +x, so a downward dip reduces "above".
        points = {
            ROOT_OF_TAIL: place(0.0, 0.0 - dip),
            NECK: place(body_length, 8.0),
            NOSE: place(body_length + 22.0, 18.0 - dip),
            LEFT_EYE: place(body_length + 16.0, 22.0),
            RIGHT_EYE: place(body_length + 16.0, 14.0),
            LEFT_SHOULDER: place(0.74 * body_length, 6.0),
            RIGHT_SHOULDER: place(0.70 * body_length, 2.0),
            LEFT_HIP: place(0.20 * body_length, 4.0),
            RIGHT_HIP: place(0.16 * body_length, 0.0),
            LEFT_ELBOW: place(0.68 * body_length, -16.0),
            RIGHT_ELBOW: place(0.64 * body_length, -18.0),
            LEFT_KNEE: place(0.22 * body_length, -16.0),
            RIGHT_KNEE: place(0.18 * body_length, -18.0),
        }
        for name, joint in paw_index.items():
            wave = scales[name] * amplitude * math.sin(2.0 * math.pi * (STRIDE_HZ * time + phases[name]))
            points[joint] = place(paw_along[name] + wave * body_length, -36.0)
        for joint, xy in points.items():
            jitter = rng.normal(0.0, noise, size=2) if noise else 0.0
            keypoints[index, joint, 0] = float(xy[0] + (jitter[0] if noise else 0.0))
            keypoints[index, joint, 1] = float(xy[1] + (jitter[1] if noise else 0.0))
        boxes.append((0.0, 0.0, scale * body_length * 1.5, scale * box_height))
    return keypoints, timestamps, boxes
