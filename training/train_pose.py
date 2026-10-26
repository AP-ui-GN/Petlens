#!/usr/bin/env python3
"""Train an AP-10K dog-only top-down heatmap model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPOSITORY_ROOT / "training" / "dataset_config.yaml",
    )
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--device", default=None)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--prepared-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    return parser.parse_args()


def _load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "Optional training packages are missing. Install requirements-training.txt."
        ) from exc
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Could not read training config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Training config is invalid YAML: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("Training configuration must be a YAML object.")
    return config


def _seed_worker(worker_id: int) -> None:
    import numpy as np
    import torch

    seed = torch.initial_seed() % (2**32)
    np.random.seed(seed)
    random.seed(seed)


def _loss(outputs, targets, weights, torch):
    per_keypoint_error = (outputs - targets).square().sum(dim=(-2, -1))
    target_energy = targets.square().sum(dim=(-2, -1)).clamp_min(1e-6)
    normalized_error = per_keypoint_error / target_energy
    denominator = weights.sum().clamp_min(1)
    return (normalized_error * weights).sum() / denominator


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_epoch(model, loader, device, torch, optimizer=None) -> float:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_samples = 0
    context = torch.enable_grad if training else torch.no_grad
    with context():
        for images, targets, weights, _points, _crops in loader:
            images = images.to(device)
            targets = targets.to(device)
            weights = weights.to(device)
            if training:
                optimizer.zero_grad(set_to_none=True)
            outputs = model(images)
            loss = _loss(outputs, targets, weights, torch)
            if training:
                loss.backward()
                optimizer.step()
            batch_size = images.shape[0]
            total_loss += float(loss.detach().item()) * batch_size
            total_samples += batch_size
    if total_samples == 0:
        raise ValueError("Cannot train or validate on an empty dataset.")
    return total_loss / total_samples


def _save_checkpoint(path: Path, checkpoint: dict[str, Any], torch) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        torch.save(checkpoint, temporary_path)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def run_training(args: argparse.Namespace) -> int:
    try:
        import torch
        import yaml  # noqa: F401 - checked with the other optional dependency
    except ImportError as exc:
        raise RuntimeError(
            "Optional training packages are missing. Install requirements-training.txt."
        ) from exc

    from gait_engine.ap10k_data import SCHEMA_VERSION
    from gait_engine.pose_backend import AP10K_KEYPOINTS
    from training.data import AP10KHeatmapDataset
    from training.pose_model import build_model

    config = _load_config(args.config)
    dataset_config = config.get("dataset", {})
    model_config = config.get("model", {})
    training_config = config.get("training", {})
    if not all(
        isinstance(section, dict)
        for section in (dataset_config, model_config, training_config)
    ):
        raise ValueError("Training config must contain dataset, model, and training objects.")
    if args.dataset_root is not None:
        dataset_config["root"] = str(args.dataset_root)
    if args.prepared_dir is not None:
        dataset_config["prepared_dir"] = str(args.prepared_dir)
    if args.output_dir is not None:
        training_config["output_dir"] = str(args.output_dir)
    if args.epochs is not None:
        training_config["epochs"] = args.epochs
    if args.batch_size is not None:
        training_config["batch_size"] = args.batch_size
    if dataset_config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("The training config must name the active AP-10K schema version.")
    if model_config.get("initialization") != "random":
        raise ValueError("Only random model initialization is supported by this trainer.")
    if model_config.get("architecture") != "resnet18-topdown-heatmap":
        raise ValueError("Unsupported pose architecture in training config.")

    dataset_root = Path(dataset_config["root"]).expanduser()
    prepared_dir = Path(dataset_config["prepared_dir"]).expanduser()
    species = str(dataset_config.get("species", "dog"))
    input_size = (
        int(model_config["input_width"]),
        int(model_config["input_height"]),
    )
    heatmap_size = (
        int(model_config["heatmap_width"]),
        int(model_config["heatmap_height"]),
    )
    seed = int(training_config["seed"])
    epochs = int(training_config["epochs"])
    patience = int(training_config["patience"])
    batch_size = int(training_config["batch_size"])
    worker_count = int(training_config["num_workers"])
    if epochs <= 0 or patience <= 0 or batch_size <= 0 or worker_count < 0:
        raise ValueError(
            "epochs, patience, and batch_size must be positive; num_workers cannot be negative."
        )
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable.")

    common = {
        "species": species,
        "input_size": input_size,
        "heatmap_size": heatmap_size,
        "gaussian_sigma": float(training_config["gaussian_sigma"]),
    }
    image_root = dataset_root / "data"
    train_data = AP10KHeatmapDataset(
        prepared_dir / "train.json",
        image_root,
        augment=True,
        horizontal_flip_probability=float(
            training_config["horizontal_flip_probability"]
        ),
        **common,
    )
    validation_data = AP10KHeatmapDataset(
        prepared_dir / "val.json",
        image_root,
        augment=False,
        **common,
    )
    seed_generator = torch.Generator().manual_seed(seed)
    loader_options = {
        "batch_size": batch_size,
        "num_workers": worker_count,
        "pin_memory": device.type == "cuda",
        "worker_init_fn": _seed_worker,
    }
    train_loader = torch.utils.data.DataLoader(
        train_data,
        shuffle=True,
        generator=seed_generator,
        **loader_options,
    )
    validation_loader = torch.utils.data.DataLoader(
        validation_data,
        shuffle=False,
        **loader_options,
    )

    output_root = Path(training_config["output_dir"]).expanduser()
    if not output_root.is_absolute():
        output_root = REPOSITORY_ROOT / output_root
    manifest_path = prepared_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Prepared dataset manifest is required to identify the data: {manifest_path}"
        )
    dataset_identity = {
        "manifest_file": manifest_path.name,
        "manifest_sha256": _sha256_file(manifest_path),
        "train_annotations_sha256": _sha256_file(prepared_dir / "train.json"),
        "validation_annotations_sha256": _sha256_file(prepared_dir / "val.json"),
    }
    effective_config_sha256 = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    model = build_model().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training_config["learning_rate"]),
        weight_decay=float(training_config["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )
    start_epoch = 0
    best_validation_loss = float("inf")
    stale_epochs = 0
    run_id = str(uuid4())
    parent_run_id = None
    parent_checkpoint_sha256 = None
    resumed_checkpoint = None
    if args.resume is not None:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=True)
        if checkpoint.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Resume checkpoint uses a different keypoint schema.")
        if checkpoint.get("keypoints") != list(AP10K_KEYPOINTS):
            raise ValueError("Resume checkpoint keypoint ordering is incompatible.")
        saved_dataset = checkpoint.get("dataset", {})
        if saved_dataset.get("train_annotations_sha256") != dataset_identity["train_annotations_sha256"] or (
            saved_dataset.get("validation_annotations_sha256")
            != dataset_identity["validation_annotations_sha256"]
        ):
            raise ValueError(
                "Resume checkpoint was trained with different or unidentified data splits."
            )
        model.load_state_dict(checkpoint["model_state"])
        optimizer.load_state_dict(checkpoint["optimizer_state"])
        if "scheduler_state" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler_state"])
        start_epoch = int(checkpoint["epoch"])
        best_validation_loss = float(checkpoint["best_validation_loss"])
        stale_epochs = int(checkpoint.get("stale_epochs", 0))
        parent_run_id = str(checkpoint["run_id"])
        parent_checkpoint_sha256 = _sha256_file(args.resume)
        resumed_checkpoint = checkpoint
        if "python_random_state" in checkpoint:
            random.setstate(checkpoint["python_random_state"])
        if "torch_random_state" in checkpoint:
            torch.set_rng_state(checkpoint["torch_random_state"])
        if "loader_generator_state" in checkpoint:
            seed_generator.set_state(checkpoint["loader_generator_state"])
        if device.type == "cuda" and checkpoint.get("cuda_random_state"):
            torch.cuda.set_rng_state_all(checkpoint["cuda_random_state"])

    if start_epoch >= epochs:
        raise ValueError(
            f"Checkpoint is already at epoch {start_epoch}; configured epochs is {epochs}."
        )
    output_dir = output_root / f"experiment-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    history_path = output_dir / "training_metrics.jsonl"
    started_at = time.monotonic()
    best_epoch = 0
    if resumed_checkpoint is not None:
        # Recheck the resumed model, then seed the new run's best checkpoint.
        best_validation_loss = _run_epoch(
            model, validation_loader, device, torch
        )
        stale_epochs = 0
        best_epoch = start_epoch
        initial_checkpoint = {
            **resumed_checkpoint,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "parent_checkpoint_sha256": parent_checkpoint_sha256,
            "seed": seed,
            "validation_loss": best_validation_loss,
            "best_validation_loss": best_validation_loss,
            "stale_epochs": stale_epochs,
            "training_config": config,
            "dataset": {
                "name": "AP-10K",
                "species_filter": species,
                "train_instances": len(train_data),
                "validation_instances": len(validation_data),
                **dataset_identity,
                "test_split_previously_inspected": True,
                "test_used_for_selection": False,
            },
        }
        _save_checkpoint(output_dir / "checkpoint_last.pt", initial_checkpoint, torch)
        _save_checkpoint(output_dir / "checkpoint_best.pt", initial_checkpoint, torch)

    # Train on the training split and select checkpoints by validation loss.
    for epoch in range(start_epoch, epochs):
        training_loss = _run_epoch(model, train_loader, device, torch, optimizer)
        validation_loss = _run_epoch(model, validation_loader, device, torch)
        scheduler.step(validation_loss)
        improved = validation_loss < best_validation_loss
        if improved:
            best_validation_loss = validation_loss
            stale_epochs = 0
            best_epoch = epoch + 1
        else:
            stale_epochs += 1
        row = {
            "epoch": epoch + 1,
            "seed": seed,
            "training_loss": training_loss,
            "validation_loss": validation_loss,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "best_validation_loss": best_validation_loss,
        }
        with history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(row, allow_nan=False) + "\n")
        checkpoint = {
            "format_version": 1,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "parent_checkpoint_sha256": parent_checkpoint_sha256,
            "epoch": epoch + 1,
            "seed": seed,
            "validation_loss": validation_loss,
            "model_name": "PetLens AP-10K dog-only ResNet-18 heatmap (experimental)",
            "architecture": "resnet18-topdown-heatmap",
            "initialization": "random",
            "schema_version": SCHEMA_VERSION,
            "keypoints": list(AP10K_KEYPOINTS),
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "best_validation_loss": best_validation_loss,
            "stale_epochs": stale_epochs,
            "python_random_state": random.getstate(),
            "torch_random_state": torch.get_rng_state(),
            "loader_generator_state": seed_generator.get_state(),
            "cuda_random_state": (
                torch.cuda.get_rng_state_all() if device.type == "cuda" else []
            ),
            "training_config": config,
            "dataset": {
                "name": "AP-10K",
                "species_filter": species,
                "train_instances": len(train_data),
                "validation_instances": len(validation_data),
                **dataset_identity,
                "test_split_previously_inspected": True,
                "test_used_for_selection": False,
            },
        }
        _save_checkpoint(output_dir / "checkpoint_last.pt", checkpoint, torch)
        if improved:
            _save_checkpoint(output_dir / "checkpoint_best.pt", checkpoint, torch)
        print(json.dumps(row, allow_nan=False), flush=True)
        if stale_epochs >= patience:
            break

    best_checkpoint_path = output_dir / "checkpoint_best.pt"
    metadata = {
        "experiment_id": run_id,
        "parent_experiment_id": parent_run_id,
        "parent_checkpoint_sha256": parent_checkpoint_sha256,
        "status": "completed",
        "model_artifact": best_checkpoint_path.name,
        "model_artifact_sha256": _sha256_file(best_checkpoint_path),
        "experiment_directory": str(output_dir),
        "architecture": "resnet18-topdown-heatmap",
        "initialization": "random",
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "keypoints": list(AP10K_KEYPOINTS),
        "dataset": {
            "name": "AP-10K",
            "species_filter": species,
            "train_instances": len(train_data),
            "validation_instances": len(validation_data),
            **dataset_identity,
            "test_split_previously_inspected": True,
            "test_split_used_for_selection": False,
        },
        "epochs_completed": epoch + 1,
        "best_checkpoint_epoch": best_epoch,
        "epochs_this_run": epoch + 1 - start_epoch,
        "best_validation_loss": best_validation_loss,
        "duration_seconds_this_run": time.monotonic() - started_at,
        "config_sha256": _sha256_file(args.config),
        "effective_config_sha256": effective_config_sha256,
        "training_config": config,
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "torch_version": torch.__version__,
            "device": str(device),
        },
    }
    (output_dir / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Best checkpoint: {best_checkpoint_path}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run_training(args)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Canine pose training failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
