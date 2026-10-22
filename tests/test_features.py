"""Tests for the raw measurement helpers."""

import unittest

from gait_engine.features import (
    MOTION_FLOOR,
    motion_statistics,
    movement_consistency,
)


class MotionStatisticsTests(unittest.TestCase):
    def test_empty_signal_is_all_zero(self):
        self.assertEqual(motion_statistics([]), (0.0, 0.0, 0.0))

    def test_steady_signal_has_no_deviation(self):
        mean, deviation, coverage = motion_statistics([0.02, 0.02, 0.02])
        self.assertAlmostEqual(mean, 0.02)
        self.assertEqual(deviation, 0.0)
        self.assertEqual(coverage, 1.0)

    def test_coverage_counts_only_frames_above_the_motion_floor(self):
        still = MOTION_FLOOR / 2
        _, _, coverage = motion_statistics([0.02, still, 0.02, still])
        self.assertEqual(coverage, 0.5)


class MovementConsistencyTests(unittest.TestCase):
    def test_a_still_clip_is_not_scored(self):
        self.assertIsNone(movement_consistency(MOTION_FLOOR / 2, 0.0))

    def test_steady_movement_scores_one(self):
        self.assertEqual(movement_consistency(0.02, 0.0), 1.0)

    def test_erratic_movement_scores_lower_than_steady_movement(self):
        steady = movement_consistency(0.02, 0.002)
        erratic = movement_consistency(0.02, 0.010)
        self.assertGreater(steady, erratic)

    def test_score_never_goes_below_zero(self):
        self.assertEqual(movement_consistency(0.01, 0.5), 0.0)


if __name__ == "__main__":
    unittest.main()
