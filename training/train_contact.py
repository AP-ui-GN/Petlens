"""Scratch canine temporal training. Real data only; no synthetic CLI mode.

Rebuilds hash-checked inputs on every run. Strict mode retains independent
review, full-paw coverage and validation gates. Explicitly owner-authorized
exploratory_train_only permits sparse single-dog state fitting without validation.
Test data is never loaded into model selection or reported metrics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from petlens_gait import contact_features as c
from training import prepare_contact_sequences as prep


def gather_window(arrays, row, physical=False):
    """Preserve order/timing; never gather -1 as a real source frame."""
    row = np.asarray(row)
    c.require(row.ndim == 1 and np.issubdtype(row.dtype, np.integer), "Invalid window")
    valid = row >= 0
    c.require(valid.any() and np.all(row[~valid] == -1) and
              not np.any(np.diff(valid.astype(int)) > 0), "Invalid padding")
    indices = row[valid]
    c.require(np.all(indices < len(arrays["features"])) and np.all(np.diff(indices) == 1),
              "Window must retain consecutive source frames")
    c.require(np.all(np.diff(arrays["timestamps"][indices]) > 0) and
              np.all(np.diff(arrays["timestamps"][indices]) <= c.POLICY["maxGapSeconds"]),
              "Window timing discontinuity")
    c.require(arrays["reference_valid"][indices].all(), "Invalid body reference in window")
    prefix = "physical_" if physical else ""
    identities = arrays[prefix+"identity_segments"][indices]
    c.require(np.all(identities == identities[:1]), "Window crosses identity boundary")
    features = np.zeros((len(row), len(c.CHANNELS)), dtype=np.float32)
    targets = np.zeros((len(row), 1 if physical else 4), dtype=np.float32)
    mask = np.zeros_like(targets, dtype=bool)
    features[valid] = arrays["features"][indices]
    targets[valid] = arrays[prefix+"targets"][indices]
    eligible = arrays[prefix+"target_valid"][indices].copy()
    for key in ("label_valid", "identity_valid", "visibility_valid"):
        eligible &= arrays[prefix+key][indices]
    eligible &= arrays[prefix+"target_reasons"][indices] == "valid"
    eligible &= (arrays["observed_mask"][indices][:, [7,10]].all(axis=1, keepdims=True) if physical
                 else arrays["observed_mask"][indices][:, c.PAW_INDICES])
    eligible &= identities >= 0
    mask[valid] = eligible
    return features, targets, mask, ~valid


def load_prepared(folder, mode="strict", supervision="anatomical"):
    """Internal loader for fresh preparer output, not arbitrary label files."""
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    c.require(supervision in ("anatomical", "identity_neutral_front") and
              manifest.get("supervisionOutput", "anatomical") == supervision,
              "Prepared supervision output mismatch")
    physical = supervision == "identity_neutral_front"
    c.require(not physical or (mode == "exploratory_train_only" and len(manifest["sequences"]) == 1),
              "Physical output requires one exploratory source")
    c.require(mode in ("strict", "exploratory_train_only") and
              manifest.get("trainingMode", "strict") == mode, "Prepared training mode mismatch")
    c.require(manifest.get("trainingReady") is True, "Dataset is not training-ready")
    records, splits, provenance = [], {"train": [], "validation": []}, []
    for entry in manifest["sequences"]:
        path = prep.p.checked(folder, dict(path=entry["manifest"], sha256=entry["sha256"]))
        record = json.loads(path.read_text())
        c.require(record.get("supervisionOutput", "anatomical") == supervision, "Sequence output mismatch")
        c.require(record.get("trainingMode", "strict") == mode, "Sequence training mode mismatch")
        if mode == "exploratory_train_only":
            c.require(record["split"] == "train", "Exploratory source is not train-only")
        c.require(record.get("trainingReady") is True and record.get("trainingApproved") is True
                  and record.get("dogIdentityVerified") is True and c.canonical_dog_id(record.get("dogId"))
                  and record.get("provenanceGroup") and record.get("lineageHashes"),
                  "Unapproved or unidentified sequence")
        c.require(record.get("schemaVersion") == c.VERSION and record.get("channelOrder") == list(c.CHANNELS)
                  and record.get("pawOrder") == list(c.PAWS), "Feature/paw contract mismatch")
        # TEST-ONLY fixtures are never a real training source.
        c.require(record.get("dataPurpose", "real") == "real" and
                  not record.get("synthetic", False), "TEST-ONLY/synthetic data forbidden")
        records.append(record)
        provenance.append(dict(sequenceId=record["id"], dogId=record["dogId"], split=record["split"],
                               manifestSha256=entry["sha256"], outputs=record["outputs"],
                               lineageHashes=record["lineageHashes"], inputs=record["inputs"],
                               reviewEvidence=record["reviewEvidence"], timing=record["timing"],
                               rights=record["rights"], physicalOutput=record.get("physicalOutput")))
        npz_path = prep.p.checked(path.parent, dict(path="features.npz", sha256=record["outputs"]["features.npz"]))
        if record["split"] not in splits:
            continue
        with np.load(npz_path, allow_pickle=False) as arrays:
            for row in arrays["window_indices"]:
                window = gather_window(arrays, row, physical)
                if window[2].any():
                    splits[record["split"]].append(window)
    c.validate_partitions(records)
    if mode == "strict":
        c.require(all(splits.values()), "Need supervised train and validation dogs")
    else:
        c.require(len({c.canonical_dog_id(r["dogId"]) for r in records}) == 1 and
                  splits["train"] and not splits["validation"], "Need one supervised train-only dog")
    return splits, provenance


def run_epoch(model, windows, batch_size, *, optimizer=None, generator=None):
    import torch
    from petlens_gait.contact_model import masked_contact_loss
    model.train(optimizer is not None)
    order = torch.randperm(len(windows), generator=generator).tolist() if optimizer else range(len(windows))
    totals = dict(lossSum=0.0, correct=0, supervised=0, possible=0, tp=0, fp=0, fn=0)
    with torch.set_grad_enabled(optimizer is not None):
        for start in range(0, len(windows), batch_size):
            batch = [windows[i] for i in list(order)[start:start+batch_size]]
            x, y, mask, padding = [torch.from_numpy(np.stack(items)) for items in zip(*batch)]
            logits = model(x, padding)
            loss = masked_contact_loss(logits, y, mask, padding)
            if loss is None:
                continue
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            if optimizer:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            count = int(mask.sum())
            predicted, actual = logits.detach()[mask] >= 0, y[mask] == 1
            totals["lossSum"] += float(loss.detach()) * count
            totals["supervised"] += count
            totals["possible"] += int((~padding).sum()) * y.shape[-1]
            totals["correct"] += int((predicted == actual).sum())
            totals["tp"] += int((predicted & actual).sum())
            totals["fp"] += int((predicted & ~actual).sum())
            totals["fn"] += int((~predicted & actual).sum())
    n = totals["supervised"]
    c.require(n > 0, "No supervision in epoch")
    return dict(loss=totals["lossSum"]/n, accuracy=totals["correct"]/n,
                supervisedPawFrames=n, eligibleCoverage=n/totals["possible"],
                contactTP=totals["tp"], contactFP=totals["fp"], contactFN=totals["fn"],
                counting="Window-weighted; overlapping frames may repeat")


def fit(model, splits, config, output, metadata, mode, optimizer, generator):
    """Optimization stage; tests use only TEST-ONLY temporary fixture metadata."""
    from petlens_gait.contact_model import save_checkpoint
    if config.get("supervisionOutput", "anatomical") == "identity_neutral_front":
        from petlens_gait.contact_identity_neutral import IdentityNeutralContactModel, save_neutral_checkpoint
        c.require(mode == "exploratory_train_only" and isinstance(model, IdentityNeutralContactModel) and
                  metadata.get("physicalOutput") == model.binding,
                  "Identity-neutral model/metadata binding mismatch")
        save_checkpoint = save_neutral_checkpoint
    exploratory = mode == "exploratory_train_only"
    c.require(mode in ("strict", "exploratory_train_only"), "Unknown training mode")
    if exploratory:
        c.require(not splits["validation"] and 0 < len(splits["train"]) <= 32 and
                  config["epochs"] <= 100 and
                  config["epochs"] * ((len(splits["train"])+config["batch_size"]-1)//config["batch_size"]) <= 3200,
                  "Exploratory run exceeds bounds or contains validation data")
        c.require(model.config.max_frames == 128, "Exploratory windows must be at most 128 frames")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    best, history = float("inf"), []
    for epoch in range(config["epochs"]):
        training = run_epoch(model, splits["train"], config["batch_size"], optimizer=optimizer, generator=generator)
        result = dict(epoch=epoch+1, train=training)
        if not exploratory:
            validation = run_epoch(model, splits["validation"], config["batch_size"])
            result["validation"] = validation
            if validation["loss"] < best:
                best = validation["loss"]
                save_checkpoint(output / "best.pt", model, optimizer=optimizer, metadata={**metadata, **result})
        history.append(result)
        print(json.dumps(result), flush=True)
        save_checkpoint(output / "last.pt", model, optimizer=optimizer, metadata={**metadata, **result})
        (output / "metrics.json").write_text(json.dumps(history, indent=2) + "\n")
    return history


def train(job, root, config_path, output):
    import torch
    from petlens_gait.contact_model import CanineContactTransformer, ModelConfig
    config = json.loads(Path(config_path).read_text())
    mode = config.get("trainingMode", "strict")
    supervision = config.get("supervisionOutput", "anatomical")
    c.require(supervision in ("anatomical", "identity_neutral_front") and
              (supervision == "anatomical" or mode == "exploratory_train_only"), "Invalid output/mode")
    c.require(mode in ("strict", "exploratory_train_only"), "Unknown training mode")
    c.require(config["dataPurpose"] == "real-approved-canine", "Real approved data configuration required")
    for key in ("epochs", "batch_size", "threads"):
        c.require(type(config[key]) is int and config[key] > 0, f"Invalid {key}")
    c.require(type(config["seed"]) is int and 0 <= config["seed"] < 2**32, "Invalid seed")
    c.require(0 < config["learning_rate"] < 1 and config["weight_decay"] >= 0, "Invalid optimizer settings")
    c.require(not Path(output).exists(), "Output directory already exists")
    job_document = prep.p.load_json(Path(job))
    c.require(job_document.get("supervisionOutput", "anatomical") == supervision,
              "Job/config supervision output mismatch")
    for item in [job_document, *job_document.get("sequences", [])]:
        c.require(not item.get("synthetic", False) and item.get("dataPurpose", "real") == "real",
                  "TEST-ONLY/synthetic data forbidden")
    random.seed(config["seed"])
    np.random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    torch.set_num_threads(config["threads"])
    torch.use_deterministic_algorithms(True)
    generator = torch.Generator().manual_seed(config["seed"])
    with tempfile.TemporaryDirectory(prefix="petlens-real-contact-") as temporary:
        prepared = Path(temporary) / "prepared"
        readiness = prep.build(root, job, prepared, mode)
        c.require(readiness["trainingReady"], "Training blocked: " + "; ".join(readiness["blockers"]))
        splits, provenance = load_prepared(prepared, mode, supervision)
        if supervision == "identity_neutral_front":
            from petlens_gait.contact_identity_neutral import IdentityNeutralContactModel
            model = IdentityNeutralContactModel(ModelConfig(**config["model"]), provenance[0]["physicalOutput"])
        else:
            model = CanineContactTransformer(ModelConfig(**config["model"]))
        c.require(model.config.max_frames >= c.POLICY["windowLength"], "Model window is shorter than adapter window")
        optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
        output = Path(output)
        # Persist source-level provenance, including locked test assignments.
        metadata = dict(dataPurpose="real-approved-canine", config=config, provenance=provenance,
                        jobSha256=prep.p.digest(Path(job)), torchVersion=str(torch.__version__),
                        numpyVersion=np.__version__, pythonVersion=sys.version,
                        modelSourceSha256=prep.p.digest(ROOT / "src/petlens_gait/contact_model.py"),
                        trainerSourceSha256=prep.p.digest(Path(__file__)),
                        adapterSourceSha256=prep.p.digest(Path(c.__file__)),
                        preparerSourceSha256=prep.p.digest(Path(prep.__file__)),
                        trainingMode=mode, supervisionOutput=supervision)
        if mode == "exploratory_train_only":
            from training import contact_exploratory as exploratory
            metadata.update(independentValidation=False, generalizationValidated=False,
                            eventTimingValidated=False, trainOnly=True,
                            exploratorySourceSha256=prep.p.digest(Path(exploratory.__file__)),
                            policySha256=prep.p.digest(exploratory.POLICY))
            if supervision == exploratory.NEUTRAL:
                from petlens_gait import contact_identity_neutral
                metadata.update(physicalOutput=model.binding,
                                identityNeutralPolicySha256=prep.p.digest(exploratory.NEUTRAL_POLICY),
                                auxiliarySourceSha256=prep.p.digest(Path(contact_identity_neutral.__file__)))
        history = fit(model, splits, config, output, metadata, mode, optimizer, generator)
    return history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / "training/contact_model_config.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        train(args.job, args.root, args.config, args.output_dir)
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        print(f"Contact training blocked: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
