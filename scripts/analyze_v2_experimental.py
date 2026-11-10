"""Experimental PetLens V2 video-to-gait report runner. Not a clinical assessment."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from petlens_gait.inference import Models, infer
from petlens_gait.integration import analyze_predictions

EXPERIMENT = ROOT / "tmp/rtmpose-test/multi-video-evaluation"
POSE = EXPERIMENT / "models/rtmpose-ap10k.onnx"
REVISION = "457857cec8ac28ddede40ecee9eed2beca321af8"
POSE_SHA256 = "1cfd1c86e0d9e5d5f95178bcd95ee9a4e8386a624cd3c57519f27ff58cac7f28"
TRACKING = ROOT / "tmp/rtmpose-test/paw-tracking-experiment"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    video = args.video.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    if hashlib.sha256(POSE.read_bytes()).hexdigest() != POSE_SHA256:
        raise ValueError("Pose model fingerprint mismatch")

    os.environ.setdefault("HF_HUB_CACHE", str(EXPERIMENT / "cache/huggingface/hub"))
    model = Models(POSE, REVISION)
    predictions = infer(video, output, model)

    (output / "predictions.json").write_text(
        json.dumps(predictions, indent=2, allow_nan=False)
    )
    report = analyze_predictions(predictions, TRACKING)
    report["experimental"] = True
    report["video"] = str(video)
    (output / "gait-report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)
    )

    print(json.dumps({
        "status": "complete",
        "experimental": True,
        "frames": report["frameCount"],
        "segments": len(report["segments"]),
        "report": str(output / "gait-report.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
