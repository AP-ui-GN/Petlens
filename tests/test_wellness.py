"""Tests for the scoring and observation-text layer."""

import re
import unittest

from gait_engine.wellness import (
    CONCERNING_ASYMMETRY,
    CONCERNING_DROP,
    DEFAULT_WEIGHTS,
    build_observation,
    concerning_change,
    historical_change_factor,
    mobility_factor,
    overall_score,
    score_factors,
    weights_used,
)


def measurements(**overrides):
    """A measurement dictionary with usable movement, plus any overrides."""

    base = {
        "frameCount": 60,
        "durationSeconds": 4.0,
        "meanKeypointConfidence": None,
        "leftAnkleMotion": None,
        "rightAnkleMotion": None,
        "strideSymmetry": None,
        "asymmetryPercent": None,
        "motionMean": 0.02,
        "motionStd": 0.002,
        "motionCoverage": 1.0,
        "hipStability": None,
        "symmetryReliable": False,
    }
    base.update(overrides)
    return base


class ScoreFactorsTests(unittest.TestCase):
    def test_motion_only_clips_score_consistency_and_activity(self):
        factors = score_factors(measurements())

        self.assertIsNotNone(factors["movementConsistency"])
        self.assertIsNotNone(factors["activity"])
        self.assertIsNone(factors["symmetry"])

    def test_unreliable_symmetry_is_not_scored(self):
        factors = score_factors(
            measurements(strideSymmetry=0.9, symmetryReliable=False)
        )

        self.assertIsNone(factors["symmetry"])

    def test_reliable_symmetry_is_scored_on_the_0_to_100_scale(self):
        factors = score_factors(
            measurements(strideSymmetry=0.9, symmetryReliable=True)
        )

        self.assertEqual(factors["symmetry"], 90.0)

    def test_motion_only_clips_do_not_invent_a_mobility_score(self):
        factors = score_factors(measurements())

        self.assertIsNone(factors["mobility"])
        # The pipeline fills this in after the overall score exists.
        self.assertIsNone(factors["historicalChange"])


class OverallScoreTests(unittest.TestCase):
    def test_missing_factors_are_skipped_and_weights_renormalized(self):
        factors = {
            "movementConsistency": 80.0,
            "symmetry": None,
            "mobility": None,
            "activity": 100.0,
            "historicalChange": None,
        }

        # 0.45 and 0.20 renormalize to 0.6923 and 0.3077.
        self.assertEqual(overall_score(factors), 86.2)

    def test_no_scored_factors_means_no_overall_score(self):
        empty = dict.fromkeys(
            ["movementConsistency", "symmetry", "mobility", "activity", "historicalChange"]
        )

        self.assertIsNone(overall_score(empty))

    def test_reported_weights_sum_to_one_and_cover_only_scored_factors(self):
        factors = {
            "movementConsistency": 80.0,
            "symmetry": 70.0,
            "mobility": None,
            "activity": 90.0,
            "historicalChange": None,
        }

        used = weights_used(factors)

        self.assertEqual(set(used), {"movementConsistency", "symmetry", "activity"})
        self.assertAlmostEqual(sum(used.values()), 1.0, places=3)

    def test_a_factor_without_a_weight_cannot_affect_the_score(self):
        weights = {"movementConsistency": 0.45, "activity": 0.20}
        without = overall_score({"movementConsistency": 80.0, "activity": 80.0}, weights)
        with_extra = overall_score(
            {"movementConsistency": 80.0, "activity": 80.0, "mobility": 10.0},
            weights,
        )

        self.assertEqual(without, with_extra)

    def test_configured_weights_include_mobility_and_historical_change(self):
        self.assertIn("mobility", DEFAULT_WEIGHTS)
        self.assertIn("historicalChange", DEFAULT_WEIGHTS)
        self.assertGreater(DEFAULT_WEIGHTS["mobility"], 0)
        self.assertGreater(DEFAULT_WEIGHTS["historicalChange"], 0)

    def test_a_low_mobility_score_lowers_the_overall_and_none_does_not(self):
        base = {"movementConsistency": 80.0, "activity": 80.0}
        skipped = overall_score({**base, "mobility": None})
        low = overall_score({**base, "mobility": 10.0})

        self.assertGreater(skipped, low)


class MobilityFactorTests(unittest.TestCase):
    def pose(self, **overrides):
        base = measurements(
            symmetryReliable=True,
            strideSymmetry=0.8,
            strideTimeCv=0.0,
            headBobAsymmetry=0.1,
            pelvisAsymmetry=0.1,
        )
        base.update(overrides)
        return base

    def test_missing_regularity_and_vertical_symmetry_are_not_scored(self):
        self.assertIsNone(mobility_factor(measurements()))

    def test_a_missing_vertical_index_is_not_treated_as_zero(self):
        # strideTimeCv 0 -> regularity 100. Only one asymmetry index, 0.1,
        # so vertical symmetry is 80. The missing index is left out.
        scored = mobility_factor(self.pose(pelvisAsymmetry=None))

        self.assertEqual(scored, 90.0)

    def test_regularity_and_vertical_symmetry_are_averaged(self):
        # regularity 100, vertical 100 * (1 - 0.1 / 0.5) = 80, mean 90.
        self.assertEqual(mobility_factor(self.pose()), 90.0)

    def test_a_missing_cadence_variation_is_left_out_rather_than_scored_as_zero(self):
        scored = mobility_factor(self.pose(strideTimeCv=None))

        self.assertEqual(scored, 80.0)

    def test_a_measured_zero_variation_can_still_be_scored(self):
        scored = mobility_factor(self.pose(strideTimeCv=0.0, headBobAsymmetry=None, pelvisAsymmetry=None))

        self.assertEqual(scored, 100.0)

    def test_score_factors_uses_the_mobility_factor(self):
        factors = score_factors(self.pose())

        self.assertEqual(factors["mobility"], 90.0)


class HistoricalChangeFactorTests(unittest.TestCase):
    def test_a_first_walk_is_not_scored(self):
        self.assertIsNone(historical_change_factor(80.0, None))
        self.assertIsNone(historical_change_factor(None, 80.0))

    def test_no_change_or_an_improvement_scores_100(self):
        self.assertEqual(historical_change_factor(80.0, 80.0), 100.0)
        self.assertEqual(historical_change_factor(90.0, 80.0), 100.0)

    def test_each_point_of_drop_removes_one_point(self):
        self.assertEqual(historical_change_factor(70.0, 80.0), 90.0)

    def test_a_drop_larger_than_the_scale_floors_at_zero(self):
        self.assertEqual(historical_change_factor(0.0, 150.0), 0.0)

    def test_non_finite_scores_are_not_scored(self):
        self.assertIsNone(historical_change_factor(float("nan"), 80.0))
        self.assertIsNone(historical_change_factor(80.0, float("inf")))


class ConcerningChangeTests(unittest.TestCase):
    def test_a_first_walk_is_never_flagged(self):
        self.assertFalse(concerning_change(50.0, None, measurements()))

    def test_a_large_drop_against_the_previous_walk_is_flagged(self):
        previous = 80.0
        self.assertTrue(
            concerning_change(previous - CONCERNING_DROP, previous, measurements())
        )

    def test_a_small_drop_is_not_flagged(self):
        self.assertFalse(concerning_change(78.0, 80.0, measurements()))

    def test_high_asymmetry_is_flagged_only_when_the_measurement_is_reliable(self):
        reliable = measurements(
            asymmetryPercent=CONCERNING_ASYMMETRY, symmetryReliable=True
        )
        unreliable = measurements(
            asymmetryPercent=CONCERNING_ASYMMETRY, symmetryReliable=False
        )

        self.assertTrue(concerning_change(70.0, None, reliable))
        self.assertFalse(concerning_change(70.0, None, unreliable))


class ObservationTextTests(unittest.TestCase):
    def observation(self, **kwargs):
        defaults = {
            "pet_name": "Mabel",
            "measurements": measurements(),
            "factors": {
                "movementConsistency": 87.6,
                "symmetry": None,
                "mobility": None,
                "activity": 100.0,
                "historicalChange": None,
            },
            "overall": 91.4,
            "previous_overall": None,
            "signal_quality": "limited",
            "signal_note": "No pose landmarks were available.",
            "concerning": False,
        }
        defaults.update(kwargs)
        return build_observation(**defaults)

    def test_every_number_in_the_text_is_a_measured_value(self):
        text = self.observation()
        allowed = {0.0, 100.0, 91.4, 87.6, 59.0}  # scale bounds, scores, frame pairs

        for token in re.findall(r"\d+(?:\.\d+)?", text):
            self.assertIn(float(token), allowed, f"unexpected number in text: {token}")

    def test_unscored_factors_are_named_instead_of_hidden(self):
        text = self.observation()

        self.assertIn("Not scored in this clip", text)
        self.assertIn("stride symmetry", text)

    def test_a_drop_against_the_baseline_is_described_in_points(self):
        text = self.observation(overall=70.0, previous_overall=80.0)

        self.assertIn("10.0 points lower", text)

    def test_an_unusable_clip_does_not_describe_a_pattern(self):
        text = self.observation(
            overall=None,
            signal_quality="unusable",
            signal_note="Almost no movement was visible between frames.",
        )

        self.assertIn("could not measure enough movement", text)
        self.assertNotIn("out of 100", text)

    def test_a_concerning_result_points_to_a_veterinarian(self):
        text = self.observation(concerning=True)

        self.assertIn("veterinarian", text)

    def test_the_text_never_claims_a_diagnosis(self):
        text = self.observation(concerning=True)

        for banned in ("diagnos", "arthritis", "disease", "certainly"):
            self.assertNotIn(banned, text.lower())

    def test_scored_mobility_is_quoted_and_a_missing_hip_is_not_written_as_zero(self):
        text = self.observation(
            factors={
                "movementConsistency": 87.6,
                "symmetry": 80.0,
                "mobility": 80.0,
                "activity": 100.0,
                "historicalChange": None,
            },
            measurements=measurements(
                symmetryReliable=True,
                strideSymmetry=0.8,
                leftAnkleMotion=0.4,
                rightAnkleMotion=0.35,
                hipStability=None,
            ),
        )

        self.assertIn("mobility 80.0 out of 100", text)
        self.assertNotIn("hip", text.lower())

    def test_a_first_walk_does_not_describe_historical_change_as_zero(self):
        text = self.observation()

        self.assertIn("change from baseline", text)
        self.assertIn("Not scored in this clip", text)
        self.assertNotIn("change from baseline 0", text)


if __name__ == "__main__":
    unittest.main()
