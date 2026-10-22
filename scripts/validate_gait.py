#!/usr/bin/env python3
"""Compare labeled clips. This is preliminary, not clinical validation.

    python scripts/validate_gait.py --clips-dir validation_clips \\
        --labels validation_clips/labels.csv --out outputs/validation.csv

If the folder has no clips, this prints how to add them and exits 0.
Do not commit the clips.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

HOW_TO = """
validation_clips/ is gitignored, so videos are not committed.
Add clips and validation_clips/labels.csv there.
Columns: file,label,source,license,notes
label is one of: normal, mild, significant

Then run:
  python scripts/validate_gait.py --clips-dir validation_clips \\
      --labels validation_clips/labels.csv --out outputs/validation.csv

The output is preliminary, a small sample, and not clinical validation.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize labeled gait clips.")
    parser.add_argument("--clips-dir", type=Path, default=Path("validation_clips"))
    parser.add_argument("--labels", type=Path, default=Path("validation_clips/labels.csv"))
    parser.add_argument("--out", type=Path, default=Path("outputs/validation.csv"))
    return parser.parse_args()


def mann_whitney_u(left: list[float], right: list[float]) -> tuple[float | None, float | None]:
    """Two-sided Mann–Whitney U with a normal approximation. NumPy only."""

    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size == 0 or b.size == 0:
        return None, None
    combined = np.concatenate([a, b])
    order = np.argsort(combined, kind="mergesort")
    ranks = np.empty(combined.size, dtype=np.float64)
    ranks[order] = np.arange(1, combined.size + 1, dtype=np.float64)
    # Average ties.
    sorted_values = combined[order]
    start = 0
    while start < sorted_values.size:
        end = start + 1
        while end < sorted_values.size and sorted_values[end] == sorted_values[start]:
            end += 1
        if end - start > 1:
            tied = ranks[order[start:end]]
            ranks[order[start:end]] = float(np.mean(tied))
        start = end
    rank_sum = float(np.sum(ranks[: a.size]))
    u_stat = rank_sum - a.size * (a.size + 1) / 2.0
    mean = a.size * b.size / 2.0
    if a.size + b.size < 2:
        return u_stat, None
    tie_term = 0.0
    _, counts = np.unique(combined, return_counts=True)
    for count in counts:
        if count > 1:
            tie_term += count * (count - 1) * (count + 1)  # count**3 - count
    n = a.size + b.size
    variance = a.size * b.size / 12.0 * ((n + 1) - tie_term / (n * (n - 1)))
    if variance <= 0:
        return u_stat, None
    z_score = (u_stat - mean) / np.sqrt(variance)
    # Two-sided normal tail without scipy.
    p_value = float(np.erfc(abs(z_score) / np.sqrt(2.0)))
    return float(u_stat), p_value


def main() -> int:
    args = parse_args()
    clips = []
    if args.clips_dir.is_dir():
        clips = [
            path
            for path in args.clips_dir.iterdir()
            if path.suffix.lower() in {".mp4", ".mov", ".webm", ".avi"}
        ]
    if not clips or not args.labels.is_file():
        print(HOW_TO.strip())
        print("\npreliminary, small sample, not clinical validation.")
        print("Validation did not run: no labeled clips were found.")
        return 0

    from gait_engine.pipeline import analyze_clip

    rows = []
    with args.labels.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(record)
    by_file = {row.get("file", ""): row for row in rows}
    fieldnames = [
        "file",
        "label",
        "source",
        "license",
        "notes",
        "pipeline",
        "dogFramesShare",
        "meanKeypointScore",
        "frontLeftStrides",
        "frontRightStrides",
        "rearLeftStrides",
        "rearRightStrides",
        "frontSymmetry",
        "rearSymmetry",
        "headBobAsymmetry",
        "pelvisAsymmetry",
        "notMeasuredReasons",
        "seconds",
    ]
    written = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for clip in sorted(clips):
        label_row = by_file.get(clip.name, {})
        started = time.perf_counter()
        result = analyze_clip(clip)
        elapsed = time.perf_counter() - started
        measurements = result.get("measurements") or {}
        strides = measurements.get("strides") or {}
        limb = measurements.get("limbSymmetry") or {}
        subject = measurements.get("subject") or {}
        written.append({
            "file": clip.name,
            "label": label_row.get("label", ""),
            "source": label_row.get("source", ""),
            "license": label_row.get("license", ""),
            "notes": label_row.get("notes", ""),
            "pipeline": result.get("pipeline"),
            "dogFramesShare": subject.get("dogFramesShare"),
            "meanKeypointScore": measurements.get("meanKeypointConfidence"),
            "frontLeftStrides": (strides.get("frontLeft") or {}).get("strideCount"),
            "frontRightStrides": (strides.get("frontRight") or {}).get("strideCount"),
            "rearLeftStrides": (strides.get("rearLeft") or {}).get("strideCount"),
            "rearRightStrides": (strides.get("rearRight") or {}).get("strideCount"),
            "frontSymmetry": limb.get("front"),
            "rearSymmetry": limb.get("rear"),
            "headBobAsymmetry": measurements.get("headBobAsymmetry"),
            "pelvisAsymmetry": measurements.get("pelvisAsymmetry"),
            "notMeasuredReasons": " | ".join(measurements.get("notMeasuredReasons") or []),
            "seconds": round(elapsed, 3),
        })
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(written)

    print("preliminary, small sample, not clinical validation.")
    for label in ("normal", "mild", "significant"):
        group = [row for row in written if row["label"] == label]
        if not group:
            print(f"{label}: no clips")
            continue
        for column in ("frontSymmetry", "rearSymmetry", "headBobAsymmetry", "pelvisAsymmetry"):
            values = [row[column] for row in group if isinstance(row[column], (int, float))]
            if not values:
                print(f"{label} {column} median: not measured")
            else:
                print(f"{label} {column} median: {float(np.median(values)):.4f}")
    normal = [row["frontSymmetry"] for row in written if row["label"] == "normal" and isinstance(row["frontSymmetry"], (int, float))]
    significant = [row["frontSymmetry"] for row in written if row["label"] == "significant" and isinstance(row["frontSymmetry"], (int, float))]
    u_stat, p_value = mann_whitney_u(normal, significant)
    if u_stat is None:
        print("Mann–Whitney U on front symmetry, normal vs significant: not computed")
    else:
        p_text = "not computed" if p_value is None else f"{p_value:.4f}"
        print(f"Mann–Whitney U on front symmetry, normal vs significant: U={u_stat:.3f}, two-sided p≈{p_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
