"""Offline, identity-agnostic hind-paw localization benchmark (no inference).

Run from the repository root: python -m training.evaluate_paw_tracking_v2
Only the new report is written; all inputs are read-only.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys

from training import prepare_paw_annotations as p

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path("tmp/rtmpose-test/paw-tracking-experiment")
DEFAULT_OUTPUT = ROOT / EXPERIMENT / "multi-video-localization-v2.json"
ALGORITHMS = {
    "association": EXPERIMENT / "dog02-identity-association/associate.py",
    "observationTracker": EXPERIMENT / "dog02-temporal-tracker-v2/tracker.py",
    "recovery": EXPERIMENT / "segment-recovery-v2/recovery.py",
}
THRESHOLDS = (10, 20)
LIMITATION = (
    "Identity-agnostic localization: an optimistic upper bound, NOT proof of "
    "correct anatomical or temporal identity. No independent identity accuracy "
    "is estimated; per-frame assignments may switch freely."
)


def minimum_distance_assignment(predicted, human):
    """Maximum-cardinality, minimum-total-Euclidean-distance one-to-one pairs.

    Enumerate at most two paws. Equal costs use input order deterministically.
    Assignment is independent of the thresholds; it does not maximize hit count.
    Returns (prediction index, human index, distance in source-image pixels).
    """
    p.require(len(predicted) <= 2 and len(human) <= 2, "Expected at most two paws")
    for point in (*predicted, *human):
        p.require(all(p.finite(point.get(c)) for c in ("x", "y")),
                  "Invalid localization coordinate")
    count = min(len(predicted), len(human))
    if not count:
        return []
    candidates = []
    for pi in itertools.combinations(range(len(predicted)), count):
        for hi in itertools.permutations(range(len(human)), count):
            pairs = [(i, j, math.hypot(predicted[i]["x"] - human[j]["x"],
                                     predicted[i]["y"] - human[j]["y"]))
                     for i, j in zip(pi, hi)]
            candidates.append(pairs)
    return min(candidates, key=lambda pairs: sum(pair[2] for pair in pairs))


def score_localization(labels, points_by_frame):
    """Both methods call this with the same merged human frame/label set."""
    visible = matched = 0
    hits = {str(t): 0 for t in THRESHOLDS}
    audit = []
    for key in sorted(labels, key=int):
        humans = [(paw, labels[key][paw]) for paw in p.PAWS
                  if labels[key][paw]["status"] == "visible"]
        points = points_by_frame.get(int(key), [])
        pairs = minimum_distance_assignment(points, [h for _, h in humans])
        visible += len(humans)
        matched += len(pairs)
        for threshold in THRESHOLDS:
            hits[str(threshold)] += sum(d <= threshold for _, _, d in pairs)
        by_human = {j: (i, d) for i, j, d in pairs}
        audit.append({
            "frameIndex": int(key), "predictedPaws": len(points),
            "visibleLabels": [{
                "paw": paw,
                "predictionIndex": by_human[j][0] if j in by_human else None,
                "distancePx": by_human[j][1] if j in by_human else None,
            } for j, (paw, _) in enumerate(humans)],
        })
    return {
        "visibleHumanPawLabels": visible,
        "visibleLabelsReceivingPredictions": matched,
        "visibleLabelsMissingPredictions": visible - matched,
        "predictionAvailability": matched / visible if visible else None,
        "localization": {str(t): {
            "thresholdPx": t, "hits": hits[str(t)],
            "misses": visible - hits[str(t)], "denominator": visible,
            "recall": hits[str(t)] / visible if visible else None,
        } for t in THRESHOLDS},
        "frames": audit,
    }


def raw_points(frame):
    """Use saved raw hind-paw coordinates with no confidence threshold.

    A failed dog detection yields no predictions. Finite saved coordinates,
    including low-score or out-of-image points, remain raw predictions.
    """
    if not frame["detectionSuccess"]:
        return []
    points = {point["name"]: point for point in frame["keypoints"]}
    return [points[name] for name in p.ANATOMICAL if name in points]


def recovered_points(recovered, frame_count):
    """Only associated, non-null points in accepted recovery segments count."""
    output = {}
    for segment in recovered["segments"]:
        for frame in segment["result"]["frames"]:
            index = frame["frameIndex"]
            p.require(type(index) is int and 0 <= index < frame_count,
                      "Tracker frame outside source video")
            p.require(index not in output, "Overlapping recovered frames")
            points = [t["point"] for t in frame["physicalTracks"]
                      if t["status"] == "associated" and t["point"] is not None]
            p.require(len(points) <= 2, "Tracker emitted more than two paws")
            output[index] = points
    return output


def evaluate_sequence(sequence, meta, predictions, labels, duplicates,
                      association, recovery):
    frames = predictions["frames"]
    # Existing algorithms receive no labels and cannot mutate saved input data.
    recovered = recovery.recover_segments(copy.deepcopy(frames), meta["frameWidth"],
                                         meta["frameHeight"], association.associate)
    methods = {
        "rawRTMPose": {f["frameIndex"]: raw_points(f) for f in frames},
        "trackerRecovery": recovered_points(recovered, len(frames)),
    }
    scores = {}
    for name, points in methods.items():
        score = score_localization(labels, points)
        available = sum(len(v) for v in points.values())
        score["wholeVideo"] = {
            "frames": len(frames), "predictedPaws": available,
            "pawOpportunities": 2 * len(frames),
            "coverage": available / (2 * len(frames)),
        }
        scores[name] = score
    return {
        "group": sequence["group"], "split": sequence["split"],
        "exploratory": sequence["group"] == "dog02",
        "annotatedFrames": len(labels),
        "duplicateCompletedLabelsRemoved": duplicates,
        "modelExposedAnnotatedFrames": sum(f["modelExposed"] for f in labels.values()),
        "acceptedRecoverySegments": len(recovered["segments"]),
        "methods": scores,
    }


def load_algorithm(name, path):
    # Avoid importing the application integration or the V1 evaluator.
    spec = importlib.util.spec_from_file_location(name, path)
    p.require(spec is not None and spec.loader is not None, f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_report(root=ROOT):
    config_path = root / "training/paw_annotation_sources.json"
    config = p.load_json(config_path)
    p.require(config.get("schemaVersion") == 1, "Unsupported source configuration")
    schema = p.load_json(p.checked(root, config["keypointSchema"]))
    names = [k["id"] for k in schema["keypoints"]]
    prepared, seen = [], set()
    for sequence in config["sequences"]:
        paths = {k: p.checked(root, sequence[k])
                 for k in ("metadata", "predictions", "video")}
        meta, pred = p.load_json(paths["metadata"]), p.load_json(paths["predictions"])
        p.validate_split(sequence, meta, seen)
        p.require(meta["videoSha256"] == sequence["video"]["sha256"] and
                  meta["predictionSha256"] == sequence["predictions"]["sha256"],
                  "Source provenance mismatch")
        p.validate_predictions(pred, meta, names)
        docs = [(a["path"], p.load_json(p.checked(root, a)))
                for a in sequence["annotations"]]
        labels, _, duplicates = p.merge_annotations(docs, meta, pred["frames"])
        prepared.append((sequence, meta, pred, labels, duplicates))
    p.require({s[0]["group"] for s in prepared} == set(p.SPLITS),
              "Both Dalmatian and exploratory Dog02 are required")
    hashes = {name: p.digest(root / path) for name, path in ALGORITHMS.items()}
    association = load_algorithm("paw_localization_v2_association", root / ALGORITHMS["association"])
    recovery = load_algorithm("paw_localization_v2_recovery", root / ALGORITHMS["recovery"])
    return {
        "benchmarkVersion": 2, "evaluation": "identity-agnostic localization",
        "limitations": [LIMITATION,
            "Dog02 is exploratory, not an independent confirmatory evaluation.",
            "Existing human labels may have been model-exposed; exposure counts are reported."],
        "policies": {
            "assignment": "Per-frame maximum-cardinality one-to-one minimum total Euclidean distance; deterministic input-order ties; no threshold-based rematching",
            "thresholdsPx": list(THRESHOLDS), "thresholdComparison": "distance <= threshold",
            "denominator": "All visible merged human A/B labels, identical for both methods; absent predictions are misses",
            "rawRTMPose": "Successful detection, saved finite hind-paw coordinates, no score or image-bound filtering",
            "trackerRecovery": "Existing defaults; associated non-null points from accepted recovery segments only; unresolved/rejected/absent frames are misses",
            "predictionAvailability": "One-to-one assigned visible labels / all visible labels, regardless of distance",
            "wholeVideoCoverage": "Available paw points / (2 * all saved video frames), including unannotated frames",
        },
        "sourceManifestSha256": p.digest(config_path), "sourceManifest": config,
        "algorithmHashes": hashes, "evaluatorSha256": p.digest(Path(__file__)),
        "annotationUtilitiesSha256": p.digest(Path(p.__file__)),
        "results": [evaluate_sequence(*args, association, recovery) for args in prepared],
    }


def write_report(output, report):
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects V1 baselines and every other existing file.
    with output.open("x") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        p.require(not args.output.exists(), f"Output exists; choose a new path: {args.output}")
        report = build_report()
        write_report(args.output, report)
    except (p.ValidationError, OSError, KeyError, TypeError) as exc:
        print(f"Paw localization V2 failed: {exc}", file=sys.stderr)
        return 2
    for result in report["results"]:
        print(result["group"], "(exploratory)" if result["exploratory"] else "(train)")
        for method, score in result["methods"].items():
            print(f"  {method}: " + ", ".join(
                f"recall@{t}px={score['localization'][str(t)]['recall']}" for t in THRESHOLDS)
                + f", availability={score['predictionAvailability']}, "
                + f"whole-video coverage={score['wholeVideo']['coverage']}")
    print(LIMITATION)
    print("Saved:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
