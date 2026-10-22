"""CLI contract tests that do not load OpenCV or model weights."""

import sys
import unittest
from unittest.mock import patch

from scripts.analyze_clip import attach_request_id, parse_args


class AnalyzeCliTests(unittest.TestCase):
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
