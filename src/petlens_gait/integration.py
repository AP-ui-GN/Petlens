"""Connect experimental paw tracking and segment recovery to V2 gait analysis."""

import importlib.util
import sys
from pathlib import Path

from petlens_gait.pipeline import analyze_gait


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def analyze_predictions(predictions, experiment_root):
    """Analyze saved AP-10K predictions without linking segment identities."""
    frames = predictions["frames"]

    if not frames:
        return {
            "analysisType": "exploratory_hind_paw_gait",
            "frameCount": 0,
            "restartAccepted": False,
            "segments": [],
        }

    root = Path(experiment_root)
    association = _load_module(
        "petlens_v2_association",
        root / "dog02-identity-association/associate.py",
    )
    recovery = _load_module(
        "petlens_v2_recovery",
        root / "segment-recovery-v2/recovery.py",
    )

    # Frame dimensions must come from the source, not a hardcoded video.
    width = predictions["width"]
    height = predictions["height"]

    recovered = recovery.recover_segments(
        frames, width, height, association.associate
    )

    segments = []
    for segment in recovered["segments"]:
        start = segment["startFrame"]
        end = segment["endFrame"]
        source = [
            frame for frame in frames
            if start <= frame["frameIndex"] <= end
        ]
        report = analyze_gait(source, segment["result"]["frames"])

        segments.append({
            "segmentId": segment["segmentId"],
            "startFrame": start,
            "endFrame": end,
            "trackingCoverage": report["trackingCoverage"],
            "report": report,
        })

    return {
        "analysisType": "exploratory_hind_paw_gait",
        "frameCount": len(frames),
        "restartAccepted": recovered["restartAccepted"],
        "segments": segments,
        "limitations": [
            "Physical paw identities are independent across segments.",
            "Candidate cycles are not verified walking strides.",
            "Tracking coverage does not establish anatomical accuracy.",
            "This analysis is not a veterinary diagnosis.",
        ],
    }
