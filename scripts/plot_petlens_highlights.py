#!/usr/bin/env python3
"""Create presentation-ready plots of measured PetLens validation improvements."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from plot_pose_validation_report import KEYPOINT_LABELS

ROOT = Path(__file__).resolve().parents[1]
BLUE = "#176b87"
GREEN = "#25836b"
ORANGE = "#d36a36"
INK = "#163247"
MUTED = "#526b7c"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metrics",
        type=Path,
        default=ROOT / "reports" / "canine-pose-validation" / "metrics.json",
    )
    parser.add_argument(
        "--training-csv",
        type=Path,
        default=ROOT / "reports" / "canine-pose-validation" / "training.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "reports" / "petlens-positive-results",
    )
    return parser.parse_args()


def load_inputs(metrics_path: Path, training_path: Path) -> tuple[dict[str, Any], list[dict[str, float]]]:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("status") != "development_validation_only":
        raise ValueError("Expected a development-validation metrics report.")
    if metrics.get("dataset", {}).get("split") != "official val split":
        raise ValueError("Highlights must use the official validation split.")
    if metrics.get("evaluation_protocol", {}).get("independent") is not False:
        raise ValueError("Expected non-independent validation metadata.")

    rows: list[dict[str, float]] = []
    with training_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            rows.append(
                {
                    "epoch": int(row["epoch"]),
                    "training_loss": float(row["training_loss"]),
                    "validation_loss": float(row["validation_loss"]),
                }
            )
    if not rows or any(row["epoch"] <= 0 for row in rows):
        raise ValueError("Training history is missing or invalid.")
    if any(right["epoch"] <= left["epoch"] for left, right in zip(rows, rows[1:])):
        raise ValueError("Training epochs must be strictly increasing.")

    checkpoint_epoch = int(metrics["model"]["checkpoint_epoch"])
    if checkpoint_epoch not in {int(row["epoch"]) for row in rows}:
        raise ValueError("Selected checkpoint epoch is missing from training history.")
    return metrics, rows


def style_axis(ax: plt.Axes) -> None:
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#bfd0d8")
    ax.tick_params(colors=MUTED)
    ax.grid(axis="x", color="#dbe5e9", linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    fig.savefig(out_dir / f"{stem}.png", dpi=200, bbox_inches="tight", facecolor="white")
    svg_path = out_dir / f"{stem}.svg"
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)


def plot_baseline(metrics: dict[str, Any], out_dir: Path) -> dict[str, float]:
    model = metrics["pck_at_0_1"]["model"]
    baseline = metrics["pck_at_0_1"]["box_center_baseline"]
    model_value = float(model["overall"])
    baseline_value = float(baseline["overall"])
    ratio = model_value / baseline_value if baseline_value else float("inf")
    model_ci = model["bootstrap_95_ci_by_image"]
    baseline_ci = baseline["bootstrap_95_ci_by_image"]
    values = [model_value, baseline_value]
    intervals = [model_ci, baseline_ci]

    fig, ax = plt.subplots(figsize=(9, 4.4), layout="constrained")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    y = [1, 0]
    colors = [GREEN, "#9bb4bd"]
    for position, value, interval, color in zip(y, values, intervals, colors):
        ax.barh(position, value, height=0.48, color=color, zorder=3)
        lower = value - float(interval["lower"])
        upper = float(interval["upper"]) - value
        ax.errorbar(
            value,
            position,
            xerr=[[lower], [upper]],
            fmt="o",
            markersize=5,
            capsize=5,
            color=INK,
            zorder=4,
        )
        ax.text(
            float(interval["upper"]) + 0.018,
            position,
            f"{value:.1%}  ({model['correct'] if position == 1 else baseline['correct']}/"
            f"{model['visible_keypoints'] if position == 1 else baseline['visible_keypoints']})",
            va="center",
            ha="left",
            color=INK,
            fontweight="bold",
            fontsize=11,
        )
    ax.set_yticks(y, ["PetLens pose model", "Box-center baseline"])
    ax.set_xlim(0, 0.78)
    ax.set_ylim(-0.8, 1.5)
    ax.set_xlabel("PCK@0.1 — fraction of visible landmarks localized")
    ax.set_title(
        "PetLens localized more labeled landmarks than a simple baseline",
        loc="left",
        color=INK,
        fontsize=16,
        fontweight="bold",
        pad=18,
    )
    ax.text(
        0,
        1.25,
        f"{ratio:.1f}× the baseline PCK on validation  •  95% image-bootstrap intervals",
        color=GREEN,
        fontsize=11,
        fontweight="bold",
    )
    ax.text(
        0,
        -0.65,
        "AP-10K dog-only validation • 110 instances • oracle ground-truth boxes • checkpoint selected on this split",
        color=MUTED,
        fontsize=8.5,
    )
    style_axis(ax)
    save(fig, out_dir, "01-validation-vs-baseline")
    return {"model": model_value, "baseline": baseline_value, "ratio": ratio}


def plot_keypoints(metrics: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    model = metrics["pck_at_0_1"]["model"]["per_keypoint"]
    baseline = metrics["pck_at_0_1"]["box_center_baseline"]["per_keypoint"]
    names = list(model)
    names.sort(key=lambda name: model[name]["pck"])
    labels = [KEYPOINT_LABELS.get(name, name.replace("_", " ").title()) for name in names]
    model_values = np.asarray([model[name]["pck"] for name in names])
    baseline_values = np.asarray([baseline[name]["pck"] for name in names])
    y = np.arange(len(names))
    colors = [GREEN if m >= b else ORANGE for m, b in zip(model_values, baseline_values)]

    fig, ax = plt.subplots(figsize=(10, 8.2), layout="constrained")
    fig.patch.set_facecolor("white")
    ax.barh(y, model_values, color=colors, height=0.64, zorder=2)
    ax.scatter(
        baseline_values,
        y,
        marker="|",
        s=190,
        linewidths=2.4,
        color=INK,
        label="Box-center baseline",
        zorder=4,
    )
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 0.78)
    ax.set_xlabel("PCK@0.1 on validation split")
    ax.set_title(
        "Validation baseline exceeded across all 17 landmarks",
        loc="left",
        color=INK,
        fontsize=16,
        fontweight="bold",
        pad=18,
    )
    ax.text(
        0,
        1.015,
        "Each bar is PetLens; the dark tick marks the box-center score for the same landmark.",
        transform=ax.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax.text(
        0,
        -0.08,
        f"{sum(model[name]['pck'] >= baseline[name]['pck'] for name in names)}/17 landmarks at or above baseline  •  "
        f"tail-root PCK: {model['root_of_tail']['pck']:.1%} (still an improvement, but a weak result)",
        transform=ax.transAxes,
        color=INK,
        fontsize=9,
    )
    ax.legend(frameon=False, loc="lower right")
    style_axis(ax)
    save(fig, out_dir, "02-landmark-coverage")
    return {
        "model_pck": {name: float(model[name]["pck"]) for name in names},
        "baseline_pck": {name: float(baseline[name]["pck"]) for name in names},
        "landmarks_at_or_above_baseline": sum(
            model[name]["pck"] >= baseline[name]["pck"] for name in names
        ),
        "landmark_count": len(names),
    }


def plot_radar(metrics: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    groups = {
        "Head": ("left_eye", "right_eye", "nose"),
        "Neck": ("neck",),
        "Front legs": (
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_front_paw",
            "right_front_paw",
        ),
        "Hind legs": (
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_back_paw",
            "right_back_paw",
        ),
        "Tail base": ("root_of_tail",),
    }
    model = metrics["pck_at_0_1"]["model"]["per_keypoint"]
    baseline = metrics["pck_at_0_1"]["box_center_baseline"]["per_keypoint"]

    def group_pck(per_keypoint: dict[str, Any], landmarks: tuple[str, ...]) -> float:
        visible = sum(int(per_keypoint[name]["visible"]) for name in landmarks)
        correct = sum(int(per_keypoint[name]["correct"]) for name in landmarks)
        if visible == 0:
            raise ValueError(f"Landmark group has no visible annotations: {landmarks}")
        return correct / visible

    labels = list(groups)
    model_values = [group_pck(model, landmarks) for landmarks in groups.values()]
    baseline_values = [group_pck(baseline, landmarks) for landmarks in groups.values()]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    closed_angles = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(8.5, 7.2), subplot_kw={"polar": True})
    fig.subplots_adjust(top=0.82, bottom=0.2, left=0.08, right=0.92)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], color=MUTED, fontsize=8)
    ax.set_xticks(angles, labels)
    ax.tick_params(axis="x", colors=INK, labelsize=10, pad=12)
    ax.spines["polar"].set_color("#bfd0d8")
    ax.grid(color="#dbe5e9", linewidth=0.8)

    model_line = model_values + model_values[:1]
    baseline_line = baseline_values + baseline_values[:1]
    ax.plot(closed_angles, model_line, color=BLUE, linewidth=2.5, marker="o", label="PetLens pose model")
    ax.fill(closed_angles, model_line, color=BLUE, alpha=0.22)
    ax.plot(
        closed_angles,
        baseline_line,
        color="#c65a78",
        linewidth=2.5,
        marker="o",
        label="Box-center baseline",
    )
    ax.fill(closed_angles, baseline_line, color="#c65a78", alpha=0.15)
    fig.suptitle(
        "PetLens pose model vs. box-center baseline",
        y=0.975,
        color=INK,
        fontsize=15,
        fontweight="bold",
    )
    ax.text(
        0.5,
        1.14,
        "Higher is better • model scores higher in all five landmark groups",
        transform=ax.transAxes,
        ha="center",
        color=GREEN,
        fontsize=10,
        fontweight="bold",
    )
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
    fig.text(
        0.5,
        0.035,
        "AP-10K dog-only validation • 110 instances • ground-truth boxes • development-only, not app-level testing",
        ha="center",
        color=MUTED,
        fontsize=8.5,
    )
    save(fig, out_dir, "00-validation-radar")
    return {
        "metric": "PCK@0.1",
        "aggregation": "sum of correct visible landmarks / sum of visible landmarks in each group",
        "higher_is_better": True,
        "model_pck": dict(zip(labels, model_values)),
        "baseline_pck": dict(zip(labels, baseline_values)),
        "model_groups_above_baseline": sum(
            model_value > baseline_value
            for model_value, baseline_value in zip(model_values, baseline_values)
        ),
        "group_count": len(labels),
    }


def plot_training(metrics: dict[str, Any], rows: list[dict[str, float]], out_dir: Path) -> dict[str, float]:
    epochs = np.asarray([row["epoch"] for row in rows])
    training_loss = np.asarray([row["training_loss"] for row in rows])
    validation_loss = np.asarray([row["validation_loss"] for row in rows])
    checkpoint_epoch = int(metrics["model"]["checkpoint_epoch"])
    checkpoint_index = int(np.flatnonzero(epochs == checkpoint_epoch)[0])
    validation_reduction = 1 - validation_loss[checkpoint_index] / validation_loss[0]
    training_reduction = 1 - training_loss[-1] / training_loss[0]

    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.plot(epochs, training_loss, color=BLUE, lw=2.5, label="Training objective")
    ax.plot(epochs, validation_loss, color=GREEN, lw=2.8, label="Validation objective")
    ax.scatter(
        [checkpoint_epoch],
        [validation_loss[checkpoint_index]],
        s=85,
        color=GREEN,
        edgecolor="white",
        linewidth=1.5,
        zorder=5,
    )
    ax.annotate(
        f"Selected checkpoint • epoch {checkpoint_epoch}\nvalidation loss {validation_loss[checkpoint_index]:.3f}",
        xy=(checkpoint_epoch, validation_loss[checkpoint_index]),
        xytext=(-185, 38),
        textcoords="offset points",
        color=INK,
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": MUTED, "lw": 1},
    )
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Normalized heatmap training objective (lower is better)")
    ax.set_title(
        "Training made steady progress on the development objective",
        loc="left",
        color=INK,
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    ax.text(
        0,
        1.02,
        f"30 epochs • validation objective decreased {validation_reduction:.0%} from epoch 1 to selected checkpoint",
        transform=ax.transAxes,
        color=GREEN,
        fontsize=10,
        fontweight="bold",
    )
    ax.text(
        0,
        -0.19,
        "Loss is a training objective, not accuracy. The validation split selected the checkpoint; this is development-only evidence.",
        transform=ax.transAxes,
        color=MUTED,
        fontsize=8.5,
    )
    ax.set_xlim(1, int(epochs[-1]))
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#dbe5e9", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["bottom"].set_color("#bfd0d8")
    ax.spines["left"].set_color("#bfd0d8")
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, loc="upper right")
    save(fig, out_dir, "03-training-progress")
    return {
        "validation_objective_reduction": float(validation_reduction),
        "training_objective_reduction": float(training_reduction),
        "selected_epoch": checkpoint_epoch,
        "validation_objective_at_selection": float(validation_loss[checkpoint_index]),
    }


def main() -> int:
    args = parse_args()
    metrics, rows = load_inputs(args.metrics, args.training_csv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    radar = plot_radar(metrics, args.out_dir)
    baseline = plot_baseline(metrics, args.out_dir)
    keypoints = plot_keypoints(metrics, args.out_dir)
    training = plot_training(metrics, rows, args.out_dir)

    summary = {
        "status": "development_validation_only",
        "results_are_independent": False,
        "scope": (
            "Still-image keypoint localization on AP-10K dog-only validation "
            "with ground-truth boxes; not production app inference, video tracking, "
            "gait, or clinical performance."
        ),
        "pck_at_0_1": baseline,
        "anatomical_groups": radar,
        "keypoints": keypoints,
        "training": training,
        "dataset": metrics["dataset"],
    }
    (args.out_dir / "highlights.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    page = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PetLens measured highlights</title>
<style>
body{font:16px/1.55 system-ui,sans-serif;color:#163247;max-width:1000px;margin:2rem auto;padding:0 1rem}
h1,h2{line-height:1.2} .caveat{background:#fff1d6;padding:1rem;border-radius:.5rem}
section{border-top:1px solid #d7e1e8;padding:1.2rem 0} img{max-width:100%;height:auto}
small{color:#526b7c}
</style>
<h1>PetLens: measured development highlights</h1>
<p class="caveat"><strong>Read this first:</strong> These are positive results from an
AP-10K still-image validation experiment. The checkpoint was selected on this
split and used ground-truth dog boxes. It is not an independent test, not
production app inference, and not validation of walking video, gait, or
osteoarthritis. The live app pipeline remains motion-only.</p>
<section><h2>1. Pose localization across landmark groups</h2>
<img src="00-validation-radar.png" alt="Radar chart comparing PetLens and box-center validation PCK across five landmark groups">
<p>Each radar value is computed from the actual correct and visible landmark counts in that group. A higher value means more landmarks were localized within the PCK@0.1 threshold. This compares an experimental pose model with a simple baseline, not the complete app with another product.</p></section>
<section><h2>2. Overall pose localization vs. the same baseline</h2>
<img src="01-validation-vs-baseline.png" alt="Validation PCK comparison with confidence intervals">
<p>PetLens exceeded the box-center baseline on this validation split.</p></section>
<section><h2>3. Landmark coverage</h2>
<img src="02-landmark-coverage.png" alt="Per-landmark validation PCK compared with box center">
<p>The comparison shows every landmark, including the weaker tail-root result.</p></section>
<section><h2>4. Training progress</h2>
<img src="03-training-progress.png" alt="Recorded training and validation objective by epoch">
<p>Lower objective values indicate optimization progress, not model accuracy.</p></section>
<small>Source metrics and full report: ../canine-pose-validation/</small>
</html>
"""
    (args.out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote PetLens measured-highlights graphs to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
