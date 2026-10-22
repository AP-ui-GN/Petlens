#!/usr/bin/env python3
"""Validate and canonicalize AP-10K's official train/val/test annotations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from gait_engine.ap10k_data import DatasetValidationError, prepare_ap10k


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate official AP-10K COCO annotations and write canonical splits."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split-number", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument(
        "--skip-image-check",
        action="store_true",
        help="Validate annotations without opening source images; not suitable for training.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    annotation_dir = args.dataset_root / "annotations"
    split_files = {
        split: annotation_dir / f"ap10k-{split}-split{args.split_number}.json"
        for split in ("train", "val", "test")
    }
    try:
        manifest = prepare_ap10k(
            args.dataset_root,
            args.output_dir,
            split_files,
            verify_images=not args.skip_image_check,
        )
    except (DatasetValidationError, OSError) as exc:
        print(f"AP-10K preparation failed: {exc}", file=sys.stderr)
        return 2
    for split, details in manifest["splits"].items():
        print(f"{split}: {details['annotation_count']} annotations -> {details['file']}")
    print(f"schema: {manifest['schema_version']}")
    print(f"identity grouping: {manifest['identity_grouping']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
