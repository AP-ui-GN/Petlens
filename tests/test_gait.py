"""Gait metrics from a synthetic AP-10K walk. No model is loaded."""

import unittest

from gait_engine.gait import SIDE_ON_REASON, compute_gait_metrics
from tests.synthetic_gait import walking_dog


def _measure(**kwargs):
    keypoints, timestamps, boxes = walking_dog(**kwargs)
    return compute_gait_metrics(
        keypoints,
        timestamps=timestamps,
        boxes=boxes,
        dog_frames_share=1.0,
    )


def _numbers(result: dict) -> dict[str, float]:
    found = {}
    for key in (
        "strideSymmetry",
        "cadenceStridesPerMinute",
        "strideTimeCv",
        "headVerticalOscillation",
        "pelvisVerticalOscillation",
        "headBobAsymmetry",
        "pelvisAsymmetry",
    ):
        if result[key] is not None:
            found[key] = result[key]
    for side in ("front", "rear"):
        if result["limbSymmetry"][side] is not None:
            found[f"limb.{side}"] = result["limbSymmetry"][side]
        if result["strideLengthBodyLengths"][side] is not None:
            found[f"length.{side}"] = result["strideLengthBodyLengths"][side]
    return found


class SymmetricWalkTests(unittest.TestCase):
    def test_a_symmetric_dog_scores_both_pairs_high(self):
        result = _measure()

        self.assertGreaterEqual(result["limbSymmetry"]["front"], 0.95)
        self.assertGreaterEqual(result["limbSymmetry"]["rear"], 0.95)
        self.assertLess(result["headBobAsymmetry"], 0.2)
        self.assertLess(result["pelvisAsymmetry"], 0.2)
        self.assertTrue(result["view"]["sideOn"])
        self.assertTrue(result["symmetryReliable"])

    def test_a_smaller_right_rear_stride_lowers_only_the_rear_pair(self):
        result = _measure(limb_scale={"rearRight": 0.7})

        self.assertAlmostEqual(result["limbSymmetry"]["rear"], 0.82, delta=0.05)
        self.assertGreaterEqual(result["limbSymmetry"]["front"], 0.95)
        self.assertAlmostEqual(result["strideSymmetry"], result["limbSymmetry"]["rear"], places=3)

    def test_one_smaller_dip_raises_the_asymmetry_index(self):
        even = _measure()
        uneven = _measure(even_dip_scale=0.6)

        self.assertGreater(uneven["pelvisAsymmetry"], even["pelvisAsymmetry"] + 0.02)
        self.assertGreater(uneven["headBobAsymmetry"], even["headBobAsymmetry"] + 0.02)

    def test_pan_scale_and_a_mirrored_heading_do_not_change_the_metrics(self):
        base = _numbers(_measure())
        variants = [
            _numbers(_measure(translation=(40.0, -15.0))),
            _numbers(_measure(scale=2.0)),
            _numbers(_measure(heading=math_pi())),
        ]
        for variant in variants:
            self.assertEqual(set(variant), set(base))
            for key, value in base.items():
                self.assertAlmostEqual(variant[key], value, delta=0.02, msg=key)

    def test_scores_below_the_threshold_are_null_not_zero(self):
        result = _measure(score=0.1)

        self.assertIsNone(result["strideSymmetry"])
        self.assertIsNone(result["limbSymmetry"]["front"])
        self.assertNotEqual(result["strideSymmetry"], 0)
        self.assertTrue(result["notMeasuredReasons"])

    def test_fewer_than_three_strides_is_null_with_a_reason(self):
        result = _measure(seconds=1.2)

        self.assertIsNone(result["limbSymmetry"]["front"])
        self.assertIsNone(result["strideSymmetry"])
        self.assertTrue(any("strides" in reason.lower() for reason in result["notMeasuredReasons"]))

    def test_a_front_facing_dog_fails_the_side_on_gate(self):
        result = _measure(heading=math_pi() / 2.0)

        self.assertFalse(result["view"]["sideOn"])
        self.assertIsNone(result["strideSymmetry"])
        self.assertIn(SIDE_ON_REASON, result["notMeasuredReasons"])

    def test_paws_that_move_together_are_not_scored_as_a_pair(self):
        result = _measure(in_phase_rear=True, in_phase_front=True)

        self.assertIsNone(result["limbSymmetry"]["front"])
        self.assertIsNone(result["limbSymmetry"]["rear"])
        self.assertTrue(
            any("could not be told apart" in reason for reason in result["notMeasuredReasons"])
        )

    def test_a_one_hertz_stride_is_about_sixty_per_minute(self):
        result = _measure()

        self.assertAlmostEqual(result["cadenceStridesPerMinute"], 60.0, delta=2.0)


def math_pi() -> float:
    return 3.141592653589793


if __name__ == "__main__":
    unittest.main()
