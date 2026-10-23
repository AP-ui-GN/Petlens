"""Pose-only PCK evaluation for predictions aligned to AP-10K instances."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any

from .ap10k_data import SCHEMA_VERSION, DatasetValidationError
from .pose_backend import AP10K_KEYPOINTS


def evaluate_ap10k_pck(
    annotations: dict[str, Any],
    predictions: dict[str, Any],
    *,
    thresholds: Sequence[float] = (0.05, 0.1),
    minimum_confidence: float = 0.0,
    bootstrap_samples: int = 1000,
    random_seed: int = 0,
) -> dict[str, Any]:
    """Measure pose localization with oracle boxes; this does not score detection."""

    if annotations.get("schema_version") != SCHEMA_VERSION:
        raise DatasetValidationError("Annotation schema version is incompatible.")
    if predictions.get("schema_version") != SCHEMA_VERSION:
        raise DatasetValidationError("Prediction schema version is incompatible.")
    if annotations.get("keypoints") != list(AP10K_KEYPOINTS):
        raise DatasetValidationError("Annotation keypoint order does not match AP-10K.")
    if predictions.get("keypoints") != list(AP10K_KEYPOINTS):
        raise DatasetValidationError("Prediction keypoint order does not match AP-10K.")
    for name, value in (("minimum_confidence", minimum_confidence),):
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise DatasetValidationError(f"{name} must be between 0 and 1.")
    if not thresholds or any(
        not math.isfinite(value) or not 0.0 < value <= 1.0 for value in thresholds
    ):
        raise DatasetValidationError("PCK thresholds must be finite values in (0, 1].")
    if bootstrap_samples <= 0:
        raise DatasetValidationError("bootstrap_samples must be positive.")

    records = annotations.get("records")
    prediction_rows = predictions.get("predictions")
    if not isinstance(records, list) or not isinstance(prediction_rows, list):
        raise DatasetValidationError("Annotations and predictions must contain record lists.")

    annotation_by_id: dict[str | int, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("annotation_id") is None:
            raise DatasetValidationError("Every annotation record needs an annotation_id.")
        annotation_id = record["annotation_id"]
        if isinstance(annotation_id, bool) or not isinstance(annotation_id, (str, int)):
            raise DatasetValidationError("annotation_id must be a string or integer.")
        if annotation_id in annotation_by_id:
            raise DatasetValidationError(f"Duplicate annotation_id {annotation_id!r}.")
        annotation_by_id[annotation_id] = record

    prediction_by_id: dict[str | int, list[Any]] = {}
    for row in prediction_rows:
        if not isinstance(row, dict) or row.get("annotation_id") is None:
            raise DatasetValidationError("Every prediction needs an annotation_id.")
        annotation_id = row["annotation_id"]
        if isinstance(annotation_id, bool) or not isinstance(annotation_id, (str, int)):
            raise DatasetValidationError("prediction annotation_id must be a string or integer.")
        if annotation_id not in annotation_by_id:
            raise DatasetValidationError(
                f"Prediction references unknown annotation_id {annotation_id!r}."
            )
        if annotation_id in prediction_by_id:
            raise DatasetValidationError(f"Duplicate prediction for annotation_id {annotation_id!r}.")
        keypoints = row.get("keypoints")
        if not isinstance(keypoints, list) or len(keypoints) != len(AP10K_KEYPOINTS):
            raise DatasetValidationError("Each prediction must contain 17 keypoint triplets.")
        validated = []
        for point in keypoints:
            if not isinstance(point, list) or len(point) != 3:
                raise DatasetValidationError("Each predicted keypoint must be an [x, y, score] triplet.")
            try:
                x, y, score = (float(value) for value in point)
            except (TypeError, ValueError) as exc:
                raise DatasetValidationError("Predicted keypoints must be numeric.") from exc
            if not all(math.isfinite(value) for value in (x, y, score)) or not 0 <= score <= 1:
                raise DatasetValidationError("Predicted keypoint values must be finite; score in [0, 1].")
            validated.append((x, y, score))
        prediction_by_id[annotation_id] = validated

    counts = {name: 0 for name in AP10K_KEYPOINTS}
    correct = {
        float(threshold): {name: 0 for name in AP10K_KEYPOINTS}
        for threshold in thresholds
    }
    correct_by_visibility = {
        float(threshold): {1: 0, 2: 0} for threshold in thresholds
    }
    visible_total = 0
    visibility_totals = {1: 0, 2: 0}
    missing_prediction_instances = 0
    pixel_error_sum = 0.0
    normalized_error_sum = 0.0
    predicted_keypoints = 0
    pixel_error_by_keypoint = {name: 0.0 for name in AP10K_KEYPOINTS}
    normalized_error_by_keypoint = {name: 0.0 for name in AP10K_KEYPOINTS}
    predicted_by_keypoint = {name: 0 for name in AP10K_KEYPOINTS}
    per_image = []
    image_counts: dict[str | int, dict[float, dict[str, int]]] = {}
    for annotation_id, record in annotation_by_id.items():
        ground_truth = record.get("keypoints")
        box = record.get("bbox_xywh")
        if not isinstance(ground_truth, list) or len(ground_truth) != len(AP10K_KEYPOINTS):
            raise DatasetValidationError("Each annotation must contain 17 keypoint triplets.")
        if not isinstance(box, list) or len(box) != 4:
            raise DatasetValidationError("Each annotation must contain a COCO xywh box.")
        try:
            box_width, box_height = float(box[2]), float(box[3])
        except (TypeError, ValueError) as exc:
            raise DatasetValidationError("Bounding-box dimensions must be numeric.") from exc
        if not math.isfinite(box_width + box_height) or box_width <= 0 or box_height <= 0:
            raise DatasetValidationError("Bounding-box dimensions must be finite and positive.")
        normalizer = math.sqrt(box_width * box_height)
        predicted = prediction_by_id.get(annotation_id)
        if predicted is None:
            missing_prediction_instances += 1
        instance_visible = 0
        instance_predicted = 0
        instance_pixel_error = 0.0
        instance_normalized_error = 0.0
        instance_correct = {float(threshold): 0 for threshold in thresholds}

        for index, name in enumerate(AP10K_KEYPOINTS):
            truth = ground_truth[index]
            if not isinstance(truth, list) or len(truth) != 3:
                raise DatasetValidationError("Each ground-truth keypoint must be an [x, y, visibility] triplet.")
            try:
                truth_x, truth_y, visibility = (float(value) for value in truth)
            except (TypeError, ValueError) as exc:
                raise DatasetValidationError("Ground-truth keypoints must be numeric.") from exc
            if not all(math.isfinite(value) for value in (truth_x, truth_y, visibility)):
                raise DatasetValidationError("Ground-truth keypoints must be finite.")
            if visibility <= 0:
                if visibility != 0:
                    raise DatasetValidationError("Ground-truth visibility must be 0, 1, or 2.")
                continue
            if visibility not in (1, 2):
                raise DatasetValidationError("Ground-truth visibility must be 0, 1, or 2.")
            counts[name] += 1
            visible_total += 1
            instance_visible += 1
            visibility_label = int(visibility)
            visibility_totals[visibility_label] += 1
            if predicted is None:
                continue
            pred_x, pred_y, confidence = predicted[index]
            if confidence < minimum_confidence:
                continue
            pixel_distance = math.hypot(pred_x - truth_x, pred_y - truth_y)
            distance = pixel_distance / normalizer
            pixel_error_sum += pixel_distance
            normalized_error_sum += distance
            predicted_keypoints += 1
            pixel_error_by_keypoint[name] += pixel_distance
            normalized_error_by_keypoint[name] += distance
            predicted_by_keypoint[name] += 1
            instance_pixel_error += pixel_distance
            instance_normalized_error += distance
            instance_predicted += 1
            for threshold in correct:
                if distance <= threshold:
                    correct[threshold][name] += 1
                    correct_by_visibility[threshold][visibility_label] += 1
                    instance_correct[threshold] += 1
        per_image.append(
            {
                "image_id": record.get("image_id"),
                "annotation_id": annotation_id,
                "visible_keypoints": instance_visible,
                "predicted_keypoints": instance_predicted,
                "pck": {
                    f"PCK@{threshold:g}": (
                        None
                        if instance_visible == 0
                        else instance_correct[threshold] / instance_visible
                    )
                    for threshold in instance_correct
                },
                "mean_pixel_error": (
                    None
                    if instance_predicted == 0
                    else instance_pixel_error / instance_predicted
                ),
                "mean_normalized_error": (
                    None
                    if instance_predicted == 0
                    else instance_normalized_error / instance_predicted
                ),
            }
        )
        image_id = record.get("image_id")
        if image_id is None:
            image_id = annotation_id
        if isinstance(image_id, bool) or not isinstance(image_id, (str, int)):
            raise DatasetValidationError("image_id must be a string or integer when provided.")
        image_bucket = image_counts.setdefault(
            image_id,
            {
                float(threshold): {"correct": 0, "visible": 0}
                for threshold in thresholds
            },
        )
        for threshold, correct_count in instance_correct.items():
            image_bucket[threshold]["correct"] += correct_count
            image_bucket[threshold]["visible"] += instance_visible

    metrics = {}
    for threshold, keypoint_correct in correct.items():
        total_correct = sum(keypoint_correct.values())
        image_values = list(image_counts.values())
        if len(image_values) < 2:
            bootstrap_interval = None
        else:
            generator = random.Random(random_seed)
            samples = []
            for _ in range(bootstrap_samples):
                sample_correct = 0
                sample_visible = 0
                for image in generator.choices(image_values, k=len(image_values)):
                    sample_correct += image[threshold]["correct"]
                    sample_visible += image[threshold]["visible"]
                if sample_visible:
                    samples.append(sample_correct / sample_visible)
            samples.sort()
            bootstrap_interval = (
                None
                if not samples
                else {
                    "lower": samples[int(0.025 * (len(samples) - 1))],
                    "upper": samples[math.ceil(0.975 * (len(samples) - 1))],
                    "images": len(image_values),
                    "replicates": len(samples),
                    "seed": random_seed,
                }
            )
        metrics[f"PCK@{threshold:g}"] = {
            "threshold": threshold,
            "normalizer": "sqrt(annotation_bbox_width * annotation_bbox_height)",
            "overall": None if visible_total == 0 else total_correct / visible_total,
            "correct": total_correct,
            "visible_keypoints": visible_total,
            "bootstrap_95_ci_by_image": bootstrap_interval,
            "by_visibility": {
                ("visible" if visibility == 2 else "occluded"): {
                    "correct": correct_by_visibility[threshold][visibility],
                    "keypoints": visibility_totals[visibility],
                    "pck": (
                        None
                        if visibility_totals[visibility] == 0
                        else correct_by_visibility[threshold][visibility]
                        / visibility_totals[visibility]
                    ),
                }
                for visibility in (2, 1)
            },
            "per_keypoint": {
                name: {
                    "pck": None if counts[name] == 0 else keypoint_correct[name] / counts[name],
                    "correct": keypoint_correct[name],
                    "visible": counts[name],
                    "mean_pixel_error": (
                        None
                        if predicted_by_keypoint[name] == 0
                        else pixel_error_by_keypoint[name] / predicted_by_keypoint[name]
                    ),
                    "mean_normalized_error": (
                        None
                        if predicted_by_keypoint[name] == 0
                        else normalized_error_by_keypoint[name] / predicted_by_keypoint[name]
                    ),
                    "predicted": predicted_by_keypoint[name],
                }
                for name in AP10K_KEYPOINTS
            },
        }
    metrics["keypoint_error"] = {
        "pixel_units": "original-image pixels",
        "normalized_units": "error divided by sqrt(annotation_bbox_width * annotation_bbox_height)",
        "predicted_keypoints": predicted_keypoints,
        "visible_keypoints": visible_total,
        "mean_pixel_error": (
            None if predicted_keypoints == 0 else pixel_error_sum / predicted_keypoints
        ),
        "mean_normalized_error": (
            None if predicted_keypoints == 0 else normalized_error_sum / predicted_keypoints
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_scope": "pose localization with ground-truth boxes; detection, tracking, and gait are not evaluated",
        "instances": len(annotation_by_id),
        "predicted_instances": len(prediction_by_id),
        "missing_prediction_instances": missing_prediction_instances,
        "minimum_confidence": minimum_confidence,
        "metrics": metrics,
        "per_image": per_image,
    }
