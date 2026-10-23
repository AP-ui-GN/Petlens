"""Strict tests for canonical AP-10K split preparation."""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from gait_engine.ap10k_data import (
    DatasetValidationError,
    SCHEMA_VERSION,
    flip_ap10k_keypoints,
    prepare_ap10k,
)
from gait_engine.pose_backend import AP10K_KEYPOINTS


def _category_names():
    return [
        "L_Eye", "R_Eye", "Nose", "Neck", "Root of tail", "L_Shoulder",
        "L_Elbow", "L_F_Paw", "R_Shoulder", "R_Elbow", "R_F_Paw",
        "L_Hip", "L_Knee", "L_B_Paw", "R_Hip", "R_Knee", "R_B_Paw",
    ]


def _split_payload(image_id, annotation_id, *, group_id=None, keypoints=None):
    image = {
        "id": image_id,
        "file_name": f"{image_id}.jpg",
        "width": 20,
        "height": 20,
    }
    if group_id is not None:
        image["group_id"] = group_id
    points = keypoints or [value for index in range(17) for value in (5, 5, 2)]
    return {
        "images": [image],
        "categories": [{"id": 1, "name": "animal", "keypoints": _category_names()}],
        "annotations": [
            {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": 1,
                "bbox": [1, 1, 18, 18],
                "keypoints": points,
                "num_keypoints": 17,
            }
        ],
    }


def _second_annotation(image_id, annotation_id):
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": 1,
        "bbox": [2, 2, 10, 10],
        "keypoints": [value for index in range(17) for value in (6, 6, 2)],
        "num_keypoints": 17,
    }


class AP10KPreparationTests(unittest.TestCase):
    def _fixture(self, directory, *, group_ids=None, duplicate_image=False):
        root = Path(directory) / "dataset"
        image_dir = root / "data"
        image_dir.mkdir(parents=True)
        split_paths = {}
        for index, split in enumerate(("train", "val", "test")):
            image_id = index + 1
            pixel_value = 0 if duplicate_image else image_id * 40
            image_bytes = cv2.imencode(
                ".jpg",
                np.full((20, 20, 3), pixel_value, dtype=np.uint8),
            )[1].tobytes()
            (image_dir / f"{image_id}.jpg").write_bytes(image_bytes)
            source = root / "annotations" / f"{split}.json"
            source.parent.mkdir(exist_ok=True)
            group = None if group_ids is None else group_ids[index]
            source.write_text(
                json.dumps(_split_payload(image_id, index + 1, group_id=group)),
                encoding="utf-8",
            )
            split_paths[split] = source
        return root, Path(directory) / "prepared", split_paths

    def test_preserves_official_splits_and_ap10k_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            result = prepare_ap10k(root, output, splits)
            self.assertEqual(result["schema_version"], SCHEMA_VERSION)
            self.assertEqual(result["keypoints"], list(AP10K_KEYPOINTS))
            self.assertEqual(
                {name: details["annotation_count"] for name, details in result["splits"].items()},
                {"train": 1, "val": 1, "test": 1},
            )
            train = json.loads((output / "train.json").read_text(encoding="utf-8"))
            self.assertEqual(train["keypoints"], list(AP10K_KEYPOINTS))
            self.assertEqual(train["records"][0]["keypoints"][4], [5.0, 5.0, 2])
            self.assertIn("same-dog leakage cannot be ruled out", result["identity_grouping"])

    def test_rejects_wrong_keypoint_order_instead_of_renaming_channels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            payload = json.loads(splits["train"].read_text(encoding="utf-8"))
            payload["categories"][0]["keypoints"][0:2] = ["Nose", "L_Eye"]
            splits["train"].write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DatasetValidationError, "keypoint order"):
                prepare_ap10k(root, output, splits)

    def test_accepts_canonical_full_keypoint_names_without_changing_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            payload = json.loads(splits["train"].read_text(encoding="utf-8"))
            payload["categories"][0]["keypoints"] = list(AP10K_KEYPOINTS)
            splits["train"].write_text(json.dumps(payload), encoding="utf-8")
            result = prepare_ap10k(root, output, splits)
            self.assertEqual(result["keypoints"], list(AP10K_KEYPOINTS))

    def test_allows_multiple_dog_instances_in_one_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            payload = json.loads(splits["train"].read_text(encoding="utf-8"))
            payload["annotations"].append(_second_annotation(1, 99))
            splits["train"].write_text(json.dumps(payload), encoding="utf-8")
            result = prepare_ap10k(root, output, splits)
            self.assertEqual(result["splits"]["train"]["annotation_count"], 2)

    def test_rejects_identity_group_leakage_between_splits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(
                temporary, group_ids=("dog-a", "dog-a", "dog-c")
            )
            with self.assertRaisesRegex(DatasetValidationError, "appears in both"):
                prepare_ap10k(root, output, splits)

    def test_rejects_exact_duplicate_image_content_across_splits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary, duplicate_image=True)
            with self.assertRaisesRegex(DatasetValidationError, "Identical image content"):
                prepare_ap10k(root, output, splits)

    def test_rejects_invalid_visibility_and_out_of_bounds_visible_points(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            payload = json.loads(splits["train"].read_text(encoding="utf-8"))
            payload["annotations"][0]["keypoints"][2] = 3
            splits["train"].write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DatasetValidationError, "visibility"):
                prepare_ap10k(root, output, splits)

        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            payload = json.loads(splits["train"].read_text(encoding="utf-8"))
            payload["annotations"][0]["keypoints"][0] = 21
            splits["train"].write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DatasetValidationError, "outside the image"):
                prepare_ap10k(root, output, splits)

    def test_rejects_unreadable_or_mismatched_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            (root / "data" / "1.jpg").write_bytes(b"not an image")
            with self.assertRaisesRegex(DatasetValidationError, "cannot be decoded"):
                prepare_ap10k(root, output, splits)

        with tempfile.TemporaryDirectory() as temporary:
            root, output, splits = self._fixture(temporary)
            (root / "data" / "1.jpg").write_bytes(
                cv2.imencode(
                    ".jpg", np.zeros((10, 10, 3), dtype=np.uint8)
                )[1].tobytes()
            )
            with self.assertRaisesRegex(DatasetValidationError, "dimensions do not match"):
                prepare_ap10k(root, output, splits)

    def test_horizontal_flip_exchanges_all_ap10k_left_right_channels(self):
        points = np.asarray(
            [[index * 3.0, index, index % 3] for index in range(17)],
            dtype=np.float32,
        )
        flipped = flip_ap10k_keypoints(points, 100)

        self.assertEqual(flipped[2].tolist(), [93.0, 2.0, 2.0])
        self.assertEqual(flipped[5].tolist(), [75.0, 8.0, 2.0])
        self.assertEqual(flipped[8].tolist(), [84.0, 5.0, 2.0])
        self.assertEqual(flipped[11].tolist(), [57.0, 14.0, 2.0])
        self.assertEqual(flipped[14].tolist(), [66.0, 11.0, 2.0])
        self.assertEqual(points[5, 0], 15.0)


if __name__ == "__main__":
    unittest.main()
