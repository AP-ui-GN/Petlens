"""Deterministic, synthetic offline tests: no model or application imports."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from training import evaluate_paw_tracking_v2 as v2


def point(x, y=0):
    return {"x": x, "y": y}


def human(a=None, b=None):
    return {paw: dict(status="visible", **value) if value is not None
            else dict(status="occluded", x=None, y=None)
            for paw, value in (("A", a), ("B", b))} | {"modelExposed": False}


class LocalizationTests(unittest.TestCase):
    def test_missing_paws_and_missing_frames_remain_in_denominator(self):
        labels = {"0": human(point(0), point(50)), "1": human(point(0))}
        score = v2.score_localization(labels, {0: [point(0)]})
        self.assertEqual(score["visibleHumanPawLabels"], 3)
        self.assertEqual(score["visibleLabelsMissingPredictions"], 2)
        self.assertEqual(score["predictionAvailability"], 1 / 3)
        for t in ("10", "20"):
            self.assertEqual(score["localization"][t], dict(
                thresholdPx=int(t), hits=1, misses=2, denominator=3, recall=1 / 3))

    def test_swapped_paws_and_temporal_swaps_are_identity_agnostic(self):
        labels = {str(i): human(point(0), point(50)) for i in range(2)}
        score = v2.score_localization(labels, {
            0: [point(0), point(50)], 1: [point(50), point(0)]})
        self.assertEqual(score["localization"]["10"]["recall"], 1)
        self.assertEqual([v["predictionIndex"] for v in score["frames"][1]["visibleLabels"]], [1, 0])

    def test_one_prediction_cannot_match_two_humans(self):
        score = v2.score_localization({"0": human(point(0), point(1))}, {0: [point(0)]})
        self.assertEqual(score["localization"]["10"]["hits"], 1)
        self.assertEqual(score["predictionAvailability"], .5)

    def test_two_predictions_cannot_reuse_nearest_human(self):
        score = v2.score_localization({"0": human(point(0), point(100))},
                                      {0: [point(0), point(1)]})
        self.assertEqual(score["localization"]["20"]["hits"], 1)
        self.assertEqual(score["predictionAvailability"], 1)

    def test_assignment_is_global_minimum_not_greedy(self):
        pairs = v2.minimum_distance_assignment([point(4), point(0)], [point(0), point(10)])
        self.assertEqual(pairs, [(0, 1, 6.), (1, 0, 0.)])

    def test_single_visible_paw_selects_closest_prediction(self):
        self.assertEqual(v2.minimum_distance_assignment([point(30), point(1)], [point(0)]),
                         [(1, 0, 1.)])

    def test_threshold_boundaries_are_inclusive_euclidean_pixels(self):
        # Includes exact 10/20, just below, just above, and a diagonal distance.
        distances = [(10, 0), (10 - 1e-6, 0), (10 + 1e-6, 0),
                     (20, 0), (20 - 1e-6, 0), (20 + 1e-6, 0), (6, 8)]
        labels = {str(i): human(point(0)) for i in range(len(distances))}
        score = v2.score_localization(labels, {i: [point(*xy)] for i, xy in enumerate(distances)})
        self.assertEqual(score["localization"]["10"]["hits"], 3)
        self.assertEqual(score["localization"]["20"]["hits"], 6)

    def test_ties_are_deterministic(self):
        expected = [(0, 0, 1.), (1, 1, 1.)]
        self.assertEqual(v2.minimum_distance_assignment([point(0), point(0)],
                                                        [point(-1), point(1)]), expected)

    def test_no_visible_labels_has_no_recall(self):
        score = v2.score_localization({"0": human()}, {0: [point(0)]})
        self.assertIsNone(score["predictionAvailability"])
        self.assertIsNone(score["localization"]["10"]["recall"])

    def test_nonfinite_coordinates_fail_closed(self):
        with self.assertRaises(v2.p.ValidationError):
            v2.minimum_distance_assignment([point(float("nan"))], [point(0)])


class AdapterTests(unittest.TestCase):
    def test_raw_coordinates_preserve_low_scores_and_ignore_front_paws(self):
        frame = dict(detectionSuccess=True, keypoints=[
            dict(name="left_back_paw", rawScore=0, **point(-1)),
            dict(name="left_front_paw", rawScore=1, **point(50))])
        self.assertEqual(v2.raw_points(frame), [frame["keypoints"][0]])
        frame["detectionSuccess"] = False
        self.assertEqual(v2.raw_points(frame), [])

    def test_recovery_filters_unresolved_and_null_and_rejects_overlaps(self):
        recovered = {"segments": [{"result": {"frames": [dict(
            frameIndex=0, physicalTracks=[
                dict(status="unresolved", point=point(0)),
                dict(status="associated", point=None)])]}}]}
        self.assertEqual(v2.recovered_points(recovered, 2), {0: []})
        recovered["segments"] *= 2
        with self.assertRaises(v2.p.ValidationError):
            v2.recovered_points(recovered, 2)

    def test_paired_frames_and_whole_video_coverage_and_no_label_input(self):
        frames = [dict(frameIndex=i, detectionSuccess=True, keypoints=[
            dict(name="left_back_paw", rawScore=1, **point(0))]) for i in range(3)]
        original = copy.deepcopy(frames)
        labels = {"0": human(point(0)), "1": human(point(0), point(50))}

        def recover(records, width, height, associate):
            self.assertEqual(records, original)
            self.assertEqual((width, height), (100, 100))
            self.assertIs(associate, association.associate)
            records.clear()  # The caller must protect its original in-memory inputs.
            return {"segments": [{"result": {"frames": [dict(
                frameIndex=0, physicalTracks=[dict(status="associated", point=point(0))])]}}]}

        association = SimpleNamespace(associate=object())
        result = v2.evaluate_sequence(dict(group="dog02", split="exploratory_evaluation"),
            dict(frameWidth=100, frameHeight=100), {"frames": frames}, labels, 0,
            association, SimpleNamespace(recover_segments=recover))
        self.assertTrue(result["exploratory"])
        raw, tracker = (result["methods"][m] for m in ("rawRTMPose", "trackerRecovery"))
        self.assertEqual(raw["visibleHumanPawLabels"], tracker["visibleHumanPawLabels"])
        self.assertEqual(raw["localization"]["10"]["recall"], 2 / 3)
        self.assertEqual(tracker["localization"]["10"]["recall"], 1 / 3)
        self.assertEqual(raw["wholeVideo"]["coverage"], 3 / 6)
        self.assertEqual(tracker["wholeVideo"]["coverage"], 1 / 6)
        self.assertEqual(frames, original)

    def test_report_never_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text("original")
            with self.assertRaises(FileExistsError):
                v2.write_report(path, {"benchmarkVersion": 2})
            self.assertEqual(path.read_text(), "original")
            fresh = Path(directory) / "new.json"
            v2.write_report(fresh, {"benchmarkVersion": 2})
            self.assertEqual(v2.p.load_json(fresh), {"benchmarkVersion": 2})


if __name__ == "__main__":
    unittest.main()
