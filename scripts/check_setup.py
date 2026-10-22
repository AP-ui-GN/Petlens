#!/usr/bin/env python3
"""Report Python, OpenCV, and whether pose weights are already on disk.

    python scripts/check_setup.py

The command reads the local Hugging Face cache only. It does not download
weights and it does not run the pose model. Exit 0 when OpenCV imports.
Exit 1 when OpenCV is missing. Missing weights are reported and are not a
failure, because a new clone does not have them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local PetLens analysis setup without downloading weights.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write machine-readable JSON for readiness probes.",
    )
    args = parser.parse_args()

    from gait_engine.setup_check import collect_setup, format_setup

    report = collect_setup()
    if args.json:
        sys.stdout.write(json.dumps(report, separators=(",", ":")) + "\n")
        # The readiness probe needs to inspect the report even when OpenCV is
        # unavailable, so JSON mode uses the report's fallbackReady field.
        return 0
    sys.stdout.write(format_setup(report))
    if report["opencv"] is None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
