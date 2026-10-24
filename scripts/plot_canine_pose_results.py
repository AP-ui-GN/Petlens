"""Render the recorded AP-10K dog-pose experiment as a dependency-free SVG."""

import csv
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING_CSV = ROOT / "reports" / "canine_pose_training.csv"
METRICS_JSON = ROOT / "reports" / "canine_pose_metrics.json"
OUTPUT_SVG = ROOT / "reports" / "canine_pose_exploratory.svg"

WIDTH = 1280
HEIGHT = 1020
COLORS = {
    "ink": "#163247",
    "muted": "#526b7c",
    "grid": "#d7e1e8",
    "train": "#176b87",
    "validation": "#d36a36",
    "model": "#b65054",
    "baseline": "#257b65",
    "paper": "#ffffff",
    "warning": "#fff1d6",
}


def text(x, y, value, size=14, color=None, weight=400, anchor="start"):
    value = html.escape(str(value))
    fill = color or COLORS["ink"]
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="{fill}">{value}</text>'
    )


def line(x1, y1, x2, y2, color=None, width=1, dash=None):
    color = color or COLORS["grid"]
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr}/>'
    )


def load_inputs():
    with TRAINING_CSV.open(newline="", encoding="utf-8") as source:
        training = list(csv.DictReader(source))
    if [int(row["epoch"]) for row in training] != [1, 2, 3, 4]:
        raise ValueError("Expected the four recorded training epochs.")
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    model = metrics["evaluation"]["metrics"]["PCK@0.1"]
    baseline = metrics["baseline"]["metrics"]["PCK@0.1"]
    if model["visible_keypoints"] != 2269 or baseline["visible_keypoints"] != 2269:
        raise ValueError("The figure expects the documented 2,269 visible keypoints.")
    return training, model, baseline


def training_panel(training):
    x0, y0, width, height = 60, 150, 540, 300
    plot_x, plot_y = x0 + 60, y0 + 55
    plot_w, plot_h = width - 95, height - 105
    values = [
        float(row[key])
        for row in training
        for key in ("training_loss", "validation_loss")
    ]
    maximum = max(values) * 1.05
    output = [
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="12" fill="{COLORS["paper"]}" stroke="{COLORS["grid"]}"/>',
        text(x0 + 20, y0 + 30, "Recorded training objective", 18, weight=700),
        text(x0 + 20, y0 + 50, "Loss is unitless; lower is not proof of pose accuracy.", 12, COLORS["muted"]),
    ]
    for tick in range(4):
        value = maximum * tick / 3
        y = plot_y + plot_h * (1 - tick / 3)
        output.append(line(plot_x, y, plot_x + plot_w, y))
        output.append(text(plot_x - 8, y + 4, f"{value:.3f}", 10, COLORS["muted"], anchor="end"))
    output.extend(
        [
            line(plot_x, plot_y, plot_x, plot_y + plot_h, COLORS["muted"]),
            line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, COLORS["muted"]),
        ]
    )
    for key, color, label in (
        ("training_loss", COLORS["train"], "Training"),
        ("validation_loss", COLORS["validation"], "Validation"),
    ):
        points = []
        for index, row in enumerate(training):
            px = plot_x + index * plot_w / (len(training) - 1)
            py = plot_y + plot_h * (1 - float(row[key]) / maximum)
            points.append((px, py))
            if key == "training_loss":
                output.append(text(px, plot_y + plot_h + 20, row["epoch"], 10, COLORS["muted"], anchor="middle"))
        path = " ".join(f"{'M' if i == 0 else 'L'}{px:.2f},{py:.2f}" for i, (px, py) in enumerate(points))
        output.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        for px, py in points:
            output.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{color}"/>')
    output.extend(
        [
            line(x0 + 335, y0 + 30, x0 + 359, y0 + 30, COLORS["train"], 3),
            text(x0 + 365, y0 + 34, "Training", 11),
            line(x0 + 435, y0 + 30, x0 + 459, y0 + 30, COLORS["validation"], 3),
            text(x0 + 465, y0 + 34, "Validation", 11),
            text(plot_x + plot_w / 2, y0 + height - 12, "Epoch (recorded run)", 11, COLORS["muted"], anchor="middle"),
        ]
    )
    return "".join(output)


def overall_panel(model, baseline):
    x0, y0, width, height = 620, 150, 600, 300
    plot_x, plot_w = x0 + 175, width - 215
    output = [
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="12" fill="{COLORS["paper"]}" stroke="{COLORS["grid"]}"/>',
        text(x0 + 20, y0 + 30, "PCK@0.1 with image-bootstrap 95% intervals", 18, weight=700),
        text(x0 + 20, y0 + 50, "Oracle-box-center baseline is diagnostic, not deployable.", 12, COLORS["muted"]),
    ]
    max_x = 0.065
    axis_y = y0 + 245
    for tick in (0, 0.02, 0.04, 0.06):
        px = plot_x + tick / max_x * plot_w
        output.append(line(px, y0 + 78, px, axis_y, dash="3 4"))
        output.append(text(px, axis_y + 17, f"{tick:.2f}", 10, COLORS["muted"], anchor="middle"))
    for index, (label, item, color) in enumerate(
        (
            ("PetLens model", model, COLORS["model"]),
            ("Box-center baseline", baseline, COLORS["baseline"]),
        )
    ):
        y = y0 + 112 + index * 72
        ci = item["bootstrap_95_ci_by_image"]
        low, high, score = ci["lower"], ci["upper"], item["overall"]
        low_x, high_x = plot_x + low / max_x * plot_w, plot_x + high / max_x * plot_w
        score_x = plot_x + score / max_x * plot_w
        output.append(text(x0 + 20, y - 5, label, 13, weight=700))
        output.append(
            text(x0 + 20, y + 15, f'{item["correct"]}/{item["visible_keypoints"]} = {score:.4f}', 12, COLORS["muted"])
        )
        output.append(line(low_x, y, high_x, y, color, 4))
        output.append(line(low_x, y - 7, low_x, y + 7, color, 2))
        output.append(line(high_x, y - 7, high_x, y + 7, color, 2))
        output.append(f'<circle cx="{score_x:.2f}" cy="{y}" r="6" fill="{color}"/>')
    output.append(text(plot_x + plot_w / 2, y0 + height - 12, "Proportion correct (PCK)", 11, COLORS["muted"], anchor="middle"))
    return "".join(output)


def keypoint_panel(model, baseline):
    x0, y0, width, height = 60, 475, 1160, 470
    plot_x, plot_w = x0 + 245, 500
    max_x = 0.20
    output = [
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="12" fill="{COLORS["paper"]}" stroke="{COLORS["grid"]}"/>',
        text(x0 + 20, y0 + 30, "PCK@0.1 by AP-10K keypoint", 18, weight=700),
        text(x0 + 20, y0 + 50, "Bars show point estimates; exact visible-keypoint counts are printed at right.", 12, COLORS["muted"]),
        line(x0 + 650, y0 + 30, x0 + 672, y0 + 30, COLORS["model"], 6),
        text(x0 + 678, y0 + 34, "PetLens model", 11),
        line(x0 + 790, y0 + 30, x0 + 812, y0 + 30, COLORS["baseline"], 6),
        text(x0 + 818, y0 + 34, "Box-center baseline", 11),
    ]
    for tick in (0, 0.05, 0.10, 0.15, 0.20):
        px = plot_x + tick / max_x * plot_w
        output.append(line(px, y0 + 72, px, y0 + 423, dash="3 4"))
        output.append(text(px, y0 + 440, f"{tick:.2f}", 10, COLORS["muted"], anchor="middle"))
    model_points = model["per_keypoint"]
    baseline_points = baseline["per_keypoint"]
    for index, key in enumerate(model_points):
        y = y0 + 88 + index * 19.2
        own, reference = model_points[key], baseline_points[key]
        model_length = float(own["pck"]) / max_x * plot_w
        baseline_length = float(reference["pck"]) / max_x * plot_w
        output.append(text(x0 + 20, y + 4, key.replace("_", " "), 11))
        output.append(f'<rect x="{plot_x}" y="{y - 7}" width="{model_length:.2f}" height="6" fill="{COLORS["model"]}"/>')
        output.append(f'<rect x="{plot_x}" y="{y + 1}" width="{baseline_length:.2f}" height="6" fill="{COLORS["baseline"]}"/>')
        output.append(
            text(
                plot_x + plot_w + 12,
                y + 4,
                f'model {own["correct"]}/{own["visible"]}; baseline {reference["correct"]}/{reference["visible"]}',
                10,
                COLORS["muted"],
            )
        )
    output.append(text(plot_x + plot_w / 2, y0 + height - 12, "Proportion correct (PCK@0.1)", 11, COLORS["muted"], anchor="middle"))
    return "".join(output)


def main():
    training, model, baseline = load_inputs()
    warning = (
        "Retrospective diagnostic only: test results were inspected during development; "
        "not independent held-out evidence and not a performance claim."
    )
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{COLORS["paper"]}"/>',
        text(60, 52, "PetLens canine-pose experiment", 30, weight=700),
        text(60, 82, "AP-10K dog-only ResNet-18 heatmap · random initialization · exploratory localization", 15, COLORS["muted"]),
        f'<rect x="60" y="103" width="1160" height="34" rx="6" fill="{COLORS["warning"]}"/>',
        text(76, 125, warning, 12, COLORS["ink"], weight=700),
        training_panel(training),
        overall_panel(model, baseline),
        keypoint_panel(model, baseline),
        text(60, 975, "Epoch-2 test metrics are shown; epoch-2 weights were overwritten. Epoch-4 weights used the old loss normalization and were not evaluated.", 12, COLORS["muted"]),
        text(60, 998, "Oracle ground-truth boxes; 225 dog instances / 200 images; 2,269 visible keypoints. AP-10K is still-image data, not gait or OA evidence.", 12, COLORS["muted"]),
        "</svg>",
    ]
    OUTPUT_SVG.write_text("\n".join(svg), encoding="utf-8")
    print(OUTPUT_SVG.relative_to(ROOT))


if __name__ == "__main__":
    main()
