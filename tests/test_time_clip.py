"""Regression tests for the clip timer. No weights and no video file."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from scripts.time_clip import (
    format_peak_rss,
    format_seconds,
    main,
    rss_mb,
    time_gait_stage,
    time_pose_stages,
)


def _pose(schema: str) -> SimpleNamespace:
    return SimpleNamespace(
        keypoint_schema=schema,
        keypoints="keypoints",
        timestamps_seconds="timestamps",
        boxes="boxes",
        dog_frames_share=0.5,
    )


class PoseStageTests(unittest.TestCase):
    def test_loader_is_timed_before_process(self):
        calls: list[str] = []

        class Backend:
            def _ensure_loaded(self) -> None:
                calls.append("load")

            def process(self, frames: list[str]) -> SimpleNamespace:
                calls.append("process")
                self.seen = list(frames)
                return _pose("coco-17")

        backend = Backend()
        load_seconds, inference_seconds, result = time_pose_stages(backend, ["frame"])

        self.assertEqual(calls, ["load", "process"])
        self.assertEqual(backend.seen, ["frame"])
        self.assertIsNotNone(load_seconds)
        self.assertGreaterEqual(load_seconds, 0.0)
        self.assertGreaterEqual(inference_seconds, 0.0)
        self.assertEqual(result.keypoint_schema, "coco-17")

    def test_missing_loader_reports_model_load_unmeasured(self):
        class Backend:
            def process(self, frames: list[str]) -> SimpleNamespace:
                return _pose("coco-17")

        load_seconds, inference_seconds, result = time_pose_stages(Backend(), [])

        self.assertIsNone(load_seconds)
        self.assertGreaterEqual(inference_seconds, 0.0)
        self.assertEqual(result.keypoint_schema, "coco-17")

    def test_non_callable_loader_is_not_invoked(self):
        class Backend:
            _ensure_loaded = None

            def process(self, frames: list[str]) -> SimpleNamespace:
                return _pose("coco-17")

        load_seconds, _, _ = time_pose_stages(Backend(), [])
        self.assertIsNone(load_seconds)


class GaitStageTests(unittest.TestCase):
    def test_coco17_does_not_run_ap10k_gait_math(self):
        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("COCO-17 must not enter AP-10K gait math")

        seconds = time_gait_stage(_pose("coco-17"), fail_if_called)
        self.assertIsNone(seconds)

    def test_unknown_schema_does_not_run_ap10k_gait_math(self):
        called = False

        def record(*_args, **_kwargs):
            nonlocal called
            called = True

        self.assertIsNone(time_gait_stage(_pose("unknown"), record))
        self.assertFalse(called)

    def test_ap10k_passes_pose_fields_into_gait_math(self):
        seen: dict[str, object] = {}

        def compute(keypoints, timestamps, boxes, dog_frames_share):
            seen["keypoints"] = keypoints
            seen["timestamps"] = timestamps
            seen["boxes"] = boxes
            seen["dog_frames_share"] = dog_frames_share

        seconds = time_gait_stage(_pose("ap10k"), compute)

        self.assertIsNotNone(seconds)
        self.assertGreaterEqual(seconds, 0.0)
        self.assertEqual(
            seen,
            {
                "keypoints": "keypoints",
                "timestamps": "timestamps",
                "boxes": "boxes",
                "dog_frames_share": 0.5,
            },
        )


class ReportLineTests(unittest.TestCase):
    def test_unmeasured_time_and_unavailable_memory_are_not_zero(self):
        self.assertEqual(format_seconds("model_load_seconds", None), "model_load_seconds not_measured")
        self.assertEqual(format_seconds("gait_seconds", None), "gait_seconds not_measured")
        self.assertEqual(format_seconds("inference_seconds", 1.25), "inference_seconds 1.250")
        self.assertEqual(format_peak_rss(None), "peak_rss_mb not_available")
        self.assertEqual(format_peak_rss(12.34), "peak_rss_mb 12.3")

    def test_rss_is_unavailable_when_resource_cannot_be_imported(self):
        with patch("scripts.time_clip._resource", None):
            self.assertIsNone(rss_mb())
            self.assertEqual(format_peak_rss(rss_mb()), "peak_rss_mb not_available")


class MainReportTests(unittest.TestCase):
    def _run(self, backend, gait):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["time_clip.py", "clip.mp4"]),
            patch("gait_engine.sampling.sample_video", return_value=["a", "b"]),
            patch("gait_engine.pose_backend.get_pose_backend", return_value=backend),
            patch("gait_engine.gait.compute_gait_metrics", side_effect=gait),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main()
        return code, stdout.getvalue().splitlines(), stderr.getvalue().splitlines()

    def test_main_splits_load_from_inference_and_skips_coco_gait(self):
        calls: list[str] = []

        class Backend:
            def _ensure_loaded(self) -> None:
                calls.append("load")

            def process(self, frames: list[str]) -> SimpleNamespace:
                calls.append("process")
                return _pose("coco-17")

        code, lines, errors = self._run(Backend(), AssertionError("gait"))

        self.assertEqual(code, 0)
        self.assertEqual(calls, ["load", "process"])
        self.assertIn("frames 2", lines)
        self.assertTrue(any(line.startswith("sample_seconds ") for line in lines))
        self.assertTrue(any(line.startswith("model_load_seconds ") and "not_measured" not in line for line in lines))
        self.assertTrue(any(line.startswith("inference_seconds ") for line in lines))
        self.assertTrue(any(line.startswith("pose_seconds ") for line in lines))
        self.assertIn("gait_seconds not_measured", lines)
        self.assertIn("gait_metrics_skipped schema=coco-17 requires=ap10k", errors)
        self.assertNotIn("model_load_seconds not_measured; inference_seconds is the whole process() call", errors)

    def test_main_marks_model_load_unmeasured_without_a_loader(self):
        class Backend:
            def process(self, frames: list[str]) -> SimpleNamespace:
                return _pose("coco-17")

        code, lines, errors = self._run(Backend(), AssertionError("gait"))

        self.assertEqual(code, 0)
        self.assertIn("model_load_seconds not_measured", lines)
        self.assertTrue(any(line.startswith("inference_seconds ") for line in lines))
        self.assertIn(
            "model_load_seconds not_measured; inference_seconds is the whole process() call",
            errors,
        )

    def test_main_runs_gait_only_for_ap10k(self):
        seen: list[str] = []

        class Backend:
            def _ensure_loaded(self) -> None:
                return None

            def process(self, frames: list[str]) -> SimpleNamespace:
                return _pose("ap10k")

        def gait(*_args, **_kwargs):
            seen.append("gait")

        code, lines, errors = self._run(Backend(), gait)

        self.assertEqual(code, 0)
        self.assertEqual(seen, ["gait"])
        self.assertTrue(any(line.startswith("gait_seconds ") and line != "gait_seconds not_measured" for line in lines))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
