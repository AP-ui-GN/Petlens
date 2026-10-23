"""Motion is saved before pose starts, so a later deadline can keep it."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from gait_engine.pipeline import POSE_TIME_LIMIT_NOTE, analyze_clip


def write_clip(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    if not writer.isOpened():
        raise unittest.SkipTest("OpenCV could not open a test video writer")
    for index in range(8):
        frame = np.full((240, 320, 3), 30, dtype=np.uint8)
        origin = 10 + index * 8
        cv2.rectangle(frame, (origin, 40), (origin + 60, 180), (220, 220, 220), -1)
        writer.write(frame)
    writer.release()


class MotionCheckpointTests(unittest.TestCase):
    def test_motion_is_ready_before_pose_and_stride_stays_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "walk.avi"
            write_clip(path)
            order: list[str] = []
            saved: list[dict] = []

            def ready(result: dict) -> None:
                order.append("ready")
                # The CLI serializes immediately. The live dict is reused later.
                saved.append(json.loads(json.dumps(result)))

            def pose_later(_video_path: Path):
                order.append("pose")
                return None, None, "pose was not run"

            with patch("gait_engine.pipeline._try_pose_and_detection", side_effect=pose_later):
                result = analyze_clip(path, use_pose=True, motion_ready=ready)

        self.assertEqual(order, ["ready", "pose"])
        self.assertEqual(len(saved), 1)
        checkpoint = saved[0]
        self.assertEqual(checkpoint["pipeline"], "opencv-motion")
        self.assertIn("Pose analysis exceeded its time limit", checkpoint["signalNote"])
        self.assertEqual(checkpoint["signalNote"], POSE_TIME_LIMIT_NOTE)
        self.assertIsNone(checkpoint["measurements"]["strideSymmetry"])
        self.assertIsNone(checkpoint["measurements"]["asymmetryPercent"])
        self.assertIsNone(checkpoint["strideSymmetryScore"])
        self.assertNotEqual(checkpoint["measurements"]["strideSymmetry"], 0)
        self.assertNotIn("Pose analysis exceeded its time limit", result["signalNote"])
        self.assertIsNone(result["measurements"]["strideSymmetry"])

    def test_skipping_pose_does_not_write_the_time_limit_note(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "walk.avi"
            write_clip(path)
            called = False

            def ready(_result: dict) -> None:
                nonlocal called
                called = True

            result = analyze_clip(path, use_pose=False, motion_ready=ready)

        self.assertFalse(called)
        self.assertNotIn("Pose analysis exceeded its time limit", result["signalNote"])
        self.assertIsNone(result["measurements"]["strideSymmetry"])


if __name__ == "__main__":
    unittest.main()
