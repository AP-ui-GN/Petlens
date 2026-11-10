"""Deterministic identity scoring and fail-closed provenance checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from training import evaluate_paw_identity_v2 as identity
from training import evaluate_paw_tracking_v2 as localization
from training import prepare_paw_annotations as p

LEFT, RIGHT = p.ANATOMICAL


def point(x, y=0, name=None):
    q = dict(x=x, y=y, rawScore=-100)
    if name:
        q["name"] = name
    return q


def frame(i, left=None, right=None, success=True):
    return dict(frameIndex=i, detectionSuccess=success, keypoints=[
        dict(q, name=n) for n, q in ((LEFT, left), (RIGHT, right)) if q is not None])


def fixture():
    """Human evidence and coordinates constructed independently of predictions."""
    dataset = "human-fixture"
    confirmation = dict(confirmed=True, independentlyVerified=False, source="reviewer-provided",
                        mapping=identity.MAPPING, datasetId=dataset, frameRange=[46, 90],
                        reviewer="human", expectedAnnotationCount=2, expectedFrameCount=1)
    human = dict(A=dict(status="visible", x=30, y=10), B=dict(status="visible", x=10, y=10),
                 modelExposed=False)
    labels = {"46": human}
    predictions = [frame(i) for i in range(47)]
    predictions[46]["timestampSeconds"] = 4.6
    record = dict(frameIndex=46, group="dalmatian", split="train", datasetId=dataset,
                  fileName="images/dalmatian/000046.png", width=100, height=100,
                  human=copy.deepcopy(human), timestampSeconds=4.6, imageSha256="image-hash",
                  savedPredictionContext=copy.deepcopy(predictions[46]))
    entries = [dict(datasetId=dataset, frameIndex=46, physicalPaw=paw,
                    correctedLabel=copy.deepcopy(human[paw]), originalLabelSha256=p.label_digest(human[paw]),
                    imageSha256="image-hash", identityState="verified", identitySource="human-confirmed-mapping",
                    anatomicalKeypoint=identity.MAPPING[paw], landmarkConfirmed=True,
                    continuityConfirmed=True, modelExposed=False, reviewer="human",
                    evidence=json.dumps(confirmation)) for paw in p.PAWS]
    names = [f"other_{i}" for i in range(15)] + [LEFT, RIGHT]
    keypoints = [0] * 45 + [10, 10, 2, 30, 10, 2]
    coco = dict(categories=[dict(id=1, keypoints=names)],
                images=[dict(id=1, frame_id=46, video_id=dataset, file_name=record["fileName"], width=100, height=100)],
                annotations=[dict(id=1, image_id=1, category_id=1, keypoints=keypoints,
                                  num_keypoints=2, anatomical_reviews=copy.deepcopy(entries))])
    reviews = dict(reviewerProvidedConfirmation=copy.deepcopy(confirmation), reviews=entries)
    meta = dict(datasetId=dataset, frameWidth=100, frameHeight=100)
    return [coco, [record], labels, predictions, meta, confirmation, reviews]


class IdentityScoringTests(unittest.TestCase):
    def test_perfect_and_inclusive_thresholds(self):
        targets = {0: {LEFT: point(0), RIGHT: point(100)}, 1: {LEFT: point(0)}}
        frames = [frame(0, point(10), point(120)), frame(1, point(10.0001))]
        score = identity.score_identity(targets, frames)
        self.assertEqual(score["correctIdentityLocalization"]["10"]["hits"], 1)
        self.assertEqual(score["correctIdentityLocalization"]["20"]["hits"], 3)
        self.assertEqual(score["correctIdentityLocalization"]["10"]["denominator"], 3)
        self.assertEqual(score["predictionAvailability"], 1)

    def test_swap_is_not_remapped_and_agnostic_is_optimistic(self):
        targets = {0: {LEFT: point(0), RIGHT: point(100)}}
        frames = [frame(0, point(100), point(0))]
        score = identity.score_identity(targets, frames)
        self.assertEqual(score["correctIdentityLocalization"]["20"]["hits"], 0)
        swaps = score["identitySwaps"]
        self.assertEqual(swaps["swappedLowerTotalDistanceFrames"], 1)
        self.assertEqual(swaps["bothCrossDistancesWithinThresholdFrames"], {"10": 1, "20": 1})
        labels = {"0": dict(A=dict(status="visible", x=0, y=0), B=dict(status="visible", x=100, y=0))}
        upper = localization.score_localization(labels, {0: localization.raw_points(frames[0])})
        self.assertEqual(upper["localization"]["10"]["hits"], 2)

    def test_missing_correct_channel_does_not_borrow_opposite(self):
        targets = {0: {LEFT: point(0)}}
        score = identity.score_identity(targets, [frame(0, right=point(0))])
        self.assertEqual(score["predictionAvailability"], 0)
        self.assertEqual(score["correctIdentityLocalization"]["20"]["misses"], 1)
        self.assertEqual(score["identitySwaps"]["eligibleBothVisibleBothPredictedFrames"], 0)

    def test_missing_frames_failed_detection_and_single_prediction_all_count(self):
        targets = {i: {LEFT: point(0), RIGHT: point(100)} for i in range(3)}
        frames = [frame(0, point(0), point(100), success=False), frame(1, point(0))]
        score = identity.score_identity(targets, frames)
        self.assertEqual(score["visibleHumanPawLabels"], 6)
        self.assertEqual(score["visibleLabelsReceivingPredictions"], 1)
        self.assertEqual(score["correctIdentityLocalization"]["20"]["misses"], 5)

    def test_low_score_outside_image_and_far_points_remain_available(self):
        score = identity.score_identity({0: {LEFT: point(0), RIGHT: point(100)}},
                                        [frame(0, point(-1), point(1000))])
        self.assertEqual(score["predictionAvailability"], 1)
        self.assertEqual(score["correctIdentityLocalization"]["10"]["hits"], 1)

    def test_ties_are_explicit_and_single_visible_is_not_a_swap(self):
        targets = {0: {LEFT: point(0), RIGHT: point(100)}, 1: {LEFT: point(0)}}
        score = identity.score_identity(targets, [frame(0, point(50), point(50)), frame(1, point(100), point(0))])
        self.assertEqual(score["identitySwaps"]["equalCostFrames"], 1)
        self.assertEqual(score["identitySwaps"]["eligibleBothVisibleBothPredictedFrames"], 1)
        self.assertEqual(score["identitySwaps"]["swappedLowerTotalDistanceFrames"], 0)

    def test_spatial_swap_can_have_poor_localization(self):
        score = identity.score_identity({0: {LEFT: point(0), RIGHT: point(100)}},
                                        [frame(0, point(150), point(-50))])
        self.assertEqual(score["identitySwaps"]["swappedLowerTotalDistanceFrames"], 1)
        self.assertEqual(score["identitySwaps"]["bothCrossDistancesWithinThresholdFrames"]["20"], 0)

    def test_empty_deterministic_and_does_not_mutate_inputs(self):
        self.assertIsNone(identity.score_identity({}, [frame(0)])["predictionAvailability"])
        targets, frames = {5: {LEFT: point(1)}}, [frame(5, point(1))]
        before = copy.deepcopy((targets, frames))
        first = identity.score_identity(targets, frames)
        self.assertEqual(first, identity.score_identity(targets, frames))
        self.assertEqual((targets, frames), before)


class ProvenanceTests(unittest.TestCase):
    def test_exact_pixel_frame_alignment_and_failure_modes(self):
        import cv2
        import numpy as np

        for mode in ("aligned", "wrong_pixels", "wrong_timestamp", "wrong_dimensions", "wrong_hash", "missing_frame"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                image = root / identity.REFERENCE / "images/dalmatian/000000.png"
                image.parent.mkdir(parents=True)
                image.write_bytes(b"unchanged reference image")
                record = dict(frameIndex=0, fileName="images/dalmatian/000000.png",
                              imageSha256=p.digest(image) if mode != "wrong_hash" else "stale")
                saved = np.zeros((2, 3, 3), dtype=np.uint8)
                decoded = saved.copy()
                if mode == "wrong_pixels":
                    decoded[0, 0, 0] = 1
                if mode == "wrong_dimensions":
                    decoded = np.zeros((3, 2, 3), dtype=np.uint8)
                cap = MagicMock()
                cap.isOpened.return_value = True
                cap.read.side_effect = ([(False, None)] if mode == "missing_frame" else
                                        [(True, decoded), (False, None)])
                cap.get.side_effect = lambda key: (10 if key == cv2.CAP_PROP_FPS else
                                                   100 if mode == "wrong_timestamp" else 0)
                with patch.object(cv2, "VideoCapture", return_value=cap), patch.object(cv2, "imread", return_value=saved):
                    args = (root, root / "source.mp4", [record],
                            dict(frameWidth=3, frameHeight=2, fps=10), [dict(timestampSeconds=0)])
                    if mode == "aligned":
                        self.assertEqual(identity.verify_frames(*args)["exactPixelVerifiedLabelFrames"], 1)
                    else:
                        with self.assertRaises(p.ValidationError):
                            identity.verify_frames(*args)

    def test_exact_human_targets_and_inputs_preserved(self):
        args = fixture()
        before = copy.deepcopy(args)
        targets = identity.verify_targets(*args)
        self.assertEqual(targets[46][LEFT], args[2]["46"]["B"])
        self.assertEqual(targets[46][RIGHT], args[2]["46"]["A"])
        self.assertEqual(args, before)

    def test_model_channel_names_never_supply_ground_truth(self):
        args = fixture()
        predictions = args[3]
        predictions[46] = dict(frame(46, point(30, 10), point(10, 10)), timestampSeconds=4.6)
        args[1][0]["savedPredictionContext"] = copy.deepcopy(predictions[46])
        targets = identity.verify_targets(*args)
        score = identity.score_identity(targets, predictions)
        self.assertEqual(score["correctIdentityLocalization"]["10"]["hits"], 0)
        args[5]["mapping"] = {"A": LEFT, "B": RIGHT}
        with self.assertRaises(p.ValidationError):
            identity.verify_targets(*args)

    def test_frame_coordinate_and_review_tampering_fail_closed(self):
        mutations = [
            lambda a: a[0]["images"][0].update(frame_id=45),
            lambda a: a[0]["images"][0].update(width=50),
            lambda a: a[0]["images"][0].update(video_id="dog02"),
            lambda a: a[0]["images"][0].update(file_name="flipped.png"),
            lambda a: a[1][0].update(timestampSeconds=4.7),
            lambda a: a[1][0]["human"]["A"].update(x=31),
            lambda a: a[0]["annotations"][0]["anatomical_reviews"][0].update(imageSha256="stale"),
            lambda a: a[0]["annotations"][0]["anatomical_reviews"][0].update(frameIndex=45),
            lambda a: a[0]["annotations"][0]["anatomical_reviews"][0].update(anatomicalKeypoint=LEFT),
            lambda a: a[0]["annotations"][0]["keypoints"].__setitem__(45, 11),
            lambda a: a[5].update(independentlyVerified=True),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                args = fixture()
                mutate(args)
                with self.assertRaises(p.ValidationError):
                    identity.verify_targets(*args)

    def test_visible_targets_cannot_be_omitted_or_duplicated(self):
        for mode in ("missing", "duplicate", "nonvisible"):
            with self.subTest(mode=mode):
                args = fixture()
                entries = args[0]["annotations"][0]["anatomical_reviews"]
                if mode == "missing":
                    entries.pop()
                    args[0]["annotations"][0]["num_keypoints"] = 1
                    args[0]["annotations"][0]["keypoints"][45:48] = [0, 0, 0]
                elif mode == "duplicate":
                    entries.append(copy.deepcopy(entries[0]))
                else:
                    args[2]["46"]["A"].update(status="occluded", x=None, y=None)
                    args[1][0]["human"] = copy.deepcopy(args[2]["46"])
                with self.assertRaises(p.ValidationError):
                    identity.verify_targets(*args)

    def test_same_forged_export_and_review_evidence_is_rejected(self):
        for field, value in (("evidence", "{}"), ("identitySource", "model-channel"),
                             ("landmarkConfirmed", False), ("continuityConfirmed", False),
                             ("originalLabelSha256", "stale")):
            with self.subTest(field=field):
                args = fixture()
                args[0]["annotations"][0]["anatomical_reviews"][0][field] = value
                args[6]["reviews"][0][field] = value
                with self.assertRaises(p.ValidationError):
                    identity.verify_targets(*args)

    def test_exclusive_report_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            localization.write_report(path, {"new": 1})
            first = path.read_bytes()
            with self.assertRaises(FileExistsError):
                localization.write_report(path, {"replacement": 2})
            self.assertEqual(path.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
