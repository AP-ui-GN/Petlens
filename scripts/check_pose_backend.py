#!/usr/bin/env python3
"""Draw the checkpoint's keypoints on eight frames.

    python scripts/check_pose_backend.py clip.mp4 --out outputs/pose-check/

The current checkpoint emits COCO-17 joints, not AP-10K joints. The review
images use that schema. A low-confidence point is drawn as an open circle and
is not connected. This is not a clinical validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw a pose review for one clip.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs/pose-check"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from gait_engine.pose_backend import (
        KEYPOINT_MIN_SCORE,
        MODEL_OUTPUT_EDGES,
        MODEL_OUTPUT_KEYPOINTS,
        MODEL_OUTPUT_SCHEMA,
        get_pose_backend,
    )
    from gait_engine.sampling import sample_video

    frames = sample_video(args.video)
    if not frames:
        print("No frames were sampled.", file=sys.stderr)
        return 2
    result = get_pose_backend().process(frames)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"schema={result.keypoint_schema} expected={MODEL_OUTPUT_SCHEMA}")
    print("This head does not output root_of_tail. Channel 4 is right_ear.")

    step = max(1, len(frames) // 8)
    picked = list(range(0, len(frames), step))[:8]
    for slot, index in enumerate(picked):
        image = frames[index].image_bgr.copy()
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
            if not np.isfinite(point[0]) or not np.isfinite(point[1]):
                continue
            center = (int(round(point[0])), int(round(point[1])))
            confident = float(point[2]) >= KEYPOINT_MIN_SCORE
            if confident:
                cv2.circle(image, center, 4, (20, 20, 20), -1)
            else:
                cv2.circle(image, center, 5, (0, 0, 180), 1)
            label = f"{name} {float(point[2]):.2f}"
            cv2.putText(
                image,
                label,
                (center[0] + 4, center[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                label,
                (center[0] + 4, center[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )
        cv2.imwrite(str(args.out / f"frame-{slot:02d}.jpg"), image)

    def median_point(name: str) -> np.ndarray | None:
        joint = MODEL_OUTPUT_KEYPOINTS.index(name)
        rows = result.keypoints[:, joint, :]
        keep = np.isfinite(rows[:, 0]) & (rows[:, 2] >= KEYPOINT_MIN_SCORE)
        if not np.any(keep):
            return None
        return np.median(rows[keep, :2], axis=0)

    nose = median_point("nose")
    ear = median_point("right_ear")
    hip = median_point("left_hip")
    if nose is None or ear is None or hip is None:
        print("Review: nose, right ear, or left hip was not measured.")
    else:
        ear_nose = float(np.linalg.norm(ear - nose))
        ear_hip = float(np.linalg.norm(ear - hip))
        print(
            f"Review: right_ear is {ear_nose:.1f}px from the nose and {ear_hip:.1f}px from the left hip. "
            f"Head-side={ear_nose < ear_hip}."
        )
        if ear_nose < ear_hip:
            print("Channel 4 is beside the head. It is not the base of the tail.")

    def below(lower: str, upper: str) -> str:
        low = median_point(lower)
        high = median_point(upper)
        if low is None or high is None:
            return "not measured"
        return "yes" if low[1] > high[1] else "no"

    print(f"Review: left ankle below left hip: {below('left_ankle', 'left_hip')}.")
    print(f"Review: right ankle below right hip: {below('right_ankle', 'right_hip')}.")
    print(
        f"dogFramesShare={result.dog_frames_share} "
        f"multipleDogs={result.multiple_dogs} personPresent={result.person_present}"
    )
    print(f"Wrote {len(picked)} frames to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
