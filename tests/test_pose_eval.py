"""PCK evaluation tests use fixture data and do not claim model accuracy."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from gait_engine.ap10k_data import SCHEMA_VERSION, DatasetValidationError
from gait_engine.pose_backend import AP10K_KEYPOINTS
from gait_engine.pose_eval import evaluate_ap10k_pck
from scripts.evaluate_ap10k import main


def _report_payload():
    points = [[5.0, 5.0, 2] for _ in AP10K_KEYPOINTS]
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "keypoints": list(AP10K_KEYPOINTS),
            "records": [
                {
                    "annotation_id": 7,
                    "image_id": 1,
                    "bbox_xywh": [0, 0, 10, 10],
                    "keypoints": points,
                }
            ],
        },
        {
            "schema_version": SCHEMA_VERSION,
            "keypoints": list(AP10K_KEYPOINTS),
            "predictions": [
                {
                    "annotation_id": 7,
                    "keypoints": [[5.0, 5.0, 0.9] for _ in AP10K_KEYPOINTS],
                }
            ],
        },
    )


class AP10KPckTests(unittest.TestCase):
    def test_identical_predictions_score_one_on_fixture(self):
        annotations, predictions = _report_payload()
        report = evaluate_ap10k_pck(annotations, predictions)

        self.assertEqual(report["instances"], 1)
        self.assertEqual(report["predicted_instances"], 1)
        self.assertEqual(report["missing_prediction_instances"], 0)
        self.assertEqual(report["metrics"]["PCK@0.05"]["overall"], 1.0)
        self.assertEqual(
            report["per_image"][0]["pck"]["PCK@0.1"], 1.0
        )
        self.assertEqual(
            report["evaluation_scope"],
            "pose localization with ground-truth boxes; detection, tracking, and gait are not evaluated",
        )

    def test_missing_predictions_are_counted_as_incorrect_landmarks(self):
        annotations, predictions = _report_payload()
        predictions["predictions"] = []
        report = evaluate_ap10k_pck(annotations, predictions)

        self.assertEqual(report["missing_prediction_instances"], 1)
        self.assertEqual(report["metrics"]["PCK@0.1"]["overall"], 0.0)
        self.assertEqual(
            report["metrics"]["PCK@0.1"]["per_keypoint"]["nose"]["visible"], 1
        )

    def test_invisible_ground_truth_is_excluded(self):
        annotations, predictions = _report_payload()
        annotations["records"][0]["keypoints"][0][2] = 0
        report = evaluate_ap10k_pck(annotations, predictions)

        self.assertEqual(report["metrics"]["PCK@0.05"]["visible_keypoints"], 16)
        self.assertEqual(report["metrics"]["PCK@0.05"]["per_keypoint"]["left_eye"]["visible"], 0)
        self.assertIsNone(report["metrics"]["PCK@0.05"]["per_keypoint"]["left_eye"]["pck"])

    def test_reports_visible_and_occluded_metrics_and_keypoint_error(self):
        annotations, predictions = _report_payload()
        annotations["records"][0]["keypoints"][0][2] = 1
        predictions["predictions"][0]["keypoints"][0][0] = 6.0
        report = evaluate_ap10k_pck(annotations, predictions)

        pck = report["metrics"]["PCK@0.05"]
        self.assertEqual(pck["by_visibility"]["occluded"]["keypoints"], 1)
        self.assertEqual(pck["by_visibility"]["visible"]["keypoints"], 16)
        self.assertEqual(
            pck["per_keypoint"]["left_eye"]["mean_pixel_error"], 1.0
        )
        self.assertEqual(
            report["metrics"]["keypoint_error"]["mean_pixel_error"], 1 / 17
        )

    def test_confidence_filter_marks_low_scoring_points_incorrect(self):
        annotations, predictions = _report_payload()
        predictions["predictions"][0]["keypoints"][0][2] = 0.2
        report = evaluate_ap10k_pck(
            annotations, predictions, minimum_confidence=0.5
        )

        self.assertEqual(report["metrics"]["PCK@0.05"]["overall"], 16 / 17)

    def test_bootstrap_interval_uses_distinct_images(self):
        annotations, predictions = _report_payload()
        second_record = json.loads(json.dumps(annotations["records"][0]))
        second_record["annotation_id"] = 8
        second_record["image_id"] = 2
        annotations["records"].append(second_record)
        predictions["predictions"].append(
            {
                "annotation_id": 8,
                "keypoints": [[100.0, 100.0, 0.9] for _ in AP10K_KEYPOINTS],
            }
        )

        report = evaluate_ap10k_pck(
            annotations, predictions, bootstrap_samples=200, random_seed=7
        )
        interval = report["metrics"]["PCK@0.1"]["bootstrap_95_ci_by_image"]

        self.assertEqual(interval["images"], 2)
        self.assertEqual(interval["replicates"], 200)
        self.assertLessEqual(interval["lower"], report["metrics"]["PCK@0.1"]["overall"])
        self.assertGreaterEqual(interval["upper"], report["metrics"]["PCK@0.1"]["overall"])

    def test_rejects_wrong_keypoint_order_and_duplicate_predictions(self):
        annotations, predictions = _report_payload()
        predictions["keypoints"][0], predictions["keypoints"][1] = (
            predictions["keypoints"][1],
            predictions["keypoints"][0],
        )
        with self.assertRaisesRegex(DatasetValidationError, "keypoint order"):
            evaluate_ap10k_pck(annotations, predictions)

        annotations, predictions = _report_payload()
        predictions["predictions"].append(predictions["predictions"][0])
        with self.assertRaisesRegex(DatasetValidationError, "Duplicate prediction"):
            evaluate_ap10k_pck(annotations, predictions)

    def test_cli_reads_prediction_files_and_emits_json(self):
        annotations, predictions = _report_payload()
        with tempfile.TemporaryDirectory() as temporary:
            annotation_path = Path(temporary) / "annotations.json"
            prediction_path = Path(temporary) / "predictions.json"
            annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
            prediction_path.write_text(json.dumps(predictions), encoding="utf-8")
            stdout = io.StringIO()
            with (
                patch(
                    "sys.argv",
                    [
                        "evaluate_ap10k.py",
                        "--annotations",
                        str(annotation_path),
                        "--predictions",
                        str(prediction_path),
                    ],
                ),
                redirect_stdout(stdout),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["instances"], 1)

    def test_cli_reports_invalid_utf8_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            annotation_path = Path(temporary) / "annotations.json"
            prediction_path = Path(temporary) / "predictions.json"
            annotation_path.write_bytes(b"\xff")
            prediction_path.write_text("{}", encoding="utf-8")
            stderr = io.StringIO()
            with (
                patch(
                    "sys.argv",
                    [
                        "evaluate_ap10k.py",
                        "--annotations",
                        str(annotation_path),
                        "--predictions",
                        str(prediction_path),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                exit_code = main()

        self.assertEqual(exit_code, 2)
        self.assertIn("Could not read JSON file", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
