"""Formula behavior for paired movement measures and 2-D angles."""

import math
import unittest

from gait_engine.symmetry import joint_angle_2d_degrees, symmetry_indices


class SymmetryIndexTests(unittest.TestCase):
    def test_equal_values_have_zero_signed_and_absolute_asymmetry(self):
        self.assertEqual(symmetry_indices(4.0, 4.0), (0.0, 0.0))

    def test_left_larger_values_have_positive_index(self):
        self.assertEqual(symmetry_indices(3.0, 1.0), (100.0, 100.0))

    def test_reversing_the_pair_reverses_only_the_sign(self):
        self.assertEqual(symmetry_indices(1.0, 3.0), (-100.0, 100.0))

    def test_units_cancel_when_both_inputs_use_the_same_unit(self):
        self.assertEqual(symmetry_indices(30.0, 10.0), symmetry_indices(3.0, 1.0))

    def test_missing_zero_sum_negative_and_nonfinite_values_are_unmeasured(self):
        for pair in (
            (None, 1.0),
            (0.0, 0.0),
            (-1.0, 2.0),
            (math.inf, 1.0),
            (math.nan, 1.0),
        ):
            with self.subTest(pair=pair):
                self.assertEqual(symmetry_indices(*pair), (None, None))


class JointAngleTests(unittest.TestCase):
    def test_right_angle_is_degrees(self):
        self.assertAlmostEqual(
            joint_angle_2d_degrees((1, 0), (0, 0), (0, 1)),
            90.0,
        )

    def test_straight_angle_is_180_degrees(self):
        self.assertAlmostEqual(
            joint_angle_2d_degrees((-1, 0), (0, 0), (1, 0)),
            180.0,
        )

    def test_missing_degenerate_and_nonfinite_landmarks_are_unmeasured(self):
        self.assertIsNone(joint_angle_2d_degrees(None, (0, 0), (1, 1)))
        self.assertIsNone(joint_angle_2d_degrees((0, 0), (0, 0), (1, 1)))
        self.assertIsNone(joint_angle_2d_degrees((math.nan, 0), (0, 0), (1, 1)))


if __name__ == "__main__":
    unittest.main()
