#!/usr/bin/env python3
"""Compute pose-only PCK for predictions aligned to prepared AP-10K instances."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from gait_engine.ap10k_data import DatasetValidationError
from gait_engine.pose_eval import evaluate_ap10k_pck


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate AP-10K keypoint PCK with ground-truth boxes."
    )
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--thresholds", type=float, nargs="+", default=(0.05, 0.1))
    parser.add_argument("--minimum-confidence", type=float, default=0.0)
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(f"Could not read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DatasetValidationError(f"Expected a JSON object in {path}.")
    return payload


def main() -> int:
    args = parse_args()
    try:
        report = evaluate_ap10k_pck(
            _read_json(args.annotations),
            _read_json(args.predictions),
            thresholds=args.thresholds,
            minimum_confidence=args.minimum_confidence,
        )
        content = json.dumps(report, indent=2) + "\n"
        if args.out is None:
            print(content, end="")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(content, encoding="utf-8")
            print(f"Wrote pose-only PCK report to {args.out}")
    except (DatasetValidationError, OSError) as exc:
        print(f"AP-10K evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
