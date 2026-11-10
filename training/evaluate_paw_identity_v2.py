"""Read-only Dalmatian anatomical identity baseline, conditional on human mapping.

No inference, training, remapping, threshold selection, or input writes. Existing
OpenCV is used solely to verify exact source-frame pixels. Output is exclusive.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from training import prepare_paw_annotations as p
from training import evaluate_paw_tracking_v2 as localization

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path("reports/paw-annotation-data-v1")
EXPORT = Path("reports/paw-annotation-data-v2")
BENCHMARK = localization.EXPERIMENT / "multi-video-localization-v2.json"
DEFAULT_OUTPUT = ROOT / localization.EXPERIMENT / "dalmatian-anatomical-identity-v2.json"
THRESHOLDS = (10, 20)
# Recorded human evidence, never selected from prediction distances.
MAPPING = {"A": "right_back_paw", "B": "left_back_paw"}
PINNED = {
    "training/paw_annotation_sources.json": "76b59a4b007fb7223cb973e54ea49f6fddcabb7aa8cbbb9b2039f61a7b2f77a7",
    str(REFERENCE / "manifest.json"): "02a5ec9da7bd928060b9c596372baf8d27998525e7d92b7c5ef2a1f882c4e137",
    str(EXPORT / "manifest.json"): "76d4ac8fcd677cf3393562c99c5dd1dd8cf1448dd6d14ab5d18a5f32f8408bec",
    "training/paw_anatomical_mapping_confirmation.json": "3afe6cec08b16f3ff05e2e8af38565aa3967ace06a569f6f15101919b563ade4",
    "training/paw_bulk_continuity_evidence.json": "80398d5c1355f37ce03911138dbcf11a50a6c0c7bab126176ee66d358fd09ed1",
    str(BENCHMARK): "cb69963441b8cf1021957919ec850761aa062750ad28d75b3a23ee26c7f27e58",
}


def verify_frames(root, video, records, meta, predictions):
    """Decode in index order; compare untransformed pixels, not image similarity."""
    import cv2
    import numpy as np

    by_index = {r["frameIndex"]: r for r in records}
    p.require(len(by_index) == len(records), "Duplicate reference frame")
    for r in records:
        image = root / REFERENCE / r["fileName"]
        p.require(image.resolve().is_relative_to((root / REFERENCE).resolve()),
                  "Image path escapes reference")
        p.require(p.digest(image) == r["imageSha256"], "Reference image hash mismatch")
    cap = cv2.VideoCapture(str(video))
    count = verified = 0
    try:
        p.require(cap.isOpened(), "Cannot decode prediction-source video")
        p.require(math.isclose(cap.get(cv2.CAP_PROP_FPS), meta["fps"], rel_tol=1e-4),
                  "Decoded FPS mismatch")
        while True:
            ok, image = cap.read()
            if not ok:
                break
            p.require(count < len(predictions), "Excess decoded frames")
            p.require(image.shape[:2] == (meta["frameHeight"], meta["frameWidth"]),
                      "Decoded coordinate dimensions mismatch")
            p.require(math.isclose(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000,
                                   predictions[count]["timestampSeconds"], abs_tol=1e-4),
                      "Decoded/prediction timestamp mismatch")
            if count in by_index:
                saved = cv2.imread(str(root / REFERENCE / by_index[count]["fileName"]))
                p.require(saved is not None and np.array_equal(image, saved),
                          f"Exact source-frame pixel mismatch: {count}")
                verified += 1
            count += 1
    finally:
        cap.release()
    p.require(count == len(predictions) and verified == len(records),
              "Decoded frame count/alignment mismatch")
    return {"decodedSourceFrames": count, "exactPixelVerifiedLabelFrames": verified,
            "width": meta["frameWidth"], "height": meta["frameHeight"],
            "opencvVersion": cv2.__version__, "rescalingCroppingOrMirroring": False}


def verify_targets(coco, records, labels, predictions, meta, confirmation, reviews):
    """Bind every visible source label to exactly one reviewed anatomical target.

    The mapping remains provisional. Export flags alone do not verify anatomy.
    Prediction names/coordinates are never used to choose anatomical targets.
    """
    p.require(confirmation.get("confirmed") is True and
              confirmation.get("independentlyVerified") is False and
              confirmation.get("source") == "reviewer-provided" and
              confirmation.get("mapping") == MAPPING and
              confirmation.get("datasetId") == meta["datasetId"] and
              confirmation.get("frameRange") == [46, 90], "Unrecognized human mapping evidence")
    p.require(reviews.get("reviewerProvidedConfirmation") == confirmation,
              "Review confirmation mismatch")
    p.require(len(coco["categories"]) == 1, "Expected one COCO category")
    category = coco["categories"][0]
    names = category["keypoints"]
    p.require(len(names) == 17 and len(set(names)) == 17 and
              set(p.ANATOMICAL) <= set(names), "Invalid COCO channels")
    by_index = {r["frameIndex"]: r for r in records}
    p.require(set(by_index) == {int(k) for k in labels} and len(by_index) == len(records),
              "Reference/label frame set mismatch")
    images = {i["id"]: i for i in coco["images"]}
    p.require(len(images) == len(coco["images"]) == len(records), "Duplicate/missing COCO image")
    image_frames = set()
    for image in images.values():
        i = image["frame_id"]
        p.require(i in by_index and i not in image_frames, "COCO frame mismatch")
        image_frames.add(i)
        r = by_index[i]
        p.require(r["group"] == "dalmatian" and r["split"] == "train" and
                  r["datasetId"] == image["video_id"] == meta["datasetId"] and
                  r["fileName"] == image["file_name"] and
                  r["width"] == image["width"] == meta["frameWidth"] and
                  r["height"] == image["height"] == meta["frameHeight"],
                  "COCO/reference coordinate system mismatch")
        p.require(r["human"] == labels[str(i)] and
                  r["timestampSeconds"] == predictions[i]["timestampSeconds"] and
                  r["savedPredictionContext"] == predictions[i], "Reference source/frame mismatch")
    human_reviews = {}
    for review in reviews["reviews"]:
        if review["datasetId"] == meta["datasetId"]:
            key = (review["frameIndex"], review["physicalPaw"])
            p.require(key not in human_reviews, "Duplicate human review")
            human_reviews[key] = review
    targets, seen, annotation_ids, annotated_images = {}, set(), set(), set()
    for annotation in coco["annotations"]:
        image_id = annotation["image_id"]
        p.require(image_id in images and image_id not in annotated_images and
                  annotation["id"] not in annotation_ids and
                  annotation["category_id"] == category["id"], "Duplicate/invalid COCO annotation")
        annotated_images.add(image_id)
        annotation_ids.add(annotation["id"])
        i = images[image_id]["frame_id"]
        r = by_index[i]
        expected = [0] * 51
        for review in annotation["anatomical_reviews"]:
            paw = review["physicalPaw"]
            key = (i, paw)
            p.require(paw in MAPPING and key not in seen and 46 <= i <= 90,
                      "Duplicate/out-of-scope reviewed target")
            seen.add(key)
            label = labels[str(i)][paw]
            p.require(review == human_reviews.get(key) and
                      review["datasetId"] == meta["datasetId"] and review["frameIndex"] == i and
                      review["correctedLabel"] == label and label["status"] == "visible" and
                      review["originalLabelSha256"] == p.label_digest(label) and
                      review["imageSha256"] == r["imageSha256"], "Stale review label/image provenance")
            p.require(review["identityState"] == "verified" and
                      review["identitySource"] == "human-confirmed-mapping" and
                      review["anatomicalKeypoint"] == MAPPING[paw] and
                      review["landmarkConfirmed"] is True and
                      review["continuityConfirmed"] is True and
                      review["modelExposed"] == labels[str(i)]["modelExposed"] and
                      review["reviewer"] == confirmation["reviewer"] and
                      json.loads(review["evidence"]) == confirmation,
                      "Unsupported anatomical evidence")
            name = MAPPING[paw]
            targets.setdefault(i, {})[name] = dict(label)
            j = 3 * names.index(name)
            expected[j:j + 3] = [label["x"], label["y"], 2]
        p.require(annotation["keypoints"] == expected and
                  annotation["num_keypoints"] == len(annotation["anatomical_reviews"]),
                  "COCO coordinates/visibility differ from reviewed human labels")
    visible = {(int(i), paw) for i, f in labels.items() for paw in p.PAWS
               if f[paw]["status"] == "visible"}
    p.require(seen == visible, "Missing visible anatomical targets; cannot shrink denominator")
    p.require(len(seen) == confirmation["expectedAnnotationCount"] and
              len(targets) == confirmation["expectedFrameCount"], "Confirmed target counts mismatch")
    return targets


def score_identity(targets, frames):
    """Same-name scoring only; all visible targets count even if detection fails."""
    points = {f["frameIndex"]: {q["name"]: q for q in localization.raw_points(f)} for f in frames}
    visible = available = eligible = swapped = ties = 0
    hits = {str(t): 0 for t in THRESHOLDS}
    swaps_at = {str(t): 0 for t in THRESHOLDS}
    audit = []
    for i in sorted(targets):
        human, raw = targets[i], points.get(i, {})
        distances = {}
        for name in p.ANATOMICAL:
            if name not in human:
                continue
            visible += 1
            q, h = raw.get(name), human[name]
            d = math.hypot(q["x"] - h["x"], q["y"] - h["y"]) if q else None
            distances[name] = d
            available += d is not None
            for t in THRESHOLDS:
                hits[str(t)] += d is not None and d <= t
        swap = None
        if all(n in human and n in raw for n in p.ANATOMICAL):
            eligible += 1
            left, right = p.ANATOMICAL
            cross = [math.hypot(raw[a]["x"] - human[b]["x"], raw[a]["y"] - human[b]["y"])
                     for a, b in ((left, right), (right, left))]
            fixed_cost, swapped_cost = sum(distances.values()), sum(cross)
            swap = "swapped" if swapped_cost < fixed_cost else "fixed" if fixed_cost < swapped_cost else "tie"
            swapped += swap == "swapped"
            ties += swap == "tie"
            for t in THRESHOLDS:
                swaps_at[str(t)] += swap == "swapped" and all(d <= t for d in cross)
        audit.append({"frameIndex": i, "sameNameDistancePx": distances, "spatialSwapDiagnostic": swap})
    return {
        "visibleHumanPawLabels": visible, "visibleLabelsReceivingPredictions": available,
        "visibleLabelsMissingPredictions": visible - available,
        "predictionAvailability": available / visible if visible else None,
        "correctIdentityLocalization": {str(t): {
            "thresholdPx": t, "hits": hits[str(t)], "misses": visible - hits[str(t)],
            "denominator": visible, "recall": hits[str(t)] / visible if visible else None,
        } for t in THRESHOLDS},
        "identitySwaps": {"eligibleBothVisibleBothPredictedFrames": eligible,
                          "swappedLowerTotalDistanceFrames": swapped, "equalCostFrames": ties,
                          "swappedFrameFraction": swapped / eligible if eligible else None,
                          "bothCrossDistancesWithinThresholdFrames": swaps_at},
        "frames": audit,
    }


def build_report(root=ROOT):
    for path, sha in PINNED.items():
        p.checked(root, {"path": path, "sha256": sha})
    config = p.load_json(root / "training/paw_annotation_sources.json")
    v1 = p.load_json(root / REFERENCE / "manifest.json")
    v2 = p.load_json(root / EXPORT / "manifest.json")
    p.require(v1["sourceConfiguration"] == v2["sourceConfiguration"] == config,
              "Reference source configuration mismatch")
    for directory, manifest in ((REFERENCE, v1), (EXPORT, v2)):
        for path, sha in manifest["outputSha256"].items():
            # Dog02 is never loaded/scored. Verify export payload integrity only.
            p.checked(root, {"path": str(directory / path), "sha256": sha})
    confirmation = p.load_json(root / "training/paw_anatomical_mapping_confirmation.json")
    continuity = p.load_json(root / "training/paw_bulk_continuity_evidence.json")
    p.require(confirmation["continuityEvidence"] == continuity and
              confirmation["referenceSha256"] == v2["referenceSha256"] ==
              p.digest(root / REFERENCE / "physical-reference.json"), "Evidence reference mismatch")
    sequence, = [s for s in config["sequences"] if s["group"] == "dalmatian"]
    paths = {k: p.checked(root, sequence[k]) for k in ("metadata", "video", "predictions", "originalVideo")}
    meta, pred = p.load_json(paths["metadata"]), p.load_json(paths["predictions"])
    p.validate_split(sequence, meta, set())
    p.require(meta["videoSha256"] == sequence["video"]["sha256"] and
              meta["predictionSha256"] == sequence["predictions"]["sha256"], "Source provenance mismatch")
    schema = p.load_json(p.checked(root, config["keypointSchema"]))
    p.validate_predictions(pred, meta, [k["id"] for k in schema["keypoints"]])
    docs = [(a["path"], p.load_json(p.checked(root, a))) for a in sequence["annotations"]]
    p.require(all(d["originalVideoSha256"] == sequence["originalVideo"]["sha256"] for _, d in docs),
              "Original video mismatch")
    labels, _, _ = p.merge_annotations(docs, meta, pred["frames"])
    reference = p.load_json(root / REFERENCE / "physical-reference.json")
    records = [r for r in reference["records"] if r["group"] == "dalmatian"]
    exported = p.load_json(root / EXPORT / "original-physical-reference.json")
    p.require([r for r in exported if r["group"] == "dalmatian"] == records,
              "Export physical reference mismatch")
    p.require(p.load_json(root / EXPORT / "corrected-physical-reference.json") == exported,
              "Corrected reference differs from original")
    targets = verify_targets(p.load_json(root / EXPORT / "train.coco.json"), records, labels,
                             pred["frames"], meta, confirmation, p.load_json(root / EXPORT / "review.json"))
    alignment = verify_frames(root, paths["video"], records, meta, pred["frames"])
    # Validate every gate before scoring. No anatomical target comes from predictions.
    agnostic = localization.score_localization(labels, {f["frameIndex"]: localization.raw_points(f)
                                                       for f in pred["frames"]})
    baseline = p.load_json(root / BENCHMARK)
    p.require(baseline["sourceManifest"] == config, "Benchmark source mismatch")
    previous, = [r for r in baseline["results"] if r["group"] == "dalmatian"]
    saved = previous["methods"]["rawRTMPose"]
    p.require(agnostic == {k: v for k, v in saved.items() if k != "wholeVideo"},
              "Identity-agnostic results differ from saved Benchmark V2")
    return {
        "evaluation": "Provisional anatomical identity baseline conditional on reviewer-provided mapping",
        "group": "dalmatian", "split": "train", "anatomyIndependentlyVerified": False,
        "excludedSequences": {"dog02": "Anatomical identities not verified; no identity scoring"},
        "humanMappingEvidence": confirmation, "alignmentVerification": alignment,
        "policies": {
            "identity": "Raw left_back_paw only to human left hind; raw right_back_paw only to human right hind; no remapping",
            "thresholdsPx": list(THRESHOLDS), "thresholdComparison": "distance <= threshold",
            "denominator": "Every visible human target; absent same-name prediction counts as miss",
            "availability": "Successful detection and saved finite same-name coordinate, regardless of rawScore, distance or image bounds",
            "swaps": "Both human paws visible and both channels available; swapped total Euclidean distance strictly below fixed total. Ties separate. Also count both cross distances <= each threshold. Diagnostic only; never alters scoring or targets.",
            "tuning": "No mapping/threshold optimization; human mapping and existing 10px/20px thresholds fixed before scoring",
        },
        "rawRTMPose": score_identity(targets, pred["frames"]),
        "identityAgnosticOptimisticUpperBound": saved,
        "limitations": [
            "Anatomical sides and continuity are reviewer-provided provisional evidence, not independent verification; export verified flags are not additional evidence.",
            "Spatial swap diagnostics are geometric candidates, not verified temporal identity switches; unavailable/single-visible/tied frames cannot establish a full swap.",
            "Identity-agnostic localization is the existing optimistic upper bound with freely changing assignments; its minimum-distance assignment does not explicitly maximize threshold hits.",
            "One existing training dog, 79 visible points in 42 frames; no independent generalization or validated gait cycles.",
            "Model exposure flags are source declarations, not an independently audited review history; browser-only drafts were unavailable.",
        ],
        "sourceHashes": PINNED,
        "evaluatorSha256": p.digest(Path(__file__)),
        "annotationUtilitiesSha256": p.digest(Path(p.__file__)),
        "localizationEvaluatorSha256": p.digest(Path(localization.__file__)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        p.require(not args.output.exists(), f"Output exists; choose a fresh path: {args.output}")
        report = build_report()
        localization.write_report(args.output, report)
    except (p.ValidationError, OSError, KeyError, TypeError, ValueError, ImportError) as exc:
        print(f"Anatomical identity baseline STOPPED: {exc}", file=sys.stderr)
        return 2
    print("Provisional Dalmatian identity baseline; anatomy NOT independently verified")
    score = report["rawRTMPose"]
    for t in THRESHOLDS:
        print(f"Recall@{t}px: {score['correctIdentityLocalization'][str(t)]}")
    print("Prediction availability:", score["predictionAvailability"])
    print("Spatial swaps:", score["identitySwaps"])
    print("Saved:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
