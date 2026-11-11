"""One offline original-Dog02 pilot; no models, human labels or tracker execution.

Run from the repository root with the existing OpenCV environment:
    .venv-canine-v2/bin/python scripts/run_ground_evidence_pilot.py \
        --output reports/dog02-ground-evidence-v1
The output directory must be new. Inputs are verified and never rewritten.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from petlens_gait.ground import extract_ground_evidence, validate_alignment
from training import gait_event_review as review
from training import prepare_paw_annotations as provenance


def verified_inputs(root=ROOT):
    """Reuse strict original decoding/native PTS/pixel checks, without review data."""
    sources_path = root / "training/paw_annotation_sources.json"
    sources = provenance.load_json(sources_path)
    entry = next(s for s in sources["sequences"] if s["group"] == "dog02")
    pred_path = provenance.checked(root, entry["predictions"])
    video_path = provenance.checked(root, entry["video"])
    metadata_path = provenance.checked(root, entry["metadata"])
    source_manifest = root / review.MANIFEST
    # session() loads only the frame/source manifest; no review annotations.
    manifest, encoded, source_manifest_hash = review.session(root=root, group="gait-dog02")
    native = manifest["datasets"]["gait-dog02"]
    conversion_path = root / "tmp/rtmpose-test/multi-video-evaluation/inputs/dog02-conversion.json"
    inference_path = pred_path.parent / "manifest.json"
    identity_path = root / "tmp/rtmpose-test/paw-tracking-experiment/dog02-identity-association/associated-results.json"
    scene_path = root / "configs/dog02-ground-scene-v1.json"
    prediction = provenance.load_json(pred_path)
    conversion = provenance.load_json(conversion_path)
    inference = provenance.load_json(inference_path)
    derivative_meta = provenance.load_json(metadata_path)
    saved_identity = provenance.load_json(identity_path)
    scene = provenance.load_json(scene_path)
    provenance.require(conversion["outputSha256"] == provenance.digest(video_path) ==
        inference["videoSha256"] == derivative_meta["videoSha256"], "Derivative lineage hash mismatch")
    provenance.require(inference["status"] == "complete" and
        inference["artifacts"]["predictions.json"] == provenance.digest(pred_path) ==
        derivative_meta["predictionSha256"] == saved_identity["sourceSha256"],
        "Prediction/identity lineage hash mismatch")
    provenance.require((derivative_meta["frameWidth"], derivative_meta["frameHeight"],
        derivative_meta["sourceFrameCount"]) == (native["frameWidth"], native["frameHeight"], native["frameCount"]),
        "Saved prediction metadata source dimensions/count mismatch")
    provenance.require(saved_identity["originalPredictions"] == prediction,
                       "Saved identity raw predictions mismatch")
    validate_alignment(prediction, native, conversion)
    images = [cv2.imdecode(np.frombuffer(encoded["gait-dog02"][i], np.uint8), cv2.IMREAD_COLOR)
              for i in range(native["frameCount"])]
    paths = [sources_path, pred_path, video_path, metadata_path, source_manifest,
        root / native["sourceVideo"]["path"], conversion_path, inference_path, identity_path, scene_path,
        root / "src/petlens_gait/ground.py", root / "src/petlens_gait/events.py",
        root / "src/petlens_gait/metrics.py", root / "training/gait_event_review.py",
        root / "training/prepare_paw_annotations.py", Path(__file__)]
    fingerprints = {str(path.relative_to(root)): provenance.digest(path) for path in paths}
    lineage = dict(sourceManifestSha256=source_manifest_hash,
        sourceVideo=deepcopy(native["sourceVideo"]), predictionPath=str(pred_path.relative_to(root)),
        predictionSha256=provenance.digest(pred_path), derivativePath=str(video_path.relative_to(root)),
        derivativeSha256=provenance.digest(video_path),
        conversion=deepcopy(conversion), fileSha256=fingerprints,
        alignment="All 60 original native PTS/frame indices/dimensions match the documented derivative and saved predictions within 1 microsecond. Lossy derivative pixels are not asserted identical to the original.",
        originalPixelVerification="Full existing source manifest comparison passed for all original frames, including PNG and decoded-pixel hashes.",
        savedIdentityPolicy="Read-only saved arbitrary IDs 0/1; unresolved slots abstain. No human A/B mapping and no tracker rerun.",
        humanAnnotationsUsed=False, newModelInference=False,
        attribution=native["attribution"])
    return images, native, prediction, scene, saved_identity, lineage


def diagnostic_image(images, prediction, report):
    """Measurement overlay, not an annotation interface or ground-contact label."""
    panels = []
    raw = report["detector"]["rawObservations"]
    scene = report["sceneCalibration"]
    for i in (0, len(images)//2, len(images)-1):
        frame = images[i].copy()
        motion = report["groundMotion"][i]
        ground = motion["groundPolygon"]
        if ground is not None:
            cv2.polylines(frame, [np.rint(ground).astype(np.int32)], True, (0, 220, 0), 2)
        cv2.polylines(frame, [np.rint(scene["backgroundPolygon"]).astype(np.int32)], True, (255, 180, 0), 2)
        for polygon in scene["exclusionPolygons"]:
            cv2.polylines(frame, [np.asarray(polygon, np.int32)], True, (0, 0, 255), 2)
        box = prediction["frames"][i].get("boundingBoxXyxy")
        if box:
            cv2.rectangle(frame, tuple(map(round, box[:2])), tuple(map(round, box[2:])), (0, 0, 255), 2)
        for point in prediction["frames"][i].get("keypoints", []):
            if point["name"].endswith("_paw"):
                cv2.circle(frame, (round(point["x"]), round(point["y"])), 5, (0, 220, 255), 2)
        for row in raw:
            if row["frameIndex"] == i and row["pawPosition"]:
                p = row["pawPosition"]
                cv2.putText(frame, f'ID {row["identity"]}', (round(p["x"])+5, round(p["y"])-8),
                    cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
        registration = motion["registration"]
        ground_fit = registration.get("ground") or {}
        for match in ground_fit.get("matches", []):
            if match["inlier"]:
                cv2.circle(frame, tuple(map(round, match["current"])), 2, (255, 255, 0), -1)
        banner = np.zeros((100, frame.shape[1], 3), np.uint8)
        lines = [f'Original frame {i} | {motion["timestampSeconds"]:.6f} s | candidates only',
            f'Ground registration: {registration["reliable"]} | inliers: {ground_fit.get("inlierCount", 0)} | paw states: UNKNOWN',
            'Green: floor texture ROI; blue: background check; red: excluded actors; yellow: raw model paws',
            'No calibrated paw-height line. Floor overlap is not contact or clearance.']
        for j, line in enumerate(lines):
            cv2.putText(banner, line, (10, 20 + 23*j), cv2.FONT_HERSHEY_SIMPLEX, .48, (240, 240, 240), 1)
        panels.append(cv2.resize(np.vstack([frame, banner]), (768, 515)))
    return np.hstack(panels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        parser.error("Output directory already exists; choose a new directory to preserve prior work")
    cv2.setNumThreads(1)
    images, native, pred, scene, saved_identity, lineage = verified_inputs()
    report = extract_ground_evidence(images, native, pred, scene, saved_identity)
    report["provenance"] = lineage
    report["environment"] = dict(python=platform.python_version(), opencv=cv2.__version__,
        numpy=np.__version__, opencvThreads=1, ransacSeed=0,
        ffprobe=subprocess.check_output(["ffprobe", "-version"], text=True).splitlines()[0])
    report["rawPredictions"] = deepcopy(pred)
    for relative, expected in lineage["fileSha256"].items():
        provenance.require(provenance.digest(ROOT / relative) == expected,
                           f"Input changed during pilot: {relative}")
    target.mkdir(parents=True, exist_ok=False)
    image = diagnostic_image(images, pred, report)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    provenance.require(ok, "Diagnostic image encoding failed")
    (target / "diagnostic.jpg").write_bytes(encoded.tobytes())
    report["visualDiagnostic"] = dict(path="diagnostic.jpg",
        sha256=provenance.digest(target / "diagnostic.jpg"), sourceFrames=[0, 30, 59])
    with (target / "diagnostic.json").open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps(report["summary"], indent=2))
    print(f"Diagnostic report: {target / 'diagnostic.json'}")


if __name__ == "__main__":
    main()
