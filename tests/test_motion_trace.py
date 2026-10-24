"""Compact, timestamped motion trace output."""

import unittest

from gait_engine.motion import compact_motion_trace


class MotionTraceTests(unittest.TestCase):
    def test_keeps_frame_pair_times_and_values_for_short_clips(self):
        trace = compact_motion_trace([0.1, 0.3, 0.5], 2.0)

        self.assertEqual(trace["sampleCount"], 3)
        self.assertEqual(
            trace["points"],
            [
                {"timeSeconds": 0.25, "movement": 0.1},
                {"timeSeconds": 0.75, "movement": 0.3},
                {"timeSeconds": 1.25, "movement": 0.5},
            ],
        )

    def test_downsamples_without_losing_the_raw_sample_count(self):
        trace = compact_motion_trace([float(index) / 1000 for index in range(240)], 24)

        self.assertEqual(trace["sampleCount"], 240)
        self.assertEqual(len(trace["points"]), 120)
        self.assertAlmostEqual(trace["points"][0]["movement"], 0.0005)
        self.assertAlmostEqual(trace["points"][-1]["movement"], 0.2385)

    def test_unknown_fps_retains_count_but_never_fabricates_time(self):
        trace = compact_motion_trace([0.1, 0.2], 0)

        self.assertEqual(trace, {"sampleCount": 2, "points": []})

    def test_invalid_point_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            compact_motion_trace([0.1], 24, max_points=0)


if __name__ == "__main__":
    unittest.main()
