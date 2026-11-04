"""Prepare human paw references and anatomically reviewed AP-10K COCO labels.

Offline only: saved predictions are audit context, never label targets. Run with
python -m training.prepare_paw_annotations --output-dir <new-directory>.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "training/paw_annotation_sources.json"
PAWS = ("A", "B")
ANATOMICAL = ("left_back_paw", "right_back_paw")
IDENTITY = "Reviewer-defined physical hind paws A/B; no anatomical LH/RH mapping."
SPLITS = {"dalmatian": "train", "dog02": "exploratory_evaluation"}


class ValidationError(ValueError):
    """Unsafe or incompatible annotation inputs."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def label_digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValidationError(f"{path}: nonfinite JSON value {value}")
    try:
        return json.loads(path.read_text(), object_pairs_hook=pairs,
                          parse_constant=reject_constant)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{path}: {exc}") from exc


def checked(root, record):
    path = (root / record["path"]).resolve()
    require(path.is_relative_to(root.resolve()), "Source path escapes repository root")
    require(path.is_file(), f"Missing source: {record['path']}")
    require(digest(path) == record["sha256"], f"SHA256 mismatch: {record['path']}")
    return path


def validate_predictions(pred, meta, names):
    require(isinstance(pred, dict) and isinstance(meta, dict), "Expected source JSON objects")
    require(meta.get("schemaVersion") == 1, "Unsupported source manifest schema")
    require(pred.get("detectorModel") == "PekingU/rtdetr_r50vd_coco_o365",
            "Incompatible detector model")
    require(pred.get("poseModel") == "OpenMMLab RTMPose-m AP-10K" and
            pred.get("keypointSchema") == "AP-10K, 17 keypoints",
            "Incompatible animal pose schema/model")
    require(pred.get("videoSha256") == meta["videoSha256"], "Video identity mismatch")
    require(pred.get("rawPredictionsWereSmoothedOrCorrected") is False,
            "Expected unchanged saved predictions")
    frames = pred.get("frames")
    require(isinstance(frames, list) and len(frames) == meta["sourceFrameCount"] ==
            pred.get("frameCount"), "Prediction frame count mismatch")
    require(finite(pred.get("fps")) and pred["fps"] > 0 and
            math.isclose(pred["fps"], meta["fps"], rel_tol=1e-6), "FPS mismatch")
    require(all(type(meta.get(k)) is int and meta[k] > 0
                for k in ("frameWidth", "frameHeight", "sourceFrameCount")),
            "Invalid source dimensions/count")
    require(isinstance(meta.get("frames"), list), "Missing source manifest frames")
    for index, frame in enumerate(meta["frames"]):
        require(isinstance(frame, dict) and type(frame.get("frameIndex")) is int and
                frame["frameIndex"] == index and finite(frame.get("timestampSeconds")),
                "Source manifest frames must be unique, consecutive and ordered")
    manifest_frames = {f["frameIndex"]: f for f in meta["frames"]}
    require(len(manifest_frames) == len(frames), "Source manifest frame count mismatch")
    previous = -1
    for index, frame in enumerate(frames):
        require(isinstance(frame, dict), "Invalid prediction frame")
        require(type(frame.get("frameIndex")) is int and frame["frameIndex"] == index,
                "Prediction frames must be unique, consecutive and ordered from zero")
        t = frame.get("timestampSeconds")
        require(finite(t) and t >= 0 and t > previous, "Invalid/nonmonotonic timestamp")
        require(index in manifest_frames and math.isclose(
            t, manifest_frames[index]["timestampSeconds"], abs_tol=1e-6),
            "Prediction/source manifest timestamp mismatch")
        previous = t
        require(type(frame.get("detectionSuccess")) is bool, "Missing detection status")
        points = frame.get("keypoints")
        require(isinstance(points, list) and all(isinstance(p, dict) for p in points),
                "Invalid keypoint list")
        point_names = [p.get("name") for p in points]
        require(len(point_names) == len(set(point_names)) and set(point_names) <= set(names),
                "Duplicate/unknown AP-10K keypoint")
        for point in points:
            require(all(finite(point.get(k)) for k in ("x", "y", "rawScore")),
                    "Invalid saved keypoint coordinate/confidence")


def merge_annotations(documents, meta, predictions):
    """Deduplicate identical paw labels; conflicting completed labels fail closed."""
    merged, origins, duplicates = {}, {}, 0
    for path, doc in documents:
        require(isinstance(doc, dict), f"{path}: expected annotation object")
        require(doc.get("schemaVersion") == 1 and
                doc.get("annotationType") == "physical-hind-tracks",
                f"{path}: expected physical-hind-tracks schema 1")
        for key in ("datasetId", "videoSha256", "predictionSha256"):
            require(doc.get(key) == meta[key], f"{path}: {key} mismatch")
        require(doc.get("identityDefinition") == IDENTITY,
                f"{path}: unknown physical identity definition")
        for key in ("evaluationId", "evaluationSplit"):
            if key in doc:
                require(doc[key] == meta.get(key), f"{path}: {key} mismatch")
        require(isinstance(doc.get("frames"), dict), f"{path}: missing annotation frames")
        for key, frame in doc["frames"].items():
            require(key.isdecimal() and str(int(key)) == key and
                    0 <= int(key) < len(predictions), f"{path}: invalid frame index {key}")
            index = int(key)
            require(isinstance(frame, dict), "Invalid annotation frame object")
            require(type(frame.get("frameIndex", index)) is int and
                    frame.get("frameIndex", index) == index, "Annotation frameIndex mismatch")
            if "timestampSeconds" in frame:
                require(finite(frame["timestampSeconds"]) and math.isclose(
                    frame["timestampSeconds"], predictions[index]["timestampSeconds"],
                    abs_tol=1e-6), "Annotation timestamp mismatch")
            require(type(frame.get("modelExposed")) is bool, "Missing model exposure status")
            continuity = frame.get("continuity", {})
            require(isinstance(continuity, dict) and set(continuity) <= set(PAWS) and
                    all(v in ("unreviewed", "start", "continuous", "uncertain", "broken")
                        for v in continuity.values()), "Invalid continuity state")
            for paw in PAWS:
                label = frame.get(paw, {})
                require(isinstance(label, dict) and label.get("status") in
                        ("visible", "occluded", "uncertain", "ambiguous", "unmarked"),
                        "Invalid physical paw status")
                if label["status"] == "visible":
                    require(all(finite(label.get(c)) for c in ("x", "y")) and
                            0 <= label["x"] < meta["frameWidth"] and
                            0 <= label["y"] < meta["frameHeight"],
                            "Invalid visible human coordinate")
                else:
                    require(label.get("x") is None and label.get("y") is None,
                            "Nonvisible physical labels must have null coordinates")
            target = merged.setdefault(key, {})
            origins.setdefault(key, []).append(path)
            for field, value in frame.items():
                if field in PAWS:
                    old = target.get(field)
                    if old and old["status"] != "unmarked" and value["status"] != "unmarked":
                        require(old == value, f"Conflicting duplicate label: frame {key} {field}")
                        duplicates += 1
                    elif old is None or old["status"] == "unmarked":
                        target[field] = copy.deepcopy(value)
                elif field == "modelExposed":
                    target[field] = target.get(field, False) or value
                else:
                    require(field not in target or target[field] == value,
                            f"Conflicting annotation metadata: frame {key} {field}")
                    target[field] = copy.deepcopy(value)
    return merged, origins, duplicates


def validate_split(sequence, meta, seen):
    group, split = sequence["group"], sequence["split"]
    require(group in SPLITS and split == SPLITS[group],
            "Split leakage: dog02 is exploratory evaluation only; Dalmatian is training")
    require(f"petlens-{group}-" in meta["datasetId"], "Dataset/group identity mismatch")
    for identity in (group, meta["datasetId"], meta["videoSha256"], meta["predictionSha256"]):
        require(identity not in seen, f"Duplicate sequence or train/evaluation leakage: {identity}")
        seen.add(identity)


def extract_images(video, frames, meta, destination):
    """Decode source video, never run a detector/pose model or use overlay images."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    require(cap.isOpened(), f"Cannot decode source video: {video}")
    saved = {}
    index = 0
    try:
        require(math.isclose(cap.get(cv2.CAP_PROP_FPS), meta["fps"], rel_tol=1e-4),
                "Decoded video FPS mismatch")
        while True:
            ok, image = cap.read()
            if not ok:
                break
            require(image.shape[:2] == (meta["frameHeight"], meta["frameWidth"]),
                    "Decoded video dimensions mismatch")
            require(index < meta["sourceFrameCount"], "Decoded video has excess frames")
            require(math.isclose(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000,
                                meta["frames"][index]["timestampSeconds"], abs_tol=1e-4),
                    "Decoded video timestamp mismatch")
            if str(index) in frames:
                path = destination / f"{index:06}.png"
                require(cv2.imwrite(str(path), image), f"Cannot save image: {path}")
                saved[index] = digest(path)
            index += 1
    finally:
        cap.release()
    require(index == meta["sourceFrameCount"], "Decoded video frame count mismatch")
    return saved, cv2.__version__


def apply_reviews(records, reviews):
    """Only explicit per-frame human anatomical decisions unlock AP-10K channels."""
    require(isinstance(reviews, dict) and reviews.get("schemaVersion") == 1,
            "Unsupported anatomical review schema")
    index = {(r["datasetId"], r["frameIndex"], paw): r
             for r in records for paw in PAWS}
    accepted, seen = {}, set()
    require(isinstance(reviews.get("reviews"), list), "Missing anatomical review list")
    for entry in reviews["reviews"]:
        require(isinstance(entry, dict) and type(entry.get("frameIndex")) is int,
                "Invalid anatomical review/frame index")
        key = (entry.get("datasetId"), entry.get("frameIndex"), entry.get("physicalPaw"))
        require(key in index and key not in seen, "Unknown/duplicate anatomical review")
        seen.add(key)
        record = index[key]
        label = record["human"][key[2]]
        require(entry.get("physicalLabelSha256") == label_digest(label) and
                entry.get("imageSha256") == record["imageSha256"], "Stale anatomical review")
        name = entry.get("anatomicalKeypoint")
        if name is None:
            continue  # Unfilled templates are not anatomical assertions.
        require(name in ANATOMICAL, "Invalid anatomical hind-paw channel")
        require(all(isinstance(entry.get(k), str) and entry[k].strip()
                    for k in ("reviewer", "evidence")), "Anatomical review needs reviewer/evidence")
        require(label["status"] == "visible", "Anatomical mapping has no visible human coordinate")
        accepted[key] = copy.deepcopy(entry)
    for record in records:
        names = [accepted[(record["datasetId"], record["frameIndex"], p)]["anatomicalKeypoint"]
                 for p in PAWS if (record["datasetId"], record["frameIndex"], p) in accepted]
        require(len(names) == len(set(names)), "Both physical paws assigned to one anatomical channel")
    return accepted


def coco_export(records, reviews, names, split):
    images, annotations = [], []
    for record in records:
        if record["split"] != split:
            continue
        image_id = len(images) + 1
        w, h = record["width"], record["height"]
        images.append(dict(id=image_id, file_name=record["fileName"], width=w, height=h,
                           video_id=record["datasetId"], frame_id=record["frameIndex"]))
        points, sources = [0, 0, 0] * len(names), []
        for paw in PAWS:
            review = reviews.get((record["datasetId"], record["frameIndex"], paw))
            if review is None:
                continue
            label = record["human"][paw]
            offset = names.index(review["anatomicalKeypoint"]) * 3
            points[offset:offset + 3] = [label["x"], label["y"], 2]
            sources.append(review)
        if sources:
            annotations.append(dict(id=len(annotations) + 1, image_id=image_id, category_id=1,
                                    keypoints=points, num_keypoints=len(sources),
                                    bbox=[0, 0, w, h], area=w * h, iscrowd=0,
                                    bbox_source="full_image_extent_not_an_annotated_dog_box",
                                    anatomical_reviews=sources))
    return dict(info={"description": "Human-only partial AP-10K labels; zero triplets are unlabeled",
                      "split": split, "model_selection_allowed": split == "train"},
                images=images, annotations=annotations,
                categories=[dict(id=1, name="dog", supercategory="animal", keypoints=names,
                                 skeleton=[])])


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def build(root, config_path, output, review_path=None):
    root, config_path, output = root.resolve(), config_path.resolve(), output.resolve()
    require(not output.exists(), f"Output already exists; use a new directory: {output}")
    config = load_json(config_path)
    require(isinstance(config, dict) and config.get("schemaVersion") == 1,
            "Unsupported source configuration")
    schema_path = checked(root, config["keypointSchema"])
    names = [k["id"] for k in load_json(schema_path)["keypoints"]]
    require(len(names) == 17 and names[13] == ANATOMICAL[0] and names[16] == ANATOMICAL[1],
            "Invalid AP-10K channel order")
    sequences, seen = [], set()
    require(isinstance(config.get("sequences"), list), "Missing source sequences")
    for spec in config["sequences"]:
        paths = {k: checked(root, spec[k]) for k in ("video", "predictions", "metadata")}
        meta, pred = load_json(paths["metadata"]), load_json(paths["predictions"])
        validate_split(spec, meta, seen)
        require(spec["video"]["sha256"] == meta["videoSha256"] and
                spec["predictions"]["sha256"] == meta["predictionSha256"],
                "Source video/prediction provenance mismatch")
        validate_predictions(pred, meta, names)
        docs = [(a["path"], load_json(checked(root, a))) for a in spec["annotations"]]
        if "originalVideo" in spec:
            original = checked(root, spec["originalVideo"])
            require(all(d.get("originalVideoSha256", digest(original)) ==
                        spec["originalVideo"]["sha256"] for _, d in docs),
                    "Original video provenance mismatch")
        merged, origins, duplicates = merge_annotations(docs, meta, pred["frames"])
        sequences.append((spec, paths, meta, pred, docs, merged, origins, duplicates))
    require({s[0]["group"] for s in sequences} == set(SPLITS),
            "Both Dalmatian and dog02 sources are required")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".paw-data-", dir=output.parent))
    try:
        records, originals, counts = [], [], {}
        for spec, paths, meta, pred, docs, merged, origins, duplicates in sequences:
            destination = staging / "images" / spec["group"]
            destination.mkdir(parents=True)
            image_hashes, cv_version = extract_images(paths["video"], merged, meta, destination)
            statuses = Counter()
            for key in sorted(merged, key=int):
                index = int(key)
                frame = merged[key]
                statuses.update(frame[p]["status"] for p in PAWS)
                records.append(dict(datasetId=meta["datasetId"], group=spec["group"],
                    split=spec["split"], modelSelectionAllowed=spec["split"] == "train",
                    frameIndex=index, timestampSeconds=pred["frames"][index]["timestampSeconds"],
                    width=meta["frameWidth"], height=meta["frameHeight"],
                    fileName=f"images/{spec['group']}/{index:06}.png",
                    imageSha256=image_hashes[index], human=frame, annotationSources=origins[key],
                    savedPredictionContext=pred["frames"][index],
                    anatomicalIdentity="unverified_until_explicit_human_review"))
            originals.extend(dict(path=p, document=d) for p, d in docs)
            counts[spec["group"]] = dict(split=spec["split"], frames=len(merged),
                physicalStatusCounts=dict(statuses), duplicateCompletedPawLabelsRemoved=duplicates,
                framesWithVisibleLabels=sum(any(f[p]["status"] == "visible" for p in PAWS)
                                           for f in merged.values()),
                bothPawsVisibleFrames=sum(all(f[p]["status"] == "visible" for p in PAWS)
                                         for f in merged.values()),
                decodedSourceFrames=meta["sourceFrameCount"])
        review_doc = load_json(review_path) if review_path else {"schemaVersion": 1, "reviews": []}
        reviews = apply_reviews(records, review_doc)
        template = {"schemaVersion": 1, "instructions":
            "Per-frame human anatomical adjudication only. Null means unreviewed. "
            "Use original images and temporal context, never RTMPose label names or screen side. "
            "Nonvisible paws have no localization target; do not guess coordinates.", "reviews": []}
        for record in records:
            for paw in PAWS:
                label = record["human"][paw]
                if label["status"] == "unmarked":
                    continue
                template["reviews"].append(dict(datasetId=record["datasetId"],
                    frameIndex=record["frameIndex"], physicalPaw=paw,
                    physicalLabelSha256=label_digest(label), imageSha256=record["imageSha256"],
                    anatomicalKeypoint=None, reviewer="", evidence=""))
        write_json(staging / "physical-reference.json", {"schemaVersion": 1,
            "identityDefinition": IDENTITY,
            "groundTruth": "human physical A/B coordinates, independent of model predictions",
            "records": records})
        write_json(staging / "original-annotations.json", originals)
        write_json(staging / "anatomical-review-template.json", template)
        write_json(staging / "accepted-anatomical-reviews.json", list(reviews.values()))
        (staging / ".gitignore").write_text("# Regenerate lossless video frames locally.\nimages/\n")
        for split in SPLITS.values():
            coco = coco_export(records, reviews, names, split)
            write_json(staging / f"{split}.coco.json", coco)
            group = next(g for g, s in SPLITS.items() if s == split)
            counts[group]["exportedAnatomicalPoints"] = sum(a["num_keypoints"] for a in coco["annotations"])
            counts[group]["exportedPoseInstances"] = len(coco["annotations"])
            counts[group]["rejectionReasons"] = dict(Counter(
                "anatomical_identity_unverified" if r["human"][paw]["status"] == "visible"
                else "no_coordinate_" + r["human"][paw]["status"]
                for r in records if r["split"] == split for paw in PAWS
                if (r["datasetId"], r["frameIndex"], paw) not in reviews))
        manifest = dict(schemaVersion=1, sourceConfiguration=config,
            sourceConfigurationSha256=digest(config_path), builderSha256=digest(Path(__file__)),
            reviewSha256=digest(review_path) if review_path else None,
            opencvVersion=cv_version, counts=counts,
            modelSelectionPolicy="dog02 excluded from training and model selection; exploratory evaluation only",
            coordinatePolicy="Human coordinates are never snapped to, filtered by, or filled from predictions",
            visibilityPolicy="COCO v=2 only for visible, anatomically reviewed human points; "
                "all other channels [0,0,0] with zero loss weight; no v=1 inferred coordinates",
            limitations=["No verified anatomical targets exist in the original physical A/B exports",
                "COCO bbox is full image extent, not a dog crop annotation",
                "No independent validation sequence or validated stride measurements",
                "AP-10K COCO data layout only; no RTMPose training/configuration or checkpoint conversion tested"],
            outputSha256={str(p.relative_to(staging)): digest(p)
                          for p in sorted(staging.rglob("*")) if p.is_file()})
        write_json(staging / "manifest.json", manifest)
        staging.rename(output)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--anatomical-reviews", type=Path)
    args = parser.parse_args()
    try:
        manifest = build(ROOT, args.sources, args.output_dir, args.anatomical_reviews)
    except (ValidationError, OSError, KeyError, TypeError) as exc:
        print(f"Paw annotation preparation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
