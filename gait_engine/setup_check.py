"""Report the local analysis toolchain.

Reading a config file that is already on disk is allowed. This module does
not call Hugging Face, does not import torch, and does not download weights.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from .pose_backend import COCO17_KEYPOINTS, DETECTOR_ID, POSE_ID, hf_home

WEIGHT_NAMES = ("model.safetensors", "pytorch_model.bin")


def _repo_dir(root: Path, model_id: str) -> Path:
    folder = "models--" + model_id.replace("/", "--")
    hub = root / "hub" / folder
    if hub.is_dir():
        return hub
    return root / folder


def _snapshots(repo: Path) -> list[Path]:
    snapshot_root = repo / "snapshots"
    if not snapshot_root.is_dir():
        return []
    return sorted(path for path in snapshot_root.iterdir() if path.is_dir())


def _ready_file(path: Path) -> bool:
    """True only when the path is a real file. A broken symlink is absent."""

    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _read_id2label(config_path: Path) -> dict[str, str] | None:
    try:
        payload = json.loads(config_path.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError):
        return None
    labels = payload.get("id2label")
    if not isinstance(labels, dict):
        return None
    return {str(key): str(value) for key, value in labels.items()}


def _schema_from_labels(labels: dict[str, str] | None) -> str:
    if not labels:
        return "absent"
    ordered = [labels.get(str(index), "") for index in range(len(COCO17_KEYPOINTS))]
    expected = {
        "nose": "nose",
        "left_eye": "l_eye",
        "right_eye": "r_eye",
        "left_ear": "l_ear",
        "right_ear": "r_ear",
        "left_shoulder": "l_shoulder",
        "right_shoulder": "r_shoulder",
        "left_elbow": "l_elbow",
        "right_elbow": "r_elbow",
        "left_wrist": "l_wrist",
        "right_wrist": "r_wrist",
        "left_hip": "l_hip",
        "right_hip": "r_hip",
        "left_knee": "l_knee",
        "right_knee": "r_knee",
        "left_ankle": "l_ankle",
        "right_ankle": "r_ankle",
    }
    normalized = [value.strip().lower() for value in ordered]
    if normalized == [expected[name] for name in COCO17_KEYPOINTS]:
        return "coco-17"
    return "unverified"


def inspect_model(root: Path, model_id: str) -> dict[str, object]:
    """Look at one cached Hugging Face repo. Missing files stay missing."""

    snapshots = _snapshots(_repo_dir(root, model_id))
    config_path: Path | None = None
    weight_path: Path | None = None
    for snapshot in snapshots:
        candidate = snapshot / "config.json"
        if config_path is None and _ready_file(candidate):
            config_path = candidate
        for name in WEIGHT_NAMES:
            weight = snapshot / name
            if weight_path is None and _ready_file(weight):
                weight_path = weight
    labels = _read_id2label(config_path) if config_path is not None else None
    return {
        "modelId": model_id,
        "configPresent": config_path is not None,
        "weightsPresent": weight_path is not None,
        "schema": _schema_from_labels(labels),
        "channel4": None if labels is None else labels.get("4"),
    }


def opencv_version() -> str | None:
    try:
        import cv2
    except ImportError:
        return None
    return str(cv2.__version__)


def collect_setup(root: Path | None = None) -> dict[str, object]:
    """Build the report. ``root`` defaults to the project weight cache."""

    cache = root if root is not None else hf_home()
    pose = inspect_model(cache, POSE_ID)
    detector = inspect_model(cache, DETECTOR_ID)
    dependencies = {
        "torch": importlib.util.find_spec("torch") is not None,
        "transformers": importlib.util.find_spec("transformers") is not None,
    }
    opencv = opencv_version()
    return {
        "python": sys.version.split()[0],
        "opencv": opencv,
        "pose": pose,
        "detector": detector,
        "poseDependencies": dependencies,
        "poseReady": (
            dependencies["torch"]
            and dependencies["transformers"]
            and pose["weightsPresent"]
            and detector["weightsPresent"]
            and pose["schema"] == "coco-17"
        ),
        "caninePoseReady": False,
        "fallbackReady": opencv is not None,
        "downloadsWeights": False,
    }


def format_setup(report: dict[str, object]) -> str:
    pose = report["pose"]
    detector = report["detector"]
    assert isinstance(pose, dict)
    assert isinstance(detector, dict)
    opencv = report["opencv"] or "not importable"
    lines = [
        f"Python {report['python']}",
        f"OpenCV {opencv}",
        f"Pose weights: {'present' if pose['weightsPresent'] else 'absent'} ({pose['modelId']})",
        f"Pose config: {'present' if pose['configPresent'] else 'absent'}",
        f"Pose schema: {pose['schema']}",
        f"Pose channel 4: {pose['channel4'] if pose['channel4'] is not None else 'absent'}",
        f"Detector weights: {'present' if detector['weightsPresent'] else 'absent'} ({detector['modelId']})",
        f"Pose dependencies: {'present' if all(report['poseDependencies'].values()) else 'incomplete'} (torch + transformers)",
        f"COCO pose capability cached: {'yes' if report['poseReady'] else 'no'}",
        "Validated canine pose capability: no",
        "This command does not download weights.",
    ]
    return "\n".join(lines) + "\n"
