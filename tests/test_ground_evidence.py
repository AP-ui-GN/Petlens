"""Focused synthetic image tests; no inference, downloads or human gait labels."""

import copy
import hashlib
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, "src")

from petlens_gait.ground import (
    compensated_motion, extract_ground_evidence, ground_proximity,
    register_ground, validate_alignment, validate_scene,
)


def fixture(count=2):
    rng = np.random.default_rng(42)
    texture = cv2.GaussianBlur(rng.integers(0, 256, (300, 400, 3), dtype=np.uint8), (3, 3), 0)
    frames = [dict(frameIndex=i, timestampSeconds=i/12, originalPts=i,
                   originalTimeBase="1/12", pixelSha256=hashlib.sha256(texture.tobytes()).hexdigest())
              for i in range(count)]
    meta = dict(frameCount=count, frameWidth=400, frameHeight=300,
                sourceVideo=dict(sha256="source"), frames=frames)
    scene = dict(sourceSha256="source", referenceFrameIndex=0,
        referencePixelSha256=frames[0]["pixelSha256"], imageSize=[400, 300],
        surfaceType="static", foregroundCoverageSupported=True,
        groundPolygon=[[20, 215], [380, 215], [380, 290], [20, 290]],
        backgroundPolygon=[[20, 10], [380, 10], [380, 65], [20, 65]],
        exclusionPolygons=[], basis="Synthetic independent scene geometry", clearanceReference=None)
    predictions = dict(poseModel="OpenMMLab RTMPose-m AP-10K", frameCount=count, frames=[])
    for i in range(count):
        points = [dict(name=name, x=x, y=y, rawScore=0.9) for name, x, y in (
            ("left_shoulder", 120, 100), ("right_shoulder", 120, 110),
            ("left_hip", 220, 100), ("right_hip", 220, 110),
            ("left_back_paw", 180, 199.5), ("right_back_paw", 200, 199.5))]
        predictions["frames"].append(dict(frameIndex=i, timestampSeconds=i/12, keypoints=points,
            detectionSuccess=True, dogCandidateCount=1, boundingBoxXyxy=[100, 80, 250, 205]))
    lineage = dict(sourceSha256="source", frames=count, width=400, height=300,
                   sourceTimestamps=[i/12 for i in range(count)], convertedTimestamps=[i/12 for i in range(count)])
    return texture, meta, scene, predictions, lineage


def identity(predictions):
    return dict(originalPredictions=copy.deepcopy(predictions), frames=[
        dict(frameIndex=f["frameIndex"], timestampSeconds=f["timestampSeconds"], physicalTracks=[
            dict(identity=i, status="associated", reasons=[], sourceName=name,
                 point=copy.deepcopy(next(p for p in f["keypoints"] if p["name"] == name)))
            for i, name in enumerate(("left_back_paw", "right_back_paw"))])
        for f in predictions["frames"]])


@pytest.mark.parametrize("dx,dy", [(0, 0), (4, -2), (-3, 3), (1.5, -0.5)])
def test_known_camera_background_translation(dx, dy):
    a, _, scene, pred, _ = fixture()
    b = cv2.warpAffine(a, np.array([[1., 0, dx], [0, 1., dy]]), (400, 300))
    result = register_ground(a, b, *pred["frames"], scene)
    assert result["reliable"], result["reasons"]
    assert np.array(result["transform"])[:, 2] == pytest.approx([dx, dy], abs=0.12)
    for name in ("ground", "background"):
        assert result[name]["inlierCount"] >= 12
        assert result[name]["inlierFraction"] >= 0.75
        assert result[name]["p95ResidualPixels"] <= 1.5
        assert result[name]["hullCoverage"] >= 0.1
        assert result[name]["matches"]


def test_moving_paw_under_camera_motion_uses_ground_compensated_displacement():
    a, _, scene, pred, _ = fixture()
    b = cv2.warpAffine(a, np.array([[1., 0, 4], [0, 1., 2]]), (400, 300))
    reg = register_ground(a, b, *pred["frames"], scene)
    stationary = compensated_motion(dict(x=150, y=200), dict(x=154, y=202), reg["transform"], .1, 100)
    moving = compensated_motion(dict(x=150, y=200), dict(x=164, y=202), reg["transform"], .1, 100)
    assert stationary["speedTorsoLengthsPerSecond"] < .01
    assert moving["displacementPixels"] == pytest.approx([10, 0], abs=.1)
    assert moving["speedTorsoLengthsPerSecond"] == pytest.approx(1, abs=.01)


def test_static_ground_and_moving_foreground_do_not_drive_registration():
    a, _, scene, pred, _ = fixture()
    b = a.copy()
    cv2.rectangle(b, (110, 90), (240, 200), (255, 255, 255), -1)
    reg = register_ground(a, b, *pred["frames"], scene)
    assert reg["reliable"]
    assert np.array(reg["transform"])[:, 2] == pytest.approx([0, 0], abs=.01)
    assert compensated_motion(dict(x=100, y=190), dict(x=110, y=190), reg["transform"], .1, 100)["speedTorsoLengthsPerSecond"] == pytest.approx(1)


@pytest.mark.parametrize("failure", ["texture", "moving", "unknown", "no_ground", "no_background", "no_masks", "no_box"])
def test_unsupported_ground_registration_abstains(failure):
    a, _, scene, pred, _ = fixture()
    if failure == "texture":
        a[:] = 100
    elif failure in ("moving", "unknown"):
        scene["surfaceType"] = failure
    elif failure == "no_ground":
        scene["groundPolygon"] = None
    elif failure == "no_background":
        scene["backgroundPolygon"] = None
    elif failure == "no_masks":
        scene["foregroundCoverageSupported"] = False
    else:
        pred["frames"][1]["detectionSuccess"] = False
    result = register_ground(a, a.copy(), *pred["frames"], scene)
    assert not result["reliable"]
    assert result["transform"] is None
    assert result["reasons"]


def test_coherently_moving_floor_is_rejected_by_independent_background():
    a, _, scene, pred, _ = fixture()
    shifted = cv2.warpAffine(a, np.array([[1., 0, 5], [0, 1., 0]]), (400, 300))
    b = a.copy()
    b[210:] = shifted[210:]
    result = register_ground(a, b, *pred["frames"], scene)
    assert result["ground"]["reliable"] and result["background"]["reliable"]
    assert not result["reliable"]
    assert "ground_background_motion_disagreement" in result["reasons"]


def test_only_a_small_cluster_of_features_is_insufficient():
    texture, _, scene, pred, _ = fixture()
    image = np.full_like(texture, 100)
    image[230:255, 50:100] = texture[230:255, 50:100]
    result = register_ground(image, image.copy(), *pred["frames"], scene)
    assert not result["reliable"]
    assert any("coverage" in r or "few" in r for r in result["reasons"])


def support_line(scene):
    scene["clearanceReference"] = dict(line=[[20, 200], [380, 200]],
        pawCorridor=[[80, 150], [260, 150], [260, 205], [80, 205]],
        independentOfPawPredictions=True, sameDepthSupported=True, uncertaintyPixels=.2,
        basis="Known synthetic side-view support geometry, independent of paw pixels")


def test_floor_region_membership_never_becomes_clearance():
    _, _, scene, _, _ = fixture()
    p = ground_proximity(dict(x=100, y=250), 100, scene, True)
    assert p["floorRegionOverlap"] is True
    assert p["clearanceTorsoLengths"] is None
    assert not p["reliableForEvents"]


def test_independent_support_line_provides_only_projected_image_proximity():
    _, _, scene, _, _ = fixture()
    support_line(scene)
    result = ground_proximity(dict(x=180, y=188), 100, scene, True)
    assert result["reliableForEvents"]
    assert result["clearanceTorsoLengths"] == pytest.approx(.12)
    assert result["uncertaintyTorsoLengths"] == pytest.approx(.002)


@pytest.mark.parametrize("failure", ["geometry", "depth", "paw_derived", "uncertainty", "scale", "outside"])
def test_missing_or_unreliable_clearance_reference_abstains(failure):
    _, _, scene, _, _ = fixture()
    support_line(scene)
    ref = scene["clearanceReference"]
    if failure == "depth": ref["sameDepthSupported"] = False
    if failure == "paw_derived": ref["independentOfPawPredictions"] = False
    if failure == "uncertainty": ref["uncertaintyPixels"] = 5
    result = ground_proximity(dict(x=390 if failure == "outside" else 180, y=188),
        None if failure == "scale" else 100, scene, failure != "geometry")
    assert not result["reliableForEvents"]
    assert result["clearanceTorsoLengths"] is None


@pytest.mark.parametrize("failure", ["hash", "count", "dimension", "prediction_time", "source_time", "derivative_time", "frame_order"])
def test_source_derivative_and_prediction_alignment_fail_closed(failure):
    _, meta, _, pred, lineage = fixture()
    validate_alignment(pred, meta, lineage)
    if failure == "hash": lineage["sourceSha256"] = "wrong"
    if failure == "count": lineage["frames"] = 3
    if failure == "dimension": lineage["width"] = 500
    if failure == "prediction_time": pred["frames"][1]["timestampSeconds"] += .01
    if failure == "source_time": lineage["sourceTimestamps"][1] += .01
    if failure == "derivative_time": lineage["convertedTimestamps"][1] += .01
    if failure == "frame_order": pred["frames"].reverse()
    with pytest.raises(ValueError): validate_alignment(pred, meta, lineage)


@pytest.mark.parametrize("field,value", [("sourceSha256", "wrong"), ("referencePixelSha256", "wrong"),
    ("referenceFrameIndex", 1), ("imageSize", [100, 100]),
    ("groundPolygon", [[0, 0], [400, 10], [20, 20]])])
def test_scene_calibration_is_bound_to_source_pixels(field, value):
    _, meta, scene, _, _ = fixture()
    scene[field] = value
    with pytest.raises(ValueError): validate_scene(scene, meta)


def test_real_input_adapter_integrates_detector_and_preserves_all_inputs():
    a, meta, scene, pred, lineage = fixture(10)
    support_line(scene)
    # Explicit synthetic paw motion and independent support geometry.
    for i, frame in enumerate(pred["frames"]):
        swing = i >= 5
        for p in frame["keypoints"]:
            if p["name"] in ("left_back_paw", "right_back_paw"):
                p["y"] = 188 if swing else 199.5
                p["x"] += i * 3 if swing else 0
    saved = identity(pred)
    images = [a.copy() for _ in range(10)]
    # Draw the observed moving paw, entirely within the excluded foreground box.
    for image, frame in zip(images, pred["frames"]):
        for p in frame["keypoints"][-2:]:
            cv2.circle(image, (round(p["x"]), round(p["y"])), 3, (0, 0, 255), -1)
    before = copy.deepcopy((meta, scene, pred, lineage, saved))
    pixels_before = [image.tobytes() for image in images]
    validate_alignment(pred, meta, lineage)
    report = extract_ground_evidence(images, meta, pred, scene, saved)
    assert report["summary"]["reliableGroundRegistrations"] == 9
    assert report["summary"]["candidateEvents"] == 2
    assert all(e["eventType"] == "candidate_lift_off" for e in report["detector"]["events"])
    assert all(e["uncertainty"]["biologicallyVerified"] is False for e in report["detector"]["events"])
    assert all(row["timestampSeconds"] == meta["frames"][row["frameIndex"]]["timestampSeconds"]
               for row in report["detector"]["rawObservations"])
    assert (meta, scene, pred, lineage, saved) == before
    assert [image.tobytes() for image in images] == pixels_before


def test_missing_pose_and_unresolved_identity_remain_unknown_without_reconnection():
    a, meta, scene, pred, _ = fixture(4)
    saved = identity(pred)
    for track in saved["frames"][2]["physicalTracks"]:
        track.update(status="unresolved", point=None, sourceName=None, reasons=["competing_identity_paths"])
    report = extract_ground_evidence([a.copy() for _ in range(4)], meta, pred, scene, saved)
    rows = report["detector"]["rawObservations"]
    assert all(not row["identityContinuous"] for row in rows if row["frameIndex"] in (0, 2, 3))
    assert all(row["pawPosition"] is None for row in rows if row["frameIndex"] == 2)
    assert report["summary"]["stateCounts"] == {"UNKNOWN": 8}
    assert report["summary"]["candidateEvents"] == 0


def test_missing_saved_identity_never_uses_model_names_as_physical_continuity():
    a, meta, scene, pred, _ = fixture(3)
    report = extract_ground_evidence([a.copy() for _ in range(3)], meta, pred, scene)
    assert report["summary"]["stateCounts"] == {"UNKNOWN": 6}
    assert all(not row["identityContinuous"] for row in report["detector"]["rawObservations"])
    assert report["groundMotion"][1]["modelChannelMotionDiagnostics"]["left_back_paw"] is not None


def test_missing_detection_and_pose_break_registration_and_remain_unknown():
    a, meta, scene, pred, _ = fixture(4)
    pred["frames"][1].update(detectionSuccess=False, keypoints=[])
    report = extract_ground_evidence([a.copy() for _ in range(4)], meta, pred, scene)
    assert report["summary"]["reliableGroundRegistrations"] == 0
    assert not report["groundMotion"][3]["geometryReliable"]
    assert "calibration_chain_broken" in report["groundMotion"][3]["registration"]["reasons"]
    assert report["summary"]["stateCounts"] == {"UNKNOWN": 8}


def test_unbounded_raw_pose_scores_are_not_clipped_into_confidence():
    a, meta, scene, pred, _ = fixture(3)
    for frame in pred["frames"]:
        frame["keypoints"][-1]["rawScore"] = 1.2
    report = extract_ground_evidence([a.copy() for _ in range(3)], meta, pred, scene, identity(pred))
    rows = [o for o in report["detector"]["rawObservations"] if o["identity"] == 1]
    assert all(o["rawPoseScore"] == 1.2 and o["poseConfidence"] is None for o in rows)
    assert all("raw_pose_score_outside_detector_contract" in o["extractionReasons"] for o in rows)


def test_saved_identity_cannot_supply_modified_coordinates():
    a, meta, scene, pred, _ = fixture()
    saved = identity(pred)
    saved["frames"][1]["physicalTracks"][0]["point"]["x"] += 1
    with pytest.raises(ValueError, match="exact unchanged prediction"):
        extract_ground_evidence([a.copy(), a.copy()], meta, pred, scene, saved)
