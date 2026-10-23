"""Pose failures stay on the OpenCV path and still return a result."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from gait_engine.pipeline import _try_pose, analyze_clip
from gait_engine.pose_backend import (
    AP10K_SWAP_PAIRS,
    choose_initial_dog,
    choose_tracked_dog,
    crop_from_keypoints,
    dog_boxes_from_detections,
    swap_left_right,
)
from gait_engine.sampling import apply_rotation


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


class PoseFallbackTests(unittest.TestCase):
    def test_non_coco_schema_is_disabled_for_app_inference(self):
        result = SimpleNamespace(keypoint_schema="ap10k")

        class Backend:
            def process(self, frames):
                return result

        with (
            patch("gait_engine.sampling.sample_video", return_value=[object()]),
            patch("gait_engine.pose_backend.get_pose_backend", return_value=Backend()),
        ):
            pose, skip_reason = _try_pose(Path("unused.mp4"))

        self.assertIsNone(pose)
        self.assertIn("not enabled for application inference", skip_reason)

    def test_a_pose_exception_keeps_the_motion_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "walk.avi"
            write_clip(path)

            class Broken:
                def process(self, frames):
                    raise RuntimeError("weights missing")

            with patch("gait_engine.pose_backend.get_pose_backend", return_value=Broken()):
                result = analyze_clip(path, use_pose=True)

        self.assertEqual(result["pipeline"], "opencv-motion")
        self.assertTrue(result["ok"])
        self.assertIsNotNone(result["diagnostics"]["poseSkipReason"])
        self.assertIn("RuntimeError", result["diagnostics"]["poseSkipReason"])
        self.assertIsNone(result["measurements"]["strideSymmetry"])

    def test_coco_pose_is_not_reported_as_canine_pose_or_used_for_gait(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "walk.avi"
            write_clip(path)
            keypoints = np.zeros((8, 17, 3), dtype=np.float32)
            keypoints[:, :, 0] = 100
            keypoints[:, :, 1] = 100
            keypoints[:, :, 2] = 0.9
            backend_result = SimpleNamespace(
                keypoints=keypoints,
                boxes=[(20.0, 20.0, 200.0, 180.0)] * 8,
                timestamps_seconds=np.arange(8, dtype=np.float64) / 10,
                dog_frames_share=1.0,
                multiple_dogs=False,
                person_present=False,
                detector_id="test/detector",
                pose_id="test/coco-pose",
                detector_revision=None,
                pose_revision=None,
                keypoint_schema="coco-17",
                track_states=("tracked",) * 8,
                track_segment_ids=(1,) * 8,
            )

            class Backend:
                def process(self, frames):
                    return backend_result

            with patch("gait_engine.pose_backend.get_pose_backend", return_value=Backend()):
                result = analyze_clip(path, use_pose=True)

        self.assertEqual(result["pipeline"], "coco-pose")
        self.assertEqual(result["modelInfo"]["pipeline"], "coco-pose")
        self.assertIn("COCO-17 output", result["modelInfo"]["modelName"])
        self.assertIn("unvalidated", result["modelInfo"]["modelName"])
        self.assertIn("human COCO-17", result["signalNote"])
        self.assertIsNone(result["measurements"]["strideSymmetry"])
        self.assertEqual(result["measurements"]["poseSample"][4]["name"], "right_ear")
        self.assertIn("pose-model", result["aiUse"])


class PoseGeometryTests(unittest.TestCase):
    def test_the_first_dog_is_the_largest_then_the_most_central(self):
        boxes = [(0, 0, 10, 10), (100, 100, 40, 40), (140, 100, 40, 10)]
        self.assertEqual(choose_initial_dog(boxes, 200, 200), (100, 100, 40, 40))

    def test_an_overlapping_box_stays_on_the_same_dog(self):
        previous = (10, 10, 40, 40)
        moved = (18, 12, 40, 40)
        other = (400, 10, 50, 50)
        self.assertEqual(
            choose_tracked_dog([other, moved], previous, 640, 480),
            moved,
        )

    def test_a_disjoint_box_does_not_replace_the_tracked_dog(self):
        previous = (10, 10, 40, 40)
        other = (400, 10, 80, 80)
        self.assertIsNone(choose_tracked_dog([other], previous, 640, 480))

    def test_a_person_box_is_not_used_as_the_dog(self):
        labels = np.array([0, 16])
        scores = np.array([0.99, 0.55])
        boxes = np.array([[0, 0, 120, 220], [30, 40, 90, 110]], dtype=np.float32)
        dogs, count, saw_person = dog_boxes_from_detections(
            labels,
            scores,
            boxes,
            dog_id=16,
            person_id=0,
            threshold=0.3,
        )
        self.assertTrue(saw_person)
        self.assertEqual(count, 1)
        self.assertEqual(len(dogs), 1)
        self.assertAlmostEqual(dogs[0][0], 30.0)
        self.assertAlmostEqual(dogs[0][2], 60.0)

    def test_a_keypoint_crop_grows_by_a_quarter(self):
        points = np.zeros((17, 3), dtype=np.float32)
        points[3, 2] = 0.9
        points[4, 2] = 0.9
        points[3, :2] = (40, 40)
        points[4, :2] = (80, 40)
        box = crop_from_keypoints(points, 200, 100)
        self.assertIsNotNone(box)
        assert box is not None
        self.assertAlmostEqual(box[0], 30.0)
        self.assertAlmostEqual(box[2], 60.0)

    def test_left_right_pairs_exchange(self):
        points = np.zeros((1, 17, 3), dtype=np.float32)
        for left, right in AP10K_SWAP_PAIRS:
            points[0, left, 0] = left
            points[0, right, 0] = right
        swapped = swap_left_right(points)
        for left, right in AP10K_SWAP_PAIRS:
            self.assertEqual(swapped[0, left, 0], right)
            self.assertEqual(swapped[0, right, 0], left)

    def test_rotation_turns_a_wide_frame_tall(self):
        frame = np.zeros((10, 20, 3), dtype=np.uint8)
        turned = apply_rotation(frame, 90)
        self.assertEqual(turned.shape[:2], (20, 10))


if __name__ == "__main__":
    unittest.main()
