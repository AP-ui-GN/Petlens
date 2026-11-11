"""Offline 2D ground evidence, with conservative registration and abstention.

One fixed method: masked Shi–Tomasi corners, forward/backward pyramidal LK,
RANSAC similarity registration, spatial coverage and an independent static
background check. Both regions must agree; a coherently moving floor alone is
not evidence of camera motion. Scene geometry and static-surface assumptions
must be supplied from image inspection, independently of paw predictions.

No physical contact, 3D height, neural inference or identity tracking is done.
Saved physical-track hypotheses are consumed unchanged; unresolved identities
remain unresolved. A pixel floor region supplies overlap only, never clearance.
An optional independently calibrated side-view support line additionally needs
a supported depth corridor and bounded calibration uncertainty.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import math

import cv2
import numpy as np

from petlens_gait.events import _finite, detect_events
from petlens_gait.metrics import anatomical_reference


PAWS = ("left_front_paw", "right_front_paw", "left_back_paw", "right_back_paw")


@dataclass(frozen=True)
class GroundRules:
    """Shared engineering gates; units are pixels unless explicitly named.

    These defaults are fixed on synthetic scenes, not optimized against Dog02.
    Similarity motion is intentionally limited: perspective/parallax or local
    surface motion that fails the independent-region check causes abstention.
    """

    max_corners: int = 400
    corner_quality: float = 0.01
    corner_separation: int = 8
    lk_window: int = 15
    lk_levels: int = 2
    max_lk_error: float = 20.0
    max_forward_backward_error: float = 0.75
    ransac_error: float = 1.5
    min_matches: int = 12
    min_inlier_fraction: float = 0.75
    max_median_residual: float = 0.75
    max_p95_residual: float = 1.5
    min_hull_coverage: float = 0.10
    max_background_disagreement: float = 1.5
    foreground_padding_fraction: float = 0.02
    min_body_raw_score: float = 0.5
    max_reference_uncertainty_torso: float = 0.01


DEFAULT_GROUND_RULES = GroundRules()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_alignment(predictions, source_meta, conversion):
    """Bind legacy derivative predictions to original native frame references.

    File hashes must first be checked by the caller. This checks the documented
    one-to-one derivative lineage, dimensions, all source/derivative times and
    prediction ordering. It never adds metadata to the legacy predictions.
    """
    frames = source_meta["frames"]
    count = source_meta["frameCount"]
    _require(conversion["sourceSha256"] == source_meta["sourceVideo"]["sha256"],
             "Conversion original source hash mismatch")
    _require(count == len(frames) == conversion["frames"] == predictions["frameCount"]
             == len(predictions["frames"]), "Source/prediction frame count mismatch")
    _require((conversion["width"], conversion["height"]) ==
             (source_meta["frameWidth"], source_meta["frameHeight"]),
             "Derivative/source dimensions mismatch")
    _require(predictions.get("poseModel") == "OpenMMLab RTMPose-m AP-10K",
             "Expected saved AP-10K RTMPose predictions")
    for field in ("sourceTimestamps", "convertedTimestamps"):
        _require(len(conversion[field]) == count, "Conversion timestamp count mismatch")
    previous = -1
    for i, (source, prediction) in enumerate(zip(frames, predictions["frames"])):
        _require(type(prediction.get("frameIndex")) is int and
                 prediction["frameIndex"] == source["frameIndex"] == i,
                 "Prediction/source frame index mismatch")
        timestamp = source["timestampSeconds"]
        _require(_finite(timestamp) and timestamp > previous and timestamp >= 0,
                 "Invalid source timestamp")
        previous = timestamp
        for value in (prediction.get("timestampSeconds"),
                      conversion["sourceTimestamps"][i], conversion["convertedTimestamps"][i]):
            _require(_finite(value) and math.isclose(value, timestamp, rel_tol=0, abs_tol=1e-6),
                     "Prediction/conversion/source timestamp mismatch")
        names = [p["name"] for p in prediction.get("keypoints", [])]
        _require(len(names) == len(set(names)), "Duplicate prediction keypoints")


def validate_scene(scene, source_meta):
    _require(scene["sourceSha256"] == source_meta["sourceVideo"]["sha256"],
             "Scene calibration source hash mismatch")
    _require(scene["referenceFrameIndex"] == 0 and
             scene["referencePixelSha256"] == source_meta["frames"][0]["pixelSha256"],
             "Scene calibration pixel/frame reference mismatch")
    _require(scene["imageSize"] == [source_meta["frameWidth"], source_meta["frameHeight"]],
             "Scene calibration image dimensions mismatch")
    _require(bool(scene.get("basis")), "Scene geometry needs an independent image basis")
    width, height = scene["imageSize"]
    polygons = [scene.get("groundPolygon"), scene.get("backgroundPolygon")]
    polygons += scene.get("exclusionPolygons", [])
    for polygon in polygons:
        if polygon is None:
            continue
        a = np.asarray(polygon, dtype=float)
        _require(a.ndim == 2 and a.shape[0] >= 3 and a.shape[1] == 2 and
                 np.isfinite(a).all() and (a >= 0).all() and
                 (a[:, 0] < width).all() and (a[:, 1] < height).all(),
                 "Invalid calibration polygon")
        _require(abs(cv2.contourArea(a.astype(np.float32))) > 1, "Degenerate calibration polygon")


def _warp(points, matrix):
    a = np.asarray(points, dtype=np.float64)
    return a @ np.asarray(matrix)[:, :2].T + np.asarray(matrix)[:, 2]


def _polygon_mask(shape, polygon, exclusions, box, config):
    mask = np.zeros(shape[:2], np.uint8)
    if polygon is None:
        return mask
    cv2.fillPoly(mask, [np.rint(polygon).astype(np.int32)], 255)
    for excluded in exclusions:
        cv2.fillPoly(mask, [np.rint(excluded).astype(np.int32)], 0)
    padding = config.foreground_padding_fraction * math.hypot(*shape[:2])
    x0, y0, x1, y1 = box
    cv2.rectangle(mask, (math.floor(x0 - padding), math.floor(y0 - padding)),
                  (math.ceil(x1 + padding), math.ceil(y1 + padding)), 0, -1)
    # Prevent LK windows sampling foreground or non-ground polygon edges.
    return cv2.erode(mask, np.ones((config.lk_window, config.lk_window), np.uint8))


def _valid_box(frame, shape):
    box = frame.get("boundingBoxXyxy")
    return (frame.get("detectionSuccess") is True and frame.get("dogCandidateCount") == 1
            and isinstance(box, list) and len(box) == 4 and all(_finite(x) for x in box)
            and 0 <= box[0] < box[2] <= shape[1] and 0 <= box[1] < box[3] <= shape[0])


def _register_region(previous, current, before_mask, after_mask, config):
    result = {"reliable": False, "reasons": [], "cornerCount": 0, "matchCount": 0,
              "inlierCount": 0, "candidateTransform": None, "matches": []}
    corners = cv2.goodFeaturesToTrack(previous, maxCorners=config.max_corners,
        qualityLevel=config.corner_quality, minDistance=config.corner_separation,
        blockSize=7, mask=before_mask)
    if corners is None:
        result["reasons"].append("too_few_ground_features")
        return result
    result["cornerCount"] = len(corners)
    options = dict(winSize=(config.lk_window, config.lk_window), maxLevel=config.lk_levels,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    following, status, error = cv2.calcOpticalFlowPyrLK(previous, current, corners, None, **options)
    if following is None:
        result["reasons"].append("optical_flow_unavailable")
        return result
    # Do not pass nonfinite points into the reverse-flow OpenCV call.
    valid_forward = np.isfinite(following.reshape(-1, 2)).all(axis=1) & status.ravel().astype(bool)
    if not valid_forward.any():
        result["reasons"].append("too_few_consistent_matches")
        return result
    p = corners[valid_forward]
    q = following[valid_forward]
    forward_error = error.ravel()[valid_forward]
    back, reverse_status, _ = cv2.calcOpticalFlowPyrLK(current, previous, q, None, **options)
    if back is None:
        result["reasons"].append("reverse_flow_unavailable")
        return result
    p, q, back = p.reshape(-1, 2), q.reshape(-1, 2), back.reshape(-1, 2)
    fb = np.linalg.norm(p - back, axis=1)
    accepted = (reverse_status.ravel().astype(bool) & np.isfinite(back).all(axis=1)
                & (fb <= config.max_forward_backward_error)
                & np.isfinite(forward_error) & (forward_error <= config.max_lk_error))
    xy = np.rint(q).astype(np.int32)
    inside = ((xy[:, 0] >= 0) & (xy[:, 0] < current.shape[1]) &
              (xy[:, 1] >= 0) & (xy[:, 1] < current.shape[0]))
    accepted &= inside
    indices = np.flatnonzero(inside)
    accepted[indices] &= after_mask[xy[indices, 1], xy[indices, 0]] > 0
    p, q, fb = p[accepted], q[accepted], fb[accepted]
    result["matchCount"] = len(p)
    if len(p) < config.min_matches:
        result["reasons"].append("too_few_consistent_matches")
        return result
    cv2.setRNGSeed(0)
    matrix, inliers = cv2.estimateAffinePartial2D(p, q, method=cv2.RANSAC,
        ransacReprojThreshold=config.ransac_error, maxIters=2000,
        confidence=0.99, refineIters=10)
    if matrix is None or not np.isfinite(matrix).all():
        result["reasons"].append("registration_failed")
        return result
    inliers = inliers.ravel().astype(bool)
    residuals = np.linalg.norm(_warp(p, matrix) - q, axis=1)
    count = int(inliers.sum())
    result.update(candidateTransform=matrix.tolist(), inlierCount=count,
                  inlierFraction=count / len(p))
    if count < config.min_matches:
        result["reasons"].append("too_few_inliers")
    if count:
        result.update(medianResidualPixels=float(np.median(residuals[inliers])),
                      p95ResidualPixels=float(np.percentile(residuals[inliers], 95)),
                      medianForwardBackwardErrorPixels=float(np.median(fb[inliers])))
        coverage = abs(cv2.contourArea(cv2.convexHull(p[inliers]))) / max(1, np.count_nonzero(before_mask))
        result["hullCoverage"] = float(coverage)
        if coverage < config.min_hull_coverage:
            result["reasons"].append("insufficient_spatial_coverage")
        if (result["medianResidualPixels"] > config.max_median_residual or
                result["p95ResidualPixels"] > config.max_p95_residual):
            result["reasons"].append("high_registration_residual")
    if count / len(p) < config.min_inlier_fraction:
        result["reasons"].append("mixed_or_nonrigid_motion")
    result["matches"] = [dict(previous=a.tolist(), current=b.tolist(), inlier=bool(ok),
        forwardBackwardErrorPixels=float(f), residualPixels=float(r))
        for a, b, ok, f, r in zip(p, q, inliers, fb, residuals)]
    result["reliable"] = not result["reasons"]
    return result


def register_ground(previous, current, before_prediction, after_prediction,
                    scene, config=DEFAULT_GROUND_RULES):
    """Estimate previous-to-current ground similarity, without assuming zero motion.

    Scene polygons are in the previous frame. A first fit locates their current
    positions; final accepted tracks must lie inside the warped polygon and
    outside current foreground masks. No foreground pixels may supply features.
    An independent background fit must predict the same motion over the ground.
    """
    result = {"reliable": False, "transform": None, "reasons": [],
              "ground": None, "background": None}
    _require(previous.shape == current.shape and previous.dtype == current.dtype == np.uint8,
             "Registration requires equal-size uint8 images")
    if scene.get("surfaceType") != "static":
        result["reasons"].append("moving_or_unsupported_surface")
    if scene.get("foregroundCoverageSupported") is not True:
        result["reasons"].append("foreground_coverage_unsupported")
    if scene.get("groundPolygon") is None or scene.get("backgroundPolygon") is None:
        result["reasons"].append("ground_or_independent_background_region_unavailable")
    if not all(_valid_box(p, previous.shape) for p in (before_prediction, after_prediction)):
        result["reasons"].append("foreground_detection_unavailable")
    if result["reasons"]:
        return result
    a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY) if previous.ndim == 3 else previous
    b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if current.ndim == 3 else current
    exclusions = scene.get("exclusionPolygons", [])
    for name, field in (("ground", "groundPolygon"), ("background", "backgroundPolygon")):
        before_mask = _polygon_mask(a.shape, scene[field], exclusions,
                                    before_prediction["boundingBoxXyxy"], config)
        # Current mask initially permits only known scene pixels outside actors.
        # Polygon membership is checked again using the estimated transform.
        after_mask = _polygon_mask(b.shape, [[0, 0], [b.shape[1]-1, 0],
            [b.shape[1]-1, b.shape[0]-1], [0, b.shape[0]-1]], exclusions,
            after_prediction["boundingBoxXyxy"], config)
        fit = _register_region(a, b, before_mask, after_mask, config)
        if fit["reliable"]:
            warped = _warp(scene[field], fit["candidateTransform"]).astype(np.float32)
            if any(cv2.pointPolygonTest(warped, tuple(match["current"]), False) < 0
                   for match in fit["matches"] if match["inlier"]):
                fit["reasons"].append("tracks_left_calibrated_region")
                fit["reliable"] = False
        result[name] = fit
        if not fit["reliable"]:
            result["reasons"].extend(name + ":" + reason for reason in fit["reasons"])
    if result["reasons"]:
        return result
    ground = np.asarray(result["ground"]["candidateTransform"])
    background = np.asarray(result["background"]["candidateTransform"])
    # Compare at ground vertices, including extrapolation from the independent
    # background region: a floor and wall moving differently is unsupported.
    disagreement = float(np.max(np.linalg.norm(
        _warp(scene["groundPolygon"], ground) - _warp(scene["groundPolygon"], background), axis=1)))
    result["backgroundDisagreementPixels"] = disagreement
    if disagreement > config.max_background_disagreement:
        result["reasons"].append("ground_background_motion_disagreement")
        return result
    result.update(reliable=True, transform=ground.tolist())
    return result


def ground_proximity(point, scale, scene, geometry_reliable, config=DEFAULT_GROUND_RULES):
    """Image-space proximity only; floor polygon overlap is never paw height."""
    result = {"floorRegionOverlap": None, "clearanceTorsoLengths": None,
              "reliableForEvents": False, "reasons": []}
    if not geometry_reliable or scene.get("groundPolygon") is None:
        result["reasons"].append("ground_geometry_unavailable_or_unreliable")
        return result
    if point is None or not all(_finite(point.get(k)) for k in ("x", "y")):
        result["reasons"].append("paw_position_unavailable")
        return result
    xy = (point["x"], point["y"])
    result["floorRegionOverlap"] = cv2.pointPolygonTest(
        np.asarray(scene["groundPolygon"], np.float32), xy, False) >= 0
    reference = scene.get("clearanceReference")
    if reference is None:
        result["reasons"].append("floor_region_is_not_a_paw_height_reference")
        return result
    if (reference.get("independentOfPawPredictions") is not True or
            reference.get("sameDepthSupported") is not True or not reference.get("basis")):
        result["reasons"].append("support_line_depth_or_calibration_unsupported")
        return result
    if not _finite(scale) or scale < 1:
        result["reasons"].append("body_scale_unavailable")
        return result
    uncertainty = reference.get("uncertaintyPixels")
    if (not _finite(uncertainty) or uncertainty < 0 or
            uncertainty / scale > config.max_reference_uncertainty_torso):
        result["reasons"].append("support_line_uncertainty_too_large")
        return result
    corridor = np.asarray(reference["pawCorridor"], np.float32)
    line = np.asarray(reference["line"], np.float64)
    _require(line.shape == (2, 2) and np.isfinite(line).all() and
             corridor.ndim == 2 and corridor.shape[1] == 2 and len(corridor) >= 3 and
             np.isfinite(corridor).all(), "Invalid support-line calibration")
    vector = line[1] - line[0]
    length = float(np.linalg.norm(vector))
    _require(length > 1 and vector[0] > 0, "Support line must run left to right")
    if cv2.pointPolygonTest(corridor, xy, False) < 0:
        result["reasons"].append("paw_outside_calibrated_depth_corridor")
        return result
    delta = np.asarray(xy) - line[0]
    clearance = (vector[1] * delta[0] - vector[0] * delta[1]) / length / scale
    result.update(clearanceTorsoLengths=float(clearance), reliableForEvents=True,
                  uncertaintyTorsoLengths=uncertainty / scale)
    return result


def compensated_motion(before, after, transform, dt, current_scale):
    """Ground-compensated displacement in current pixels / current torso / second."""
    if (transform is None or before is None or after is None or not _finite(dt) or dt <= 0
            or not _finite(current_scale) or current_scale < 1):
        return None
    if not all(_finite(p.get(k)) for p in (before, after) for k in ("x", "y")):
        return None
    expected = _warp([[before["x"], before["y"]]], transform)[0]
    residual = np.array([after["x"], after["y"]]) - expected
    return {"displacementPixels": residual.tolist(),
            "speedTorsoLengthsPerSecond": float(np.linalg.norm(residual) / dt / current_scale)}


def _body_scale(prediction, shape, config):
    points = {p["name"]: p for p in prediction.get("keypoints", [])}
    for name in ("left_shoulder", "right_shoulder", "left_hip", "right_hip"):
        p = points.get(name, {})
        if (not all(_finite(p.get(k)) for k in ("x", "y", "rawScore"))
                or p["rawScore"] < config.min_body_raw_score
                or not (0 <= p["x"] < shape[1] and 0 <= p["y"] < shape[0])):
            return None
    reference = anatomical_reference(prediction)
    return reference["torsoLengthPixels"] if reference is not None else None


def _accepted_track(track, prediction):
    if (track.get("status") != "associated" or track.get("reasons") or
            track.get("sourceName") not in PAWS or track.get("point") is None):
        return False
    point = next((p for p in prediction.get("keypoints", []) if p["name"] == track["sourceName"]), None)
    _require(point is not None and track["point"] == point,
             "Saved identity track must select an exact unchanged prediction")
    return all(_finite(point.get(k)) for k in ("x", "y", "rawScore"))


def extract_ground_evidence(images, source_meta, predictions, scene, saved_identity=None,
                            config=DEFAULT_GROUND_RULES):
    """Extract evidence and call detect_events; no inferred identity reconnection.

    Callers must verify file hashes and derivative alignment before this function.
    Source times are always native PTS, with prediction times retained separately.
    A failed registration loses cumulative calibration; no stationary-camera
    fallback or automatic reinitialization follows. Subsequent pairs may retain
    diagnostic fits, but accepted geometry/motion stays unavailable.
    """
    validate_scene(scene, source_meta)
    count = source_meta["frameCount"]
    _require(len(images) == len(source_meta["frames"]) == len(predictions["frames"]) == count,
             "Image/source/prediction frame count mismatch")
    ids = (0, 1)
    identity_frames = saved_identity["frames"] if saved_identity is not None else []
    if saved_identity is not None:
        _require(saved_identity.get("originalPredictions") == predictions,
                 "Saved identity prediction payload mismatch")
        _require(len(identity_frames) == count, "Saved identity frame count mismatch")
        for i, frame in enumerate(identity_frames):
            _require(frame["frameIndex"] == i and math.isclose(frame["timestampSeconds"],
                source_meta["frames"][i]["timestampSeconds"], rel_tol=0, abs_tol=1e-6),
                "Saved identity source alignment mismatch")
            _require(sorted(t["identity"] for t in frame["physicalTracks"]) == list(ids),
                     "Expected saved physical hind-paw IDs 0/1")
    cumulative = np.eye(3)
    calibration_error_pixels = 0.0
    geometry_reliable = scene.get("surfaceType") == "static"
    observations, motion_frames, before_tracks = [], [], {}
    source_id = source_meta["sourceVideo"]["sha256"]

    for i, (image, native, prediction) in enumerate(zip(images, source_meta["frames"], predictions["frames"])):
        _require(image.shape[:2] == (source_meta["frameHeight"], source_meta["frameWidth"]),
                 "Decoded source dimensions mismatch")
        _require(native["frameIndex"] == prediction["frameIndex"] == i and
                 math.isclose(native["timestampSeconds"], prediction["timestampSeconds"],
                              rel_tol=0, abs_tol=1e-6), "Prediction/native source alignment mismatch")
        current_scene = deepcopy(scene)
        for field in ("groundPolygon", "backgroundPolygon"):
            if scene.get(field) is not None:
                current_scene[field] = _warp(scene[field], cumulative[:2]).tolist()
        if scene.get("clearanceReference"):
            for field in ("line", "pawCorridor"):
                current_scene["clearanceReference"][field] = _warp(
                    scene["clearanceReference"][field], cumulative[:2]).tolist()
            current_scene["clearanceReference"]["uncertaintyPixels"] *= float(np.linalg.norm(cumulative[:2, 0]))
            current_scene["clearanceReference"]["uncertaintyPixels"] += calibration_error_pixels
        registration = {"reliable": False, "transform": None, "reasons": ["no_previous_frame"]}
        if i:
            registration = register_ground(images[i-1], image, predictions["frames"][i-1],
                                           prediction, previous_scene, config)
            if not geometry_reliable:
                registration["reasons"].append("calibration_chain_broken")
                registration.update(reliable=False, transform=None)
            if registration["reliable"]:
                step = np.vstack([registration["transform"], [0, 0, 1]])
                calibration_error_pixels = (calibration_error_pixels * float(np.linalg.norm(step[:2, 0]))
                    + registration["ground"]["p95ResidualPixels"])
                cumulative = step @ cumulative
                for field in ("groundPolygon", "backgroundPolygon"):
                    if scene.get(field) is not None:
                        current_scene[field] = _warp(scene[field], cumulative[:2]).tolist()
                if scene.get("clearanceReference"):
                    for field in ("line", "pawCorridor"):
                        current_scene["clearanceReference"][field] = _warp(
                            scene["clearanceReference"][field], cumulative[:2]).tolist()
                    current_scene["clearanceReference"]["uncertaintyPixels"] = (
                        scene["clearanceReference"]["uncertaintyPixels"] * float(np.linalg.norm(cumulative[:2, 0]))
                        + calibration_error_pixels)
            else:
                geometry_reliable = False
        scale = _body_scale(prediction, image.shape, config)
        raw_points = {p["name"]: p for p in prediction.get("keypoints", [])}
        records = identity_frames[i]["physicalTracks"] if identity_frames else [
            dict(identity=k, status="unresolved", reasons=["saved_identity_unavailable"], point=None)
            for k in ids]
        model_motion = {}
        if i and registration["reliable"]:
            old = {p["name"]: p for p in predictions["frames"][i-1].get("keypoints", [])}
            dt = native["timestampSeconds"] - source_meta["frames"][i-1]["timestampSeconds"]
            for name in PAWS:
                model_motion[name] = compensated_motion(old.get(name), raw_points.get(name),
                    registration["transform"], dt, scale)
        motion_frames.append({**deepcopy(native), "registration": registration,
            "geometryReliable": geometry_reliable, "groundPolygon": current_scene.get("groundPolygon"),
            "bodyScalePixels": scale, "modelChannelMotionDiagnostics": model_motion,
            "modelChannelWarning": "Same model label across frames is not physical paw continuity."})
        next_tracks = {}
        for track in records:
            accepted = _accepted_track(track, prediction)
            point = track["point"] if accepted else None
            identity = track["identity"]
            previous_track = before_tracks.get(identity)
            continuous = bool(accepted and previous_track is not None)
            score = point.get("rawScore") if point else None
            # RTMPose raw scores can exceed one. Never clamp/normalize them into
            # a confidence compatible with the detector's existing [0,1] gate.
            confidence = score if _finite(score) and 0 <= score <= 1 else None
            motion = None
            if continuous and registration["reliable"]:
                dt = native["timestampSeconds"] - source_meta["frames"][i-1]["timestampSeconds"]
                motion = compensated_motion(previous_track, point, registration["transform"], dt, scale)
            proximity = ground_proximity(point, scale, current_scene, geometry_reliable, config)
            extraction_reasons = list(registration["reasons"]) + list(track.get("reasons", []))
            extraction_reasons += proximity["reasons"]
            if not continuous:
                extraction_reasons.append("physical_identity_continuity_unsupported")
            if point is not None and confidence is None:
                extraction_reasons.append("raw_pose_score_outside_detector_contract")
            if scale is None:
                extraction_reasons.append("body_scale_unavailable")
            observations.append({
                "sourceId": source_id, "identity": identity, "segmentId": "saved-association-v1" if identity_frames else None,
                "frameIndex": i, "timestampSeconds": native["timestampSeconds"],
                "originalPts": native["originalPts"], "originalTimeBase": native["originalTimeBase"],
                "pixelSha256": native["pixelSha256"], "predictionTimestampSeconds": prediction["timestampSeconds"],
                "pawPosition": {k: point[k] for k in ("x", "y")} if point else None,
                "rawPosePrediction": deepcopy(point), "rawPoseScore": score, "poseConfidence": confidence,
                "identityContinuous": continuous, "identityEvidence": deepcopy(track),
                "missing": point is None, "invalid": False,
                "motionReference": "camera_compensated_ground" if registration["reliable"] else None,
                "groundReferenceReliable": geometry_reliable,
                "groundMotionReliable": motion is not None,
                "groundRelativeSpeed": motion["speedTorsoLengthsPerSecond"] if motion else None,
                "groundMotionEvidence": motion, "groundMotionFramePair": [i-1, i] if motion else None,
                "groundClearance": proximity["clearanceTorsoLengths"],
                "groundClearanceReliable": proximity["reliableForEvents"],
                "groundProximity": proximity, "extractionReasons": sorted(set(extraction_reasons)),
            })
            if accepted:
                next_tracks[identity] = point
        before_tracks = next_tracks
        previous_scene = current_scene
    detected = detect_events(observations)
    return {"analysisType": "candidate_real_video_ground_evidence", "config": asdict(config),
        "sceneCalibration": deepcopy(scene), "groundMotion": motion_frames, "detector": detected,
        "summary": {"sourceFrames": count, "pawObservations": len(observations),
            "reliableGroundRegistrations": sum(f["registration"]["reliable"] for f in motion_frames),
            "measuredPhysicalPawMotions": sum(o["groundMotionReliable"] for o in observations),
            "usableClearanceObservations": sum(o["groundClearanceReliable"] for o in observations),
            "candidateEvents": len(detected["events"]), "candidateSequences": detected["candidateSequenceCount"],
            "stateCounts": dict(Counter(s["state"] for s in detected["states"])),
            "abstentionReasons": dict(Counter(reason for s in detected["states"] if s["state"] == "UNKNOWN" for reason in s["reasons"])),
            "extractionReasons": dict(Counter(reason for o in observations for reason in o["extractionReasons"]))},
        "limitations": ["All outputs are candidates, not biologically verified contact or gait.",
            "Ground/background agreement is a consistency check, not proof that a surface is stationary.",
            "A similarity model rejects unsupported perspective/parallax instead of correcting it.",
            "Floor-region overlap is not clearance; no height is inferred without independent geometry.",
            "Saved association outputs are uncertain motion-only hypotheses, not verified physical identity.",
            "No human annotations or model training/inference are used."]}
