"""TEST-ONLY synthetic execution checks. No canine accuracy or training labels.

All tensors/checkpoints live in memory or pytest temporary directories. These
tests never export to a real dataset or call the real-training entry point with
synthetic supervision.
"""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
torch = pytest.importorskip("torch")
from petlens_gait import contact_features as c
from petlens_gait.contact_model import (CanineContactTransformer, ModelConfig,
                                       masked_contact_loss, save_checkpoint, load_checkpoint)
from training import train_contact as trainer
from tests.test_contact_features import sequence


@pytest.fixture(autouse=True)
def deterministic_test_only():
    torch.set_num_threads(1)
    torch.manual_seed(7)


def synthetic_arrays():
    predictions, source = sequence(count=6, fps=12)
    arrays = c.convert_sequence(predictions, source)
    arrays.update(targets=np.array([[0, 1, 0, 1], [1, 0, 1, 0]]*3, dtype=np.float32),
                  target_valid=np.ones((6, 4), bool), label_valid=np.ones((6, 4), bool),
                  identity_valid=np.ones((6, 4), bool), visibility_valid=np.ones((6, 4), bool),
                  target_reasons=np.full((6, 4), "valid", dtype="U48"),
                  identity_segments=np.zeros((6, 4), dtype=np.int64))
    return arrays


def test_adapter_forward_backward_checkpoint_test_only(tmp_path):
    arrays = synthetic_arrays()
    window = trainer.gather_window(arrays, np.array([0, 1, 2, 3, 4, 5, -1, -1]))
    x, y, valid, padding = [torch.from_numpy(a).unsqueeze(0) for a in window]
    assert torch.equal(x[0, :6], torch.from_numpy(arrays["features"]))
    model = CanineContactTransformer()
    logits = model(x, padding)
    assert logits.shape == (1, 8, 4)
    assert torch.isfinite(logits).all()
    assert ((logits.sigmoid() > 0) & (logits.sigmoid() < 1)).all()
    before = model.classifier.weight.detach().clone()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    loss = masked_contact_loss(logits, y, valid, padding)
    loss.backward()
    assert model.projection.weight.grad.abs().sum() > 0
    optimizer.step()
    assert not torch.equal(before, model.classifier.weight)
    model.eval()
    expected = model(x, padding)
    path = tmp_path / "TEST-ONLY.pt"
    save_checkpoint(path, model, optimizer=optimizer, metadata={"dataPurpose": "TEST-ONLY", "synthetic": True})
    restored, checkpoint = load_checkpoint(path)
    assert checkpoint["metadata"]["dataPurpose"] == "TEST-ONLY"
    restored.eval()
    torch.testing.assert_close(restored(x, padding), expected, rtol=0, atol=0)


def test_masked_unknown_unapproved_and_padding_have_zero_gradient():
    logits = torch.randn(1, 3, 4, requires_grad=True)
    targets = torch.zeros_like(logits)
    mask = torch.ones_like(logits, dtype=torch.bool)
    mask[0, 0, :2] = False
    targets[~mask] = float("nan")
    padding = torch.tensor([[False, False, True]])
    targets[0, 2] = float("nan")
    loss = masked_contact_loss(logits, targets, mask, padding)
    loss.backward()
    assert logits.grad[0, 0, :2].eq(0).all()
    assert logits.grad[0, 2].eq(0).all()
    assert masked_contact_loss(logits, targets, torch.zeros_like(mask)) is None
    with pytest.raises(ValueError, match="Supervised targets"):
        masked_contact_loss(logits, torch.full_like(targets, 2), mask)


@pytest.mark.parametrize("key", ["target_valid", "label_valid", "identity_valid", "visibility_valid", "observed_mask"])
def test_missing_or_unapproved_masks_never_supervise(key):
    arrays = synthetic_arrays()
    j = c.PAW_INDICES[0] if key == "observed_mask" else 0
    arrays[key][2, j] = False
    _, _, mask, _ = trainer.gather_window(arrays, np.arange(6))
    assert not mask[2, 0]
    assert mask[2, 1:].all()


@pytest.mark.parametrize("reason", ["unreviewed", "unknown", "provisional", "reviewer_disagreement", "not_adjudicated"])
def test_excluded_reasons_never_supervise(reason):
    arrays = synthetic_arrays()
    arrays["target_reasons"][1, 3] = reason
    assert not trainer.gather_window(arrays, np.arange(6))[2][1, 3]


def test_inference_mapping_abstention_and_missing_paws():
    model = CanineContactTransformer().eval()
    with torch.no_grad():
        model.classifier.weight.zero_()
        model.classifier.bias.copy_(torch.tensor([8., -8., 0., 8.]))
    x = torch.from_numpy(synthetic_arrays()["features"]).unsqueeze(0)
    identity = torch.ones((1, 6, 4), dtype=torch.bool)
    identity[..., 3] = False  # Unverified RH must never become a physical claim.
    reference = torch.ones((1, 6), dtype=torch.bool)
    result = model.predict(x, identity_valid=identity, reference_valid=reference)
    assert result["paw_order"] == ("LF", "RF", "LH", "RH")
    assert result["states"][0, 0].tolist() == [1, 0, -1, -1]
    x[0, 1, 4*c.PAW_INDICES[0]+3] = 0
    reference[0, 2] = False
    result = model.predict(x, identity_valid=identity, reference_valid=reference)
    assert result["states"][0, 1, 0] == -1
    assert result["states"][0, 2].eq(-1).all()
    with pytest.raises(ValueError):
        model.predict(x, identity_valid=identity[..., :2], reference_valid=reference)


def test_padding_cannot_change_real_outputs():
    model = CanineContactTransformer().eval()
    x = torch.randn(1, 8, 69)
    padding = torch.tensor([[False]*6 + [True]*2])
    expected = model(x[:, :6])
    x[:, 6:] = float("nan")
    torch.testing.assert_close(model(x, padding)[:, :6], expected)
    with pytest.raises(ValueError, match="All-padding"):
        model(x, torch.ones_like(padding))


def test_order_timing_identity_boundaries_and_shapes():
    arrays = synthetic_arrays()
    for row in (np.array([1, 0]), np.array([0, 2]), np.array([0, -1, 1])):
        with pytest.raises(ValueError):
            trainer.gather_window(arrays, row)
    arrays["identity_segments"][2:, 0] = 1
    with pytest.raises(ValueError, match="identity boundary"):
        trainer.gather_window(arrays, np.arange(6))
    model = CanineContactTransformer()
    with pytest.raises(ValueError):
        model(torch.zeros(1, 4, 68))
    with pytest.raises(ValueError):
        model(torch.zeros(1, 129, 69))
    arrays = synthetic_arrays()
    arrays["timestamps"][2:] += 1
    with pytest.raises(ValueError, match="timing"):
        trainer.gather_window(arrays, np.arange(6))


def test_test_only_epoch_metrics_and_reproducible_update():
    window = trainer.gather_window(synthetic_arrays(), np.arange(6))
    def run():
        torch.manual_seed(19)
        model = CanineContactTransformer(ModelConfig(dropout=0))
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
        metrics = trainer.run_epoch(model, [window], 1, optimizer=optimizer)
        validation = trainer.run_epoch(model, [window], 1)
        return metrics, validation, model.classifier.weight.detach()
    a, b = run(), run()
    assert a[:2] == b[:2]
    torch.testing.assert_close(a[2], b[2], rtol=0, atol=0)
    assert a[0]["supervisedPawFrames"] == 24
    assert a[1]["eligibleCoverage"] == 1


def test_real_cli_rejects_test_only_job_and_unready_export(tmp_path):
    job = tmp_path / "TEST-ONLY.json"
    job.write_text(json.dumps({"synthetic": True, "sequences": []}))
    with pytest.raises(ValueError, match="synthetic"):
        trainer.train(job, tmp_path, trainer.ROOT / "training/contact_model_config.json", tmp_path / "out")
    assert not (tmp_path / "out").exists()
    (tmp_path / "manifest.json").write_text(json.dumps({"trainingReady": False}))
    with pytest.raises(ValueError, match="not training-ready"):
        trainer.load_prepared(tmp_path)


@pytest.mark.parametrize("field", ["dogId", "provenanceGroup", "lineageHashes"])
def test_cross_split_leakage_fails(field):
    common = ["a"*64] if field == "lineageHashes" else "same"
    a = dict(dogId="dog-a", provenanceGroup="group-a", lineageHashes=["a"*64], split="train")
    b = dict(dogId="dog-b", provenanceGroup="group-b", lineageHashes=["b"*64], split="validation")
    a[field] = b[field] = common
    with pytest.raises(ValueError):
        c.validate_partitions([a, b])
