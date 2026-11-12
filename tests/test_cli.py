"""CLI contract tests that do not load OpenCV or model weights."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.analyze_clip import attach_request_id, parse_args


class AnalyzeCliTests(unittest.TestCase):
    def test_missing_pipeline_dependency_returns_json_and_writes_failure(self):
        import tempfile

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            command = (
                "import runpy, sys; sys.modules['cv2'] = None; "
                "sys.argv = ['analyze_clip.py', 'unused.mp4', '--output-json', sys.argv[1], "
                "'--request-id', 'missing-runtime']; "
                "runpy.run_path('scripts/analyze_clip.py', run_name='__main__')"
            )
            result = subprocess.run([sys.executable, "-c", command, str(output)],
                                    cwd=root, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("ModuleNotFoundError", payload["error"])
            self.assertEqual(payload["requestId"], "missing-runtime")
            self.assertEqual(json.loads(output.read_text()), payload)

    def test_request_id_argument_is_parsed(self):
        with patch.object(
            sys,
            "argv",
            ["analyze_clip.py", "walk.mp4", "--request-id", "request-123", "--no-pose"],
        ):
            args = parse_args()

        self.assertEqual(args.request_id, "request-123")
        self.assertTrue(args.no_pose)

    def test_request_id_is_added_to_success_diagnostics(self):
        result = {
            "ok": True,
            "pipeline": "opencv-motion",
            "diagnostics": {"framePairs": 10},
        }

        updated = attach_request_id(result, "request-123")

        self.assertIs(updated, result)
        self.assertEqual(updated["diagnostics"]["requestId"], "request-123")
        self.assertEqual(updated["diagnostics"]["framePairs"], 10)
        self.assertNotIn("requestId", updated)

    def test_request_id_is_added_to_failure_payload(self):
        result = {"ok": False, "error": "invalid clip"}

        updated = attach_request_id(result, "request-456")

        self.assertEqual(updated["requestId"], "request-456")
        self.assertEqual(updated["error"], "invalid clip")

    def test_missing_request_id_does_not_change_result(self):
        result = {"ok": True, "diagnostics": {"framePairs": 10}}

        self.assertIs(attach_request_id(result, None), result)
        self.assertNotIn("requestId", result["diagnostics"])


if __name__ == "__main__":
    unittest.main()
