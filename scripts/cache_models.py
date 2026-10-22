#!/usr/bin/env python3
"""Download the dog detector and the AP-10K pose model into HF_HOME.

    python scripts/cache_models.py

HF_HOME defaults to models/hf. The directory is gitignored.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def main() -> int:
    from gait_engine.pose_backend import DETECTOR_ID, POSE_ID, hf_home

    home = hf_home()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(home)
    try:
        from transformers import (
            RTDetrForObjectDetection,
            RTDetrImageProcessor,
            VitPoseForPoseEstimation,
            VitPoseImageProcessor,
        )
    except ImportError as exc:
        print(f"torch or transformers is not installed: {exc}", file=sys.stderr)
        return 1

    print(f"Caching {DETECTOR_ID} and {POSE_ID} in {home}")
    RTDetrImageProcessor.from_pretrained(DETECTOR_ID)
    RTDetrForObjectDetection.from_pretrained(DETECTOR_ID)
    VitPoseImageProcessor.from_pretrained(POSE_ID)
    VitPoseForPoseEstimation.from_pretrained(POSE_ID)
    print("Model cache ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
