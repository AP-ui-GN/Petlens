"""The setup report reads local files and does not fetch a model."""

import json
import os
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

from gait_engine.pose_backend import COCO17_KEYPOINTS, POSE_ID
from gait_engine.setup_check import collect_setup, format_setup, inspect_model


def _write_snapshot(root: Path, model_id: str, labels: dict[str, str], *, weight: bool) -> None:
    folder = "models--" + model_id.replace("/", "--")
    snapshot = root / "hub" / folder / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text(json.dumps({"id2label": labels}), encoding="utf8")
    if weight:
        (snapshot / "model.safetensors").write_bytes(b"not-a-real-weight")


def _coco_labels() -> dict[str, str]:
    short = {
        "nose": "Nose",
        "left_eye": "L_Eye",
        "right_eye": "R_Eye",
        "left_ear": "L_Ear",
        "right_ear": "R_Ear",
        "left_shoulder": "L_Shoulder",
        "right_shoulder": "R_Shoulder",
        "left_elbow": "L_Elbow",
        "right_elbow": "R_Elbow",
        "left_wrist": "L_Wrist",
        "right_wrist": "R_Wrist",
        "left_hip": "L_Hip",
        "right_hip": "R_Hip",
        "left_knee": "L_Knee",
        "right_knee": "R_Knee",
        "left_ankle": "L_Ankle",
        "right_ankle": "R_Ankle",
    }
    return {str(index): short[name] for index, name in enumerate(COCO17_KEYPOINTS)}


class SetupCheckTests(unittest.TestCase):
    def test_an_empty_cache_reports_weights_absent(self):
        with self._temp() as root:
            report = inspect_model(root, POSE_ID)
        self.assertFalse(report["weightsPresent"])
        self.assertFalse(report["configPresent"])
        self.assertEqual(report["schema"], "absent")
        self.assertIsNone(report["channel4"])

    def test_a_local_coco_config_is_named_from_the_file(self):
        with self._temp() as root:
            _write_snapshot(root, POSE_ID, _coco_labels(), weight=True)
            report = inspect_model(root, POSE_ID)
            text = format_setup(collect_setup(root))
        self.assertTrue(report["weightsPresent"])
        self.assertEqual(report["schema"], "coco-17")
        self.assertEqual(report["channel4"], "R_Ear")
        self.assertIn("Pose schema: coco-17", text)
        self.assertIn("Validated canine pose capability: no", text)
        self.assertFalse(collect_setup(root)["caninePoseReady"])
        self.assertIn("does not download weights", text)
        self.assertNotIn("ap10k", text.lower())

    def test_a_broken_weight_symlink_is_absent(self):
        with self._temp() as root:
            _write_snapshot(root, POSE_ID, _coco_labels(), weight=False)
            folder = "models--" + POSE_ID.replace("/", "--")
            snapshot = root / "hub" / folder / "snapshots" / "abc"
            try:
                (snapshot / "model.safetensors").symlink_to(snapshot / "missing-blob")
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")
            report = inspect_model(root, POSE_ID)
        self.assertTrue(report["configPresent"])
        self.assertFalse(report["weightsPresent"])
        self.assertEqual(report["channel4"], "R_Ear")

    def test_channel_4_is_not_relabeled_when_the_file_says_something_else(self):
        labels = _coco_labels()
        labels["4"] = "root_of_tail"
        with self._temp() as root:
            _write_snapshot(root, POSE_ID, labels, weight=True)
            report = inspect_model(root, POSE_ID)
        self.assertEqual(report["channel4"], "root_of_tail")
        self.assertEqual(report["schema"], "unverified")

    def test_setup_cli_json_is_valid_and_never_downloads_weights(self):
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as cache:
            environment = os.environ.copy()
            environment["HF_HOME"] = cache
            completed = subprocess.run(
                [sys.executable, str(repository_root / "scripts" / "check_setup.py"), "--json"],
                cwd=repository_root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )

        report = json.loads(completed.stdout)
        self.assertFalse(report["downloadsWeights"])
        self.assertIn("fallbackReady", report)
        self.assertIn("poseReady", report)
        self.assertFalse(report["caninePoseReady"])
        self.assertIn("poseDependencies", report)
        self.assertIn("detector", report)
        self.assertIn("pose", report)

    def _temp(self):
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def _directory():
            with tempfile.TemporaryDirectory() as directory:
                yield Path(directory)

        return _directory()


if __name__ == "__main__":
    unittest.main()
