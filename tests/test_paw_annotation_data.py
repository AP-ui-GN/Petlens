"""Offline human-label integrity tests; no model imports, inference or training."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from training import prepare_paw_annotations as data


NAMES = [k["id"] for k in json.loads(
    (data.ROOT / "training/canine_keypoint_schema.json").read_text())["keypoints"]]


class PawAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "sources.json"
        self.output = self.root / "dataset"
        self.sources = {"schemaVersion": 1, "sequences": []}
        self.docs = {}
        schema = self.root / "schema.json"
        data.write_json(schema, {"keypoints": [{"id": n} for n in NAMES]})
        self.sources["keypointSchema"] = self.source(schema)
        for group, split in data.SPLITS.items():
            video = self.root / f"{group}.mp4"
            video.write_bytes(group.encode())
            frames = [dict(frameIndex=i, timestampSeconds=i / 10, detectionSuccess=True,
                           keypoints=[dict(name=n, x=80, y=80, rawScore=.01) for n in NAMES])
                      for i in range(2)]
            pred = dict(detectorModel="PekingU/rtdetr_r50vd_coco_o365",
                        poseModel="OpenMMLab RTMPose-m AP-10K", keypointSchema="AP-10K, 17 keypoints",
                        videoSha256=data.digest(video), rawPredictionsWereSmoothedOrCorrected=False,
                        frameCount=2, fps=10, frames=frames)
            pred_path = self.root / f"{group}-pred.json"
            data.write_json(pred_path, pred)
            meta = dict(schemaVersion=1, datasetId=f"petlens-{group}-fixture",
                        videoSha256=data.digest(video), predictionSha256=data.digest(pred_path),
                        sourceFrameCount=2, frameWidth=100, frameHeight=100, fps=10,
                        frames=[dict(frameIndex=i, timestampSeconds=i / 10) for i in range(2)])
            labels = dict(schemaVersion=1, annotationType="physical-hind-tracks",
                          identityDefinition=data.IDENTITY, annotator="human",
                          **{k: meta[k] for k in ("datasetId", "videoSha256", "predictionSha256")},
                          frames={str(i): dict(A=dict(status="visible", x=20 + i, y=30),
                                              B=dict(status="visible", x=60 + i, y=40),
                                              modelExposed=False) for i in range(2)})
            meta_path, ann_path = self.root / f"{group}-meta.json", self.root / f"{group}-ann.json"
            data.write_json(meta_path, meta)
            data.write_json(ann_path, labels)
            spec = dict(group=group, split=split, video=self.source(video),
                        predictions=self.source(pred_path), metadata=self.source(meta_path),
                        annotations=[self.source(ann_path)])
            self.sources["sequences"].append(spec)
            self.docs[group] = (meta, pred, labels)
        data.write_json(self.config, self.sources)

    def source(self, path):
        return dict(path=path.relative_to(self.root).as_posix(), sha256=data.digest(path))

    @staticmethod
    def extract(video, frames, meta, destination):
        hashes = {}
        for key in frames:
            path = destination / f"{int(key):06}.png"
            path.write_bytes(b"fixture-image")
            hashes[int(key)] = data.digest(path)
        return hashes, "fixture"

    def build(self, reviews=None):
        with patch.object(data, "extract_images", self.extract):
            return data.build(self.root, self.config, self.output, reviews)

    def records(self):
        return data.load_json(self.output / "physical-reference.json")["records"]

    def rewrite_annotations(self, group, labels):
        spec = next(s for s in self.sources["sequences"] if s["group"] == group)
        path = self.root / spec["annotations"][0]["path"]
        data.write_json(path, labels)
        spec["annotations"][0] = self.source(path)
        data.write_json(self.config, self.sources)

    def test_unverified_coordinates_preserved_but_no_anatomical_targets(self):
        manifest = self.build()
        self.assertEqual(manifest["counts"]["dalmatian"]["physicalStatusCounts"], {"visible": 4})
        self.assertEqual(manifest["counts"]["dalmatian"]["exportedAnatomicalPoints"], 0)
        record = self.records()[0]
        self.assertEqual(record["human"]["A"], dict(status="visible", x=20, y=30))
        self.assertEqual(record["savedPredictionContext"]["keypoints"][13]["x"], 80)
        self.assertEqual(data.load_json(self.output / "train.coco.json")["annotations"], [])
        originals = data.load_json(self.output / "original-annotations.json")
        self.assertEqual(originals[0]["document"], self.docs["dalmatian"][2])

    def test_verified_export_uses_human_coordinates_even_if_predictions_missing(self):
        self.build()
        records = self.records()
        r = records[0]
        r["savedPredictionContext"]["keypoints"] = []
        review = dict(datasetId=r["datasetId"], frameIndex=0, physicalPaw="A",
                      physicalLabelSha256=data.label_digest(r["human"]["A"]),
                      imageSha256=r["imageSha256"], anatomicalKeypoint="right_back_paw",
                      reviewer="reviewer-1", evidence="Reviewed anatomy and adjacent source frames")
        accepted = data.apply_reviews(records, {"schemaVersion": 1, "reviews": [review]})
        coco = data.coco_export(records, accepted, NAMES, "train")
        target = coco["annotations"][0]
        self.assertEqual(target["keypoints"][48:51], [20, 30, 2])
        self.assertEqual(target["num_keypoints"], 1)
        self.assertEqual(sum(target["keypoints"][2::3]), 2)
        self.assertEqual(target["keypoints"][39:42], [0, 0, 0])

    def test_review_sidecar_full_build_and_coco_layout(self):
        self.build()
        template = data.load_json(self.output / "anatomical-review-template.json")
        first = template["reviews"][0]
        first.update(anatomicalKeypoint="right_back_paw", reviewer="synthetic-test-reviewer",
                     evidence="Synthetic fixture only, never real human labels")
        path = self.root / "review.json"
        data.write_json(path, {"schemaVersion": 1, "reviews": [first]})
        self.output = self.root / "reviewed-dataset"
        manifest = self.build(path)
        self.assertEqual(manifest["counts"]["dalmatian"]["exportedAnatomicalPoints"], 1)
        coco = data.load_json(self.output / "train.coco.json")
        self.assertEqual(coco["categories"][0]["keypoints"], NAMES)
        a = coco["annotations"][0]
        self.assertEqual(len(a["keypoints"]), 51)
        self.assertEqual(a["keypoints"][48:51], [20, 30, 2])
        self.assertTrue((self.output / coco["images"][0]["file_name"]).is_file())

    def test_hash_mismatch_fails_before_output(self):
        spec = self.sources["sequences"][0]
        for kind in ("video", "metadata", "predictions"):
            with self.subTest(kind=kind):
                path = self.root / spec[kind]["path"]
                before = path.read_bytes()
                path.write_bytes(before + b" ")
                with self.assertRaisesRegex(data.ValidationError, "SHA256 mismatch"):
                    self.build()
                path.write_bytes(before)
                self.assertFalse(self.output.exists())

    def test_annotation_hash_and_source_identity_mismatch(self):
        spec = self.sources["sequences"][0]
        path = self.root / spec["annotations"][0]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(data.ValidationError, "SHA256 mismatch"):
            self.build()
        labels = copy.deepcopy(self.docs["dalmatian"][2])
        labels["videoSha256"] = "wrong"
        self.rewrite_annotations("dalmatian", labels)
        with self.assertRaisesRegex(data.ValidationError, "videoSha256 mismatch"):
            self.build()

    def test_identical_duplicates_do_not_add_labels_and_conflicts_fail(self):
        meta, pred, labels = self.docs["dalmatian"]
        merged, origins, count = data.merge_annotations([("a", labels), ("b", labels)], meta, pred["frames"])
        self.assertEqual(count, 4)
        self.assertEqual(len(merged), 2)
        self.assertEqual(origins["0"], ["a", "b"])
        conflict = copy.deepcopy(labels)
        conflict["frames"]["0"]["A"]["x"] += 1
        with self.assertRaisesRegex(data.ValidationError, "Conflicting duplicate label"):
            data.merge_annotations([("a", labels), ("b", conflict)], meta, pred["frames"])

    def test_unmarked_duplicate_does_not_erase_completed_label(self):
        meta, pred, labels = self.docs["dalmatian"]
        seed = copy.deepcopy(labels)
        seed["frames"]["0"]["A"] = dict(status="unmarked", x=None, y=None)
        for docs in ([('a', seed), ('b', labels)], [('a', labels), ('b', seed)]):
            merged, _, _ = data.merge_annotations(docs, meta, pred["frames"])
            self.assertEqual(merged["0"]["A"], labels["frames"]["0"]["A"])

    def test_occluded_ambiguous_uncertain_unmarked_never_get_coordinates(self):
        meta, pred, labels = self.docs["dalmatian"]
        for status in ("occluded", "ambiguous", "uncertain", "unmarked"):
            with self.subTest(status=status):
                doc = copy.deepcopy(labels)
                doc["frames"]["0"]["A"] = dict(status=status, x=None, y=None)
                merged, _, _ = data.merge_annotations([("a", doc)], meta, pred["frames"])
                self.assertIsNone(merged["0"]["A"]["x"])
                doc["frames"]["0"]["A"]["x"] = 20
                with self.assertRaisesRegex(data.ValidationError, "null coordinates"):
                    data.merge_annotations([("a", doc)], meta, pred["frames"])

    def test_invalid_schema_frames_and_coordinates_fail(self):
        meta, pred, labels = self.docs["dalmatian"]
        for mutate in (lambda d: d.update(schemaVersion=2),
                       lambda d: d["frames"].update({"2": d["frames"]["0"]}),
                       lambda d: d["frames"]["0"]["A"].update(x=100),
                       lambda d: d["frames"]["0"]["A"].update(x=True),
                       lambda d: d["frames"]["0"].update(timestampSeconds=.7)):
            doc = copy.deepcopy(labels)
            mutate(doc)
            with self.assertRaises(data.ValidationError):
                data.merge_annotations([("a", doc)], meta, pred["frames"])

    def test_prediction_compatibility_order_and_timing(self):
        meta, pred, _ = self.docs["dalmatian"]
        for mutate in (lambda d: d.update(poseModel="human COCO"),
                       lambda d: d["frames"].reverse(),
                       lambda d: d["frames"][1].update(frameIndex=0),
                       lambda d: d["frames"][1].update(timestampSeconds=0),
                       lambda d: d["frames"][0]["keypoints"].append(d["frames"][0]["keypoints"][0])):
            doc = copy.deepcopy(pred)
            mutate(doc)
            with self.assertRaises(data.ValidationError):
                data.validate_predictions(doc, meta, NAMES)
        doc = copy.deepcopy(pred)
        doc["frames"][0].update(detectionSuccess=False, keypoints=[])
        data.validate_predictions(doc, meta, NAMES)

    def test_dog02_cannot_enter_training_or_model_selection(self):
        self.sources["sequences"][1]["split"] = "train"
        data.write_json(self.config, self.sources)
        with self.assertRaisesRegex(data.ValidationError, "Split leakage"):
            self.build()
        self.sources["sequences"][1]["split"] = "exploratory_evaluation"
        data.write_json(self.config, self.sources)
        self.build()
        self.assertTrue(all(not r["modelSelectionAllowed"] for r in self.records() if r["group"] == "dog02"))
        coco = data.load_json(self.output / "train.coco.json")
        self.assertTrue(all("dog02" not in i["video_id"] for i in coco["images"]))

    def test_duplicate_sequence_or_shared_video_fails(self):
        spec = self.sources["sequences"][0]
        meta = self.docs["dalmatian"][0]
        seen = set()
        data.validate_split(spec, meta, seen)
        with self.assertRaisesRegex(data.ValidationError, "leakage"):
            data.validate_split(spec, meta, seen)
        dog = copy.deepcopy(self.docs["dog02"][0])
        dog["videoSha256"] = meta["videoSha256"]
        with self.assertRaisesRegex(data.ValidationError, "leakage"):
            data.validate_split(self.sources["sequences"][1], dog, seen)

    def test_reviews_need_human_evidence_current_labels_and_distinct_channels(self):
        self.build()
        records = self.records()
        template = data.load_json(self.output / "anatomical-review-template.json")
        self.assertEqual(data.apply_reviews(records, template), {})
        first = copy.deepcopy(template["reviews"][0])
        first.update(anatomicalKeypoint="left_back_paw", reviewer="human", evidence="anatomy")
        for update in ({"reviewer": ""}, {"evidence": ""}, {"physicalLabelSha256": "stale"},
                       {"imageSha256": "stale"}, {"anatomicalKeypoint": "A"}):
            with self.subTest(update=update):
                entry = {**first, **update}
                with self.assertRaises(data.ValidationError):
                    data.apply_reviews(records, {"schemaVersion": 1, "reviews": [entry]})
        second = copy.deepcopy(template["reviews"][1])
        second.update(anatomicalKeypoint="left_back_paw", reviewer="human", evidence="anatomy")
        with self.assertRaisesRegex(data.ValidationError, "one anatomical channel"):
            data.apply_reviews(records, {"schemaVersion": 1, "reviews": [first, second]})
        with self.assertRaisesRegex(data.ValidationError, "duplicate"):
            data.apply_reviews(records, {"schemaVersion": 1, "reviews": [first, first]})

    def test_output_reproducible_and_inputs_immutable(self):
        before = {p: data.digest(p) for p in self.root.iterdir() if p.is_file()}
        first = self.build()
        self.output = self.root / "dataset-2"
        second = self.build()
        self.assertEqual(first, second)
        self.assertTrue(all(data.digest(p) == h for p, h in before.items()))
        with self.assertRaisesRegex(data.ValidationError, "already exists"):
            self.build()

    def test_duplicate_json_keys_rejected(self):
        path = self.root / "bad.json"
        path.write_text('{"frames": {}, "frames": {}}')
        with self.assertRaisesRegex(data.ValidationError, "duplicate JSON key"):
            data.load_json(path)
        path.write_text('{"x": NaN}')
        with self.assertRaisesRegex(data.ValidationError, "nonfinite JSON"):
            data.load_json(path)

    def test_failed_extraction_does_not_leave_partial_dataset(self):
        with patch.object(data, "extract_images", side_effect=data.ValidationError("bad video")):
            with self.assertRaisesRegex(data.ValidationError, "bad video"):
                data.build(self.root, self.config, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.paw-data-*')))


if __name__ == "__main__":
    unittest.main()
