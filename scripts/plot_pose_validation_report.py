#!/usr/bin/env python3
"""Plot transparent AP-10K validation diagnostics from recorded run outputs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
KEYPOINT_LABELS = {
    "left_eye": "Left eye",
    "right_eye": "Right eye",
    "nose": "Nose",
    "neck": "Neck",
    "root_of_tail": "Tail root",
    "left_shoulder": "Left shoulder",
    "left_elbow": "Left elbow",
    "left_front_paw": "Left front paw",
    "right_shoulder": "Right shoulder",
    "right_elbow": "Right elbow",
    "right_front_paw": "Right front paw",
    "left_hip": "Left hip",
    "left_knee": "Left knee",
    "left_back_paw": "Left back paw",
    "right_hip": "Right hip",
    "right_knee": "Right knee",
    "right_back_paw": "Right back paw",
}
BLUE = "#176b87"
ORANGE = "#d36a36"
RED = "#b65054"
GREEN = "#257b65"
INK = "#163247"
MUTED = "#526b7c"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--training-log",
        type=Path,
        action="append",
        required=True,
        help="JSONL training log; pass multiple files in chronological order when resumed.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "reports" / "canine-pose-validation",
    )
    return parser.parse_args()


def load_training(log_paths: list[Path]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    last_epoch = 0
    for path in log_paths:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                epoch = int(record["epoch"])
                if epoch <= last_epoch:
                    raise ValueError(
                        f"Training logs are not in increasing epoch order at "
                        f"{path}:{line_number}."
                    )
                rows.append(
                    {
                        "epoch": epoch,
                        "training_loss": float(record["training_loss"]),
                        "validation_loss": float(record["validation_loss"]),
                    }
                )
                last_epoch = epoch
    if not rows:
        raise ValueError("Training logs contain no epochs.")
    return rows


def plot_training(rows: list[dict[str, float]], checkpoint_epoch: int, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.6), layout="constrained")
    epochs = [row["epoch"] for row in rows]
    train = [row["training_loss"] for row in rows]
    val = [row["validation_loss"] for row in rows]
    ax.plot(epochs, train, marker="o", ms=3, lw=2, color=BLUE, label="Training")
    ax.plot(epochs, val, marker="o", ms=3, lw=2, color=ORANGE, label="Validation")
    ax.axvline(checkpoint_epoch, color=MUTED, ls="--", lw=1, label=f"Best checkpoint: {checkpoint_epoch}")
    ax.set(title="AP-10K dog pose: training history", xlabel="Epoch", ylabel="Normalized heatmap loss")
    ax.set_xlim(left=1)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, ncol=3, fontsize=8)
    save_figure(fig, out, "01-training-loss")


def plot_overall(metrics: dict[str, Any], out: Path) -> None:
    model = metrics["evaluation"]["metrics"]["PCK@0.1"]
    baseline = metrics["baseline"]["metrics"]["PCK@0.1"]
    values = [model["overall"], baseline["overall"]]
    intervals = [
        model["bootstrap_95_ci_by_image"],
        baseline["bootstrap_95_ci_by_image"],
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), layout="constrained")
    ys = [1, 0]
    colors = [RED, GREEN]
    for y, value, ci, color in zip(ys, values, intervals, colors):
        lower = value - ci["lower"]
        upper = ci["upper"] - value
        ax.errorbar(value, y, xerr=[[lower], [upper]], fmt="o", capsize=4, ms=7, color=color)
        ax.text(min(value + upper + 0.015, 0.88), y, f"{value:.3f}", va="center", color=INK)
    ax.set_yticks(ys, ["PetLens model", "Box-center"])
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("PCK@0.1")
    ax.set_title("Validation localization vs. box-center baseline")
    ax.grid(axis="x", alpha=0.2)
    ax.text(
        0.99,
        -0.32,
        f"{model['correct']}/{model['visible_keypoints']} labeled points",
        ha="right",
        va="center",
        transform=ax.transAxes,
        fontsize=8,
        color=MUTED,
    )
    save_figure(fig, out, "02-overall-pck")


def plot_keypoints(metrics: dict[str, Any], out: Path) -> None:
    model = metrics["evaluation"]["metrics"]["PCK@0.1"]["per_keypoint"]
    baseline = metrics["baseline"]["metrics"]["PCK@0.1"]["per_keypoint"]
    names = list(model)
    labels = [KEYPOINT_LABELS.get(name, name.replace("_", " ").title()) for name in names]
    y = np.arange(len(names))
    height = 0.36
    fig, ax = plt.subplots(figsize=(9.2, 7.0), layout="constrained")
    ax.barh(y - height / 2, [model[name]["pck"] for name in names], height, color=BLUE, label="PetLens")
    ax.barh(y + height / 2, [baseline[name]["pck"] for name in names], height, color=ORANGE, label="Box-center")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("PCK@0.1")
    ax.set_title("Validation PCK by keypoint")
    ax.grid(axis="x", alpha=0.2)
    ax.legend(frameon=False)
    save_figure(fig, out, "03-per-keypoint-pck")

    differences = [model[name]["pck"] - baseline[name]["pck"] for name in names]
    fig, ax = plt.subplots(figsize=(9.2, 7.0), layout="constrained")
    colors = [GREEN if value >= 0 else RED for value in differences]
    ax.barh(y, differences, color=colors)
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("PCK difference (PetLens − box-center)")
    ax.set_title("Validation per-keypoint difference")
    ax.grid(axis="x", alpha=0.2)
    save_figure(fig, out, "04-per-keypoint-difference")


def plot_error(metrics: dict[str, Any], out: Path) -> list[float]:
    values = [
        float(row["mean_normalized_error"])
        for row in metrics["evaluation"]["per_image"]
        if row.get("mean_normalized_error") is not None
    ]
    if not values:
        raise ValueError("Validation output contains no per-image localization errors.")
    fig, ax = plt.subplots(figsize=(7.2, 3.8), layout="constrained")
    ax.hist(values, bins=18, color=BLUE, alpha=0.88, edgecolor="white")
    median = float(np.median(values))
    ax.axvline(median, color=RED, ls="--", lw=2, label=f"Median {median:.3f}")
    ax.set_xlabel("Mean normalized keypoint error per image")
    ax.set_ylabel("Images")
    ax.set_title("Validation image-level localization error")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    save_figure(fig, out, "05-image-error-distribution")
    return values


def plot_confidence(predictions: dict[str, Any], out: Path) -> list[float]:
    confidence = [
        float(keypoint[2])
        for prediction in predictions["predictions"]
        for keypoint in prediction["keypoints"]
        if len(keypoint) >= 3 and np.isfinite(keypoint[2])
    ]
    if not confidence:
        raise ValueError("Prediction output contains no finite keypoint scores.")
    fig, ax = plt.subplots(figsize=(7.2, 3.8), layout="constrained")
    ax.hist(confidence, bins=np.linspace(0, 1, 21), color=ORANGE, alpha=0.9, edgecolor="white")
    ax.set(xlim=(0, 1), xlabel="Peak heatmap score (uncalibrated)", ylabel="Keypoints")
    ax.set_title("Validation prediction-score distribution")
    ax.grid(axis="y", alpha=0.2)
    save_figure(fig, out, "06-confidence-distribution")
    return confidence


def save_figure(fig: plt.Figure, out: Path, stem: str) -> None:
    svg_path = out / f"{stem}.svg"
    fig.savefig(svg_path, bbox_inches="tight")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines())
        + "\n",
        encoding="utf-8",
    )
    fig.savefig(out / f"{stem}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    if metrics.get("dataset", {}).get("split") != "official val split":
        raise ValueError("This report script only accepts the AP-10K validation split.")
    if metrics.get("evaluation_protocol", {}).get("independent") is not False:
        raise ValueError("Expected validation-only, non-independent evaluation metadata.")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    training = load_training(args.training_log)
    checkpoint_epoch = int(metrics["model"]["checkpoint_epoch"])
    plot_training(training, checkpoint_epoch, args.out_dir)
    plot_overall(metrics, args.out_dir)
    plot_keypoints(metrics, args.out_dir)
    image_errors = plot_error(metrics, args.out_dir)
    confidence = plot_confidence(predictions, args.out_dir)

    keypoint_metrics = metrics["evaluation"]["metrics"]["PCK@0.1"]["per_keypoint"]
    baseline_metrics = metrics["baseline"]["metrics"]["PCK@0.1"]["per_keypoint"]
    pck = metrics["evaluation"]["metrics"]["PCK@0.1"]
    baseline_pck = metrics["baseline"]["metrics"]["PCK@0.1"]
    summary = {
        "status": "development_validation_only",
        "warning": (
            "AP-10K is an image dataset; this is validation evidence, not an "
            "independent test result or walking-video/gait validation."
        ),
        "model": metrics["model"],
        "training": metrics["training"],
        "dataset": metrics["dataset"],
        "evaluation_protocol": metrics["evaluation_protocol"],
        "pck_at_0_1": {
            "model": pck,
            "box_center_baseline": baseline_pck,
            "absolute_difference": pck["overall"] - baseline_pck["overall"],
            "baseline_met_on_validation": metrics["baseline"]["meets_or_exceeds"],
        },
        "per_keypoint": {
            key: {
                "label": KEYPOINT_LABELS.get(key, key),
                "model": keypoint_metrics[key],
                "box_center_baseline": baseline_metrics[key],
                "difference": keypoint_metrics[key]["pck"] - baseline_metrics[key]["pck"],
            }
            for key in keypoint_metrics
        },
        "per_image_normalized_error": {
            "count": len(image_errors),
            "median": float(np.median(image_errors)),
            "p90": float(np.percentile(image_errors, 90)),
            "values": image_errors,
        },
        "heatmap_peak_score": {
            "count": len(confidence),
            "median": float(np.median(confidence)),
            "histogram_bins": np.linspace(0, 1, 21).tolist(),
            "histogram_counts": np.histogram(confidence, bins=np.linspace(0, 1, 21))[0].tolist(),
            "calibrated": False,
        },
        "training_curve": training,
        "unavailable_analysis": {
            "video_pose_tracking": "Not generated: no validated AP-10K video inference path.",
            "stride_timing_and_symmetry": "Not generated: no validated canine keypoints in app inference.",
            "osteoarthritis_comparison": "Not generated: no independently labeled clinical dataset in the repository.",
        },
    }
    (args.out_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with (args.out_dir / "training.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=("epoch", "training_loss", "validation_loss"))
        writer.writeheader()
        writer.writerows(training)

    image_tags = [
        ("01-training-loss", "Actual recorded train/validation loss. The dashed line marks the selected checkpoint."),
        ("02-overall-pck", "PCK@0.1 and 95% image-bootstrap intervals on the 110-instance validation split."),
        ("03-per-keypoint-pck", "All 17 AP-10K landmarks, evaluated with the same oracle dog boxes and threshold."),
        ("04-per-keypoint-difference", "PetLens minus box-center PCK for every landmark, in proportion points."),
        ("05-image-error-distribution", "Per-image mean normalized localization error; averages only labeled, predicted visible points."),
        ("06-confidence-distribution", "Peak heatmap scores are uncalibrated and are not probabilities of correctness."),
    ]
    sections = "\n".join(
        f'<section><h2>{html.escape(stem[3:].replace("-", " ").title())}</h2>'
        f'<picture><source srcset="{stem}.svg" type="image/svg+xml">'
        f'<img src="{stem}.png" alt="{html.escape(caption)}"></picture>'
        f'<p>{html.escape(caption)}</p></section>'
        for stem, caption in image_tags
    )
    report = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PetLens canine-pose validation report</title>
<style>
body{{font:16px/1.55 system-ui,sans-serif;color:#163247;max-width:1050px;margin:2rem auto;padding:0 1rem}}
h1,h2{{line-height:1.2}} .warning{{background:#fff1d6;padding:1rem;border-radius:.5rem}}
section{{border-top:1px solid #d7e1e8;padding:1rem 0}} img{{max-width:100%;height:auto}}
code{{overflow-wrap:anywhere}} footer{{color:#526b7c}}
</style>
<h1>PetLens canine-pose validation diagnostics</h1>
<p class="warning"><strong>Development validation only.</strong> This AP-10K result uses
the validation split, which selected the checkpoint. It is not independent test
evidence and does not measure walking-video tracking, gait, or osteoarthritis.
The app's production inference remains motion-only.</p>
<p>Model run <code>{html.escape(str(metrics['model']['version']))}</code>,
checkpoint SHA-256 <code>{html.escape(str(metrics['model']['checkpoint_sha256']))}</code>,
epoch {checkpoint_epoch}. Dataset: AP-10K official dog-only validation split,
{metrics['evaluation']['instances']} instances and
{pck['visible_keypoints']} visible keypoints. PCK@0.1 is
{pck['correct']}/{pck['visible_keypoints']} ({pck['overall']:.4f});
box-center baseline {baseline_pck['correct']}/{baseline_pck['visible_keypoints']}
({baseline_pck['overall']:.4f}).</p>
{sections}
<h2>Not measured</h2><ul>
<li>Video pose tracking: no validated AP-10K video inference path.</li>
<li>Stride timing/symmetry: no validated canine keypoints in production app inference.</li>
<li>Osteoarthritis analysis: no independently labeled clinical dataset is present.</li>
</ul>
<footer>See adjacent metrics.json for graph data and docs/MODEL_CARD.md for model limitations.</footer>
</html>
"""
    (args.out_dir / "index.html").write_text(report, encoding="utf-8")
    print(f"Wrote validation figures and report to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
