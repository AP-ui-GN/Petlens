#!/usr/bin/env python3
"""Evaluate a trained AP-10K dog pose model on a prepared data split."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from gait_engine.ap10k_data import DatasetValidationError, SCHEMA_VERSION
from gait_engine.pose_backend import AP10K_KEYPOINTS
from gait_engine.pose_eval import evaluate_ap10k_pck
from training.train_pose import _load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPOSITORY_ROOT / "training" / "dataset_config.yaml",
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument(
        "--require-baseline",
        action="store_true",
        help="Return a failure status unless PCK@0.1 meets the box-center baseline.",
    )
    parser.add_argument(
        "--metrics-out",
        type=Path,
    )
    parser.add_argument(
        "--report-out",
        type=Path,
    )
    parser.add_argument("--predictions-out", type=Path)
    parser.add_argument("--visualizations-dir", type=Path)
    parser.add_argument("--max-visualizations", type=int, default=12)
    parser.add_argument("--device", default=None)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--prepared-dir", type=Path)
    parser.add_argument("--minimum-confidence", type=float, default=0.0)
    return parser.parse_args()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _draw_visualization(
    record: dict[str, Any],
    prediction: dict[str, Any],
    image_root: Path,
    output_path: Path,
    model_version: str,
) -> None:
    import cv2

    image_path = image_root / Path(*Path(record["file_name"]).parts)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise DatasetValidationError(f"Image cannot be decoded: {record['file_name']!r}.")
    x, y, width, height = (int(round(value)) for value in record["bbox_xywh"])
    cv2.rectangle(image, (x, y), (x + width, y + height), (255, 200, 0), 2)
    for index, (point_x, point_y, visibility) in enumerate(record["keypoints"]):
        if visibility > 0:
            cv2.circle(image, (round(point_x), round(point_y)), 4, (0, 0, 255), -1)
        pred_x, pred_y, confidence = prediction["keypoints"][index]
        if confidence > 0:
            cv2.circle(image, (round(pred_x), round(pred_y)), 3, (0, 255, 0), -1)
    label = f"AP-10K test | model {model_version[:12]} | red=GT green=pred"
    cv2.putText(image, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise OSError(f"Could not write visualization {output_path}.")


def _markdown_report(payload: dict[str, Any]) -> str:
    evaluation = payload["evaluation"]
    pck_005 = evaluation["metrics"]["PCK@0.05"]
    pck_01 = evaluation["metrics"]["PCK@0.1"]
    baseline_01 = payload["baseline"]["metrics"]["PCK@0.1"]
    errors = evaluation["metrics"]["keypoint_error"]
    confidence_interval = pck_01["bootstrap_95_ci_by_image"]
    confidence_interval_text = (
        "not estimable"
        if confidence_interval is None
        else f"[{confidence_interval['lower']}, {confidence_interval['upper']}]"
    )
    lines = [
        "# Canine Pose Evaluation",
        "",
        f"- Status: {payload['status']}",
        f"- Independent evaluation: {payload['evaluation_protocol']['independent']}",
        f"- Protocol note: {payload['evaluation_protocol']['note']}",
        f"- Model: {payload['model']['name']} (`{payload['model']['version']}`)",
        f"- Training: {payload['training']['epochs_completed']} epochs; {payload['training']['initialization']} initialization; selected by {payload['training']['selected_by']}",
        f"- Training device: {payload['training']['device']}; duration seconds: {payload['training']['duration_seconds']}",
        f"- Dataset: AP-10K {payload['dataset']['split']}, species filter `{payload['dataset']['species_filter']}`",
        f"- Instances: {evaluation['instances']} annotations; {evaluation['predicted_instances']} predictions",
        "- Scope: pose localization with ground-truth boxes; detection, tracking, and gait are not evaluated.",
        f"- PCK@0.05: {pck_005['overall']}",
        f"- PCK@0.1: {pck_01['overall']}",
        f"- PCK@0.1 95% image-bootstrap CI: {confidence_interval_text}",
        f"- Box-center baseline PCK@0.1: {baseline_01['overall']}",
        f"- Box-center baseline comparison: {'met' if payload['baseline']['meets_or_exceeds'] else 'not met'} on this split",
        f"- Mean pixel error: {errors['mean_pixel_error']} px over {errors['predicted_keypoints']} predicted visible keypoints",
        f"- Mean normalized error: {errors['mean_normalized_error']} (normalizer: {errors['normalized_units']})",
        f"- Model-forward latency: {payload['runtime']['mean_model_forward_seconds_per_instance']} seconds per dog crop on {payload['runtime']['device']}",
        "",
        "## Visibility-specific PCK@0.1",
        "",
        "| Visibility | PCK | Correct / labeled |",
        "| --- | ---: | ---: |",
    ]
    for visibility, values in pck_01["by_visibility"].items():
        lines.append(
            f"| {visibility} | {values['pck']} | {values['correct']} / {values['keypoints']} |"
        )
    lines.extend(
        [
            "",
            "This image-level test does not establish walking-video or gait accuracy. "
            "AP-10K's hip/knee labels have species-dependent meanings; gait metrics remain gated pending dog-video validation.",
            "",
        ]
    )
    return "\n".join(lines)


def run_evaluation(args: argparse.Namespace) -> int:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "Optional evaluation packages are missing. Install requirements-training.txt."
        ) from exc

    from training.data import AP10KHeatmapDataset
    from training.pose_model import build_model

    config = _load_config(args.config)
    dataset_config = config["dataset"]
    model_config = config["model"]
    dataset_root = (
        args.dataset_root
        if args.dataset_root is not None
        else Path(dataset_config["root"])
    ).expanduser()
    prepared_dir = (
        args.prepared_dir
        if args.prepared_dir is not None
        else Path(dataset_config["prepared_dir"])
    ).expanduser()
    species = str(dataset_config.get("species", "dog"))
    split_path = prepared_dir / f"{args.split}.json"
    metrics_out = args.metrics_out or (
        REPOSITORY_ROOT
        / "reports"
        / (
            "canine_pose_metrics.json"
            if args.split == "test"
            else f"canine_pose_metrics_{args.split}.json"
        )
    )
    report_out = args.report_out or (
        REPOSITORY_ROOT
        / "reports"
        / (
            "canine_pose_evaluation.md"
            if args.split == "test"
            else f"canine_pose_evaluation_{args.split}.md"
        )
    )
    input_size = (int(model_config["input_width"]), int(model_config["input_height"]))
    heatmap_size = (int(model_config["heatmap_width"]), int(model_config["heatmap_height"]))
    dataset = AP10KHeatmapDataset(
        split_path,
        dataset_root / "data",
        species=species,
        input_size=input_size,
        heatmap_size=heatmap_size,
        augment=False,
        gaussian_sigma=float(config["training"]["gaussian_sigma"]),
    )
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Checkpoint schema version is incompatible.")
    if checkpoint.get("keypoints") != list(AP10K_KEYPOINTS):
        raise ValueError("Checkpoint keypoint order is incompatible.")
    if checkpoint.get("architecture") != "resnet18-topdown-heatmap":
        raise ValueError("Checkpoint architecture is incompatible.")

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable.")
    model = build_model().to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    # Run the model once per prepared instance and map heatmap peaks to image pixels.
    predictions = []
    visualizations = 0
    model_version = str(checkpoint.get("run_id", "unversioned"))
    model_forward_seconds = 0.0
    with torch.inference_mode():
        for index, record in enumerate(dataset.records):
            image_tensor, _targets, _weights, _points, crop = dataset[index]
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            forward_started = time.perf_counter()
            heatmaps = model(image_tensor.unsqueeze(0).to(device))[0].cpu()
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            model_forward_seconds += time.perf_counter() - forward_started
            flat = heatmaps.reshape(len(AP10K_KEYPOINTS), -1)
            scores, positions = flat.max(dim=1)
            crop_left, crop_top, crop_right, crop_bottom = crop.tolist()
            predicted_keypoints = []
            for score, position in zip(scores.tolist(), positions.tolist()):
                heatmap_y, heatmap_x = divmod(position, heatmap_size[0])
                input_x = (
                    (heatmap_x + 0.5) * input_size[0] / heatmap_size[0] - 0.5
                )
                input_y = (
                    (heatmap_y + 0.5) * input_size[1] / heatmap_size[1] - 0.5
                )
                original_x = (
                    crop_left + (input_x + 0.5) * (crop_right - crop_left) / input_size[0] - 0.5
                )
                original_y = (
                    crop_top + (input_y + 0.5) * (crop_bottom - crop_top) / input_size[1] - 0.5
                )
                predicted_keypoints.append([original_x, original_y, score])
            prediction = {
                "annotation_id": record["annotation_id"],
                "keypoints": predicted_keypoints,
            }
            predictions.append(prediction)
            if (
                args.visualizations_dir is not None
                and visualizations < args.max_visualizations
            ):
                _draw_visualization(
                    record,
                    prediction,
                    dataset.image_root,
                    args.visualizations_dir
                    / f"{args.split}-{record['annotation_id']}-{visualizations:02d}.jpg",
                    model_version,
                )
                visualizations += 1

    annotations = {
        "schema_version": SCHEMA_VERSION,
        "keypoints": list(AP10K_KEYPOINTS),
        "records": dataset.records,
    }
    prediction_payload = {
        "schema_version": SCHEMA_VERSION,
        "keypoints": list(AP10K_KEYPOINTS),
        "predictions": predictions,
    }
    evaluation = evaluate_ap10k_pck(
        annotations,
        prediction_payload,
        minimum_confidence=args.minimum_confidence,
    )
    # Compare against a simple box-center placement using the same annotations.
    baseline_predictions = {
        "schema_version": SCHEMA_VERSION,
        "keypoints": list(AP10K_KEYPOINTS),
        "predictions": [
            {
                "annotation_id": record["annotation_id"],
                "keypoints": [
                    [
                        record["bbox_xywh"][0] + record["bbox_xywh"][2] / 2,
                        record["bbox_xywh"][1] + record["bbox_xywh"][3] / 2,
                        1.0,
                    ]
                    for _ in AP10K_KEYPOINTS
                ],
            }
            for record in dataset.records
        ],
    }
    baseline_evaluation = evaluate_ap10k_pck(
        annotations,
        baseline_predictions,
        minimum_confidence=args.minimum_confidence,
    )
    meets_baseline = (
        evaluation["metrics"]["PCK@0.1"]["overall"]
        >= baseline_evaluation["metrics"]["PCK@0.1"]["overall"]
    )
    training_metadata_path = args.checkpoint.parent / "training_metadata.json"
    training_metadata = (
        json.loads(training_metadata_path.read_text(encoding="utf-8"))
        if training_metadata_path.is_file()
        else {}
    )
    metadata_matches_checkpoint = (
        training_metadata.get("best_checkpoint_epoch")
        == checkpoint.get("epoch")
        and training_metadata.get(
            "experiment_id", training_metadata.get("run_id")
        )
        == checkpoint.get("run_id")
    )
    result = {
        "status": (
            "development_validation"
            if args.split == "val"
            else "exploratory_measured"
        ),
        "evaluation_protocol": {
            "independent": False,
            "note": (
                (
                    "The AP-10K validation split is used for model selection and "
                    "early stopping; these measurements are development-only and "
                    "are not independent performance evidence."
                    if args.split == "val"
                    else
                    "The AP-10K official test split was evaluated and inspected before "
                    "training continued; it is diagnostic only and must not guide model "
                    "selection or performance claims."
                )
            ),
        },
        "model": {
            "name": checkpoint.get("model_name", "AP-10K dog heatmap model"),
            "version": model_version,
            "architecture": checkpoint["architecture"],
            "initialization": checkpoint.get("initialization"),
            "checkpoint_file": args.checkpoint.name,
            "checkpoint_sha256": _sha256_file(args.checkpoint),
            "checkpoint_epoch": checkpoint.get("epoch"),
            "best_validation_loss": checkpoint.get("best_validation_loss"),
        },
        "training": {
            "epochs_completed": checkpoint.get("epoch"),
            "metadata_matches_checkpoint": metadata_matches_checkpoint,
            "duration_seconds": (
                training_metadata.get(
                    "duration_seconds_this_run",
                    training_metadata.get("duration_seconds"),
                )
                if metadata_matches_checkpoint
                else None
            ),
            "device": (
                training_metadata.get("hardware", {}).get("device")
                if metadata_matches_checkpoint
                else None
            ),
            "seed": checkpoint.get(
                "seed", checkpoint.get("training_config", {}).get("training", {}).get("seed")
            ),
            "initialization": checkpoint.get("initialization"),
            "selected_by": "lowest validation loss",
        },
        "dataset": {
            "name": "AP-10K",
            "split": f"official {args.split} split",
            "species_filter": species,
            "schema_version": SCHEMA_VERSION,
            "instances": len(dataset),
            "annotations_sha256": _sha256_file(split_path),
            "manifest_sha256": _sha256_file(prepared_dir / "manifest.json"),
        },
        "evaluation": evaluation,
        "baseline": {
            "method": "Every AP-10K keypoint is placed at the ground-truth box center.",
            "evaluation": "same oracle-box instances and PCK protocol as the model",
            "meets_or_exceeds": meets_baseline,
            "metrics": baseline_evaluation["metrics"],
        },
        "runtime": {
            "device": str(device),
            "model_forward_seconds": model_forward_seconds,
            "mean_model_forward_seconds_per_instance": (
                model_forward_seconds / len(dataset) if dataset else None
            ),
        },
        "visualizations_written": visualizations,
    }
    _write_json(metrics_out, result)
    if args.predictions_out is not None:
        _write_json(args.predictions_out, prediction_payload)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(_markdown_report(result), encoding="utf-8")
    print(f"Wrote {args.split} metrics to {metrics_out}")
    print(f"Wrote human-readable report to {report_out}")
    print(
        "Box-center baseline "
        f"{'met' if meets_baseline else 'not met'} on {args.split} "
        f"(model {evaluation['metrics']['PCK@0.1']['overall']:.6f}, "
        f"baseline {baseline_evaluation['metrics']['PCK@0.1']['overall']:.6f})."
    )
    if args.require_baseline and not meets_baseline:
        print(
            "Baseline acceptance failed: model PCK@0.1 is below the box-center baseline.",
            file=sys.stderr,
        )
        return 3
    return 0


def main() -> int:
    args = parse_args()
    if args.max_visualizations < 0:
        print("--max-visualizations must be non-negative.", file=sys.stderr)
        return 2
    if not 0.0 <= args.minimum_confidence <= 1.0:
        print("--minimum-confidence must be between 0 and 1.", file=sys.stderr)
        return 2
    try:
        return run_evaluation(args)
    except (DatasetValidationError, OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Canine pose evaluation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
