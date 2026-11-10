"""Reproducible, annotation-validated paw-tracking evaluation."""
import json
import math
from pathlib import Path

from training import prepare_paw_annotations as p
from petlens_gait.integration import _load_module

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "tmp/rtmpose-test/paw-tracking-experiment"
OUTPUT = ROOT / "tmp/rtmpose-test/paw-tracking-experiment/multi-video-baseline.json"
THRESHOLD_FRACTION = 0.05


def evaluate(sequence, associate, recovery):
    group = sequence["group"]
    meta = p.load_json(p.checked(ROOT, sequence["metadata"]))
    predictions = p.load_json(p.checked(ROOT, sequence["predictions"]))
    p.checked(ROOT, sequence["video"])

    schema = p.load_json(p.checked(ROOT, CONFIG["keypointSchema"]))
    names = schema.get("keypoints", schema)
    if isinstance(names, list):
        names = [item["annotation_name"] if isinstance(item, dict) else item for item in names]
    elif isinstance(names, dict):
        names = list(names)

    p.validate_predictions(predictions, meta, names)
    documents = [
        (record["path"], p.load_json(p.checked(ROOT, record)))
        for record in sequence["annotations"]
    ]
    labels, _, duplicates = p.merge_annotations(
        documents, meta, predictions["frames"]
    )

    width, height = meta["frameWidth"], meta["frameHeight"]
    threshold = THRESHOLD_FRACTION * math.hypot(width, height)
    recovered = recovery.recover_segments(
        predictions["frames"], width, height, associate.associate
    )

    tracks_by_frame = {}
    segments = []
    for segment in recovered["segments"]:
        frame_map = {
            frame["frameIndex"]: frame
            for frame in segment["result"]["frames"]
        }
        tracks_by_frame.update(frame_map)
        segments.append({
            "start": segment["startFrame"],
            "end": segment["endFrame"],
            "coverage": segment["coverage"],
            "frameMap": frame_map,
        })

    associated = sum(
        track["status"] == "associated" and track["point"] is not None
        for frame in tracks_by_frame.values()
        for track in frame["physicalTracks"]
    )
    visible = [
        (int(index), paw, frame[paw])
        for index, frame in labels.items()
        for paw in ("A", "B")
        if frame[paw]["status"] == "visible"
    ]

    matched = 0
    correct = 0
    errors = []
    evaluable = 0
    segment_summaries = []

    for segment in segments:
        comparisons = []
        for index, paw, human in visible:
            frame = segment["frameMap"].get(index)
            if frame is None:
                continue
            for track in frame["physicalTracks"]:
                if track["status"] != "associated" or track["point"] is None:
                    continue
                point = track["point"]
                distance = math.hypot(
                    point["x"] - human["x"],
                    point["y"] - human["y"]
                )
                comparisons.append((paw, track["identity"], distance))

        # One mapping for the entire segment; never remap per frame.
        scores = []
        for mapping in ({"A": 0, "B": 1}, {"A": 1, "B": 0}):
            hits = sum(
                identity == mapping[paw] and distance <= threshold
                for paw, identity, distance in comparisons
            )
            scores.append((hits, mapping))
        best = max(scores, key=lambda item: item[0])
        # A tie cannot establish which physical identity is which.
        identifiable = scores[0][0] != scores[1][0]
        if identifiable:
            mapping = best[1]
            for index, paw, human in visible:
                if index not in segment["frameMap"]:
                    continue
                evaluable += 1
                track = next(
                    (t for t in segment["frameMap"][index]["physicalTracks"]
                     if t["identity"] == mapping[paw]),
                    None
                )
                if track is None or track["status"] != "associated" or track["point"] is None:
                    continue
                matched += 1
                distance = math.hypot(
                    track["point"]["x"] - human["x"],
                    track["point"]["y"] - human["y"]
                )
                errors.append(distance)
                correct += distance <= threshold

        segment_summaries.append({
            "startFrame": segment["start"],
            "endFrame": segment["end"],
            "identityMappingIdentifiable": identifiable,
            "mapping": best[1] if identifiable else None,
            "correctWithinThreshold": best[0],
        })

    n = len(predictions["frames"])
    return {
        "group": group,
        "split": sequence["split"],
        "frames": n,
        "acceptedSegments": len(segments),
        "associatedPaws": associated,
        "totalPawOpportunities": 2 * n,
        "wholeVideoCoverage": associated / (2 * n),
        "annotatedFrames": len(labels),
        "duplicateAnnotationLabels": duplicates,
        "visibleHumanPawLabels": len(visible),
        "identityEvaluableVisibleLabels": evaluable,
        "associatedEvaluableLabels": matched,
        "correctIdentityAndLocalization": correct,
        "identityAndLocalizationRecall": correct / len(visible) if visible else None,
        "correctAmongAssociatedEvaluable": correct / matched if matched else None,
        "meanMappedLocalizationErrorPx": sum(errors) / len(errors) if errors else None,
        "segments": segment_summaries,
        "thresholdPixels": threshold,
    }


CONFIG = p.load_json(ROOT / "training/paw_annotation_sources.json")
associate_path = EXPERIMENT / "dog02-identity-association/associate.py"
recovery_path = EXPERIMENT / "segment-recovery-v2/recovery.py"
associate = _load_module("benchmark_association", associate_path)
recovery = _load_module("benchmark_recovery", recovery_path)

results = [evaluate(seq, associate, recovery) for seq in CONFIG["sequences"]]
report = {
    "benchmarkVersion": 1,
    "method": "Fixed segment-level identity permutation; 5% image-diagonal localization tolerance",
    "algorithmHashes": {
        "association": p.digest(associate_path),
        "recovery": p.digest(recovery_path),
    },
    "sourceManifestSha256": p.digest(
        ROOT / "training/paw_annotation_sources.json"
    ),
    "results": results,
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, indent=2) + "\n")

for result in results:
    print(
        f"{result['group']}: coverage={result['wholeVideoCoverage']:.1%}, "
        f"visible GT={result['visibleHumanPawLabels']}, "
        f"evaluable={result['identityEvaluableVisibleLabels']}, "
        f"correct={result['correctIdentityAndLocalization']}, "
        f"recall={result['identityAndLocalizationRecall']}"
    )
print("Saved:", OUTPUT)
