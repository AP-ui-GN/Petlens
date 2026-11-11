"""TEST-ONLY fixtures; no real canine training, approval or evaluation results."""
import copy
import json

import numpy as np
import pytest

from tests.test_contact_features import job_fixture
from training import prepare_contact_sequences as prep
from training import contact_exploratory as ex


def signature(**extra):
    return dict(approved=True, reviewer="TEST-ONLY fictional signer", date="2026-11-11",
                evidence="TEST-ONLY synthetic fixture attestation", **extra)


def fixture(root):
    job, save = job_fixture(root)
    job.update(trainingMode=ex.MODE, synthetic=True)
    entry = job["sequences"][0]
    source = prep.p.load_json(root / entry["sourceFrames"]["path"])
    source.update(physicalPaws=list("ABCD"), pawRoles={"A":"Hind A", "B":"Hind B", "C":"Front C", "D":"Front D"})
    entry["sourceFrames"] = save("native.json", source)
    entry["timing"] = dict(sourceType="source_movie", nativeVerified=False, sourcePtsVerified=True, evidence="TEST-ONLY movie PTS")
    observations = []
    for i, (state, status) in enumerate([("contacting", "definite"), ("unknown", "unknown"),
                                        ("airborne", "definite"), ("airborne", "provisional")]):
        observations.append(dict(id=f"C{i}",physicalPaw="C", frame=source["frames"][i],
                                 assessmentStatus=status, reportedSupportState=state,
                                 conflicts=[], coreEncoding=dict(visibility="visible")))
    doc = dict(sourceVideo=source["sourceVideo"], manifestSha256=entry["sourceFrames"]["sha256"],
               reviewer="TEST-ONLY previously exposed human", independenceDeclaration="prior_exposure",
               observations=observations)
    entry["exploratoryLabels"] = save("TEST-ONLY-labels.json", doc)
    entry["rightsEvidence"] = save("TEST-ONLY-rights.json", {"evidence":"TEST-ONLY rights fixture"})
    hashes = {k:entry[k]["sha256"] for k in ("predictions","video","metadata","sourceFrames","exploratoryLabels","rightsEvidence")}
    hashes["sourceVideo"] = source["sourceVideo"]["sha256"]
    approval = signature(role="project_owner", mode=ex.MODE, trainingApproved=True,
                         policySha256=prep.p.digest(ex.POLICY), scopes=dict.fromkeys(ex.SCOPES, True),
                         inputHashes=hashes, dogId=entry["dogId"], provenanceGroup=entry["provenanceGroup"],
                         dogIdentity=signature(),
                         rights=signature(attribution="TEST-ONLY fixture"),
                         mapping={"C":signature(anatomicalPaw="RF")},
                         identitySpans=[signature(physicalPaw="C", firstFrame=0, lastFrame=3, visibleContinuous=True)],
                         observations={f"C{i}":signature() for i in range(4)})
    entry["exploratoryApproval"] = save("TEST-ONLY-approval.json", approval)
    return job, save, approval, doc


def build(root, job, save, name="prepared"):
    save("TEST-ONLY-job.json", job)
    return prep.build(root, root/"TEST-ONLY-job.json", root/name, ex.MODE)


def test_sparse_exposed_single_dog_movie_timing(tmp_path):
    job, save, approval, doc = fixture(tmp_path)
    result = build(tmp_path, job, save)
    assert result["trainingReady"]
    assert not result["sequences"]["example"]["nativeTimingEvaluationEligible"]
    with np.load(tmp_path/"prepared/sequences/example/features.npz", allow_pickle=False) as a:
        assert a["target_valid"].sum() == 2
        assert a["target_valid"][:, 1].tolist() == [True,False,True,False]
        assert not a["target_valid"][:, [0,2,3]].any()
        assert a["targets"][0,1] == 1 and a["targets"][2,1] == 0
        assert len(a["window_indices"]) == 1
        assert a["window_indices"][0,:4].tolist() == [0,1,2,3]
    torch = pytest.importorskip("torch")
    from training import train_contact as trainer
    splits, provenance = trainer.load_prepared(tmp_path/"prepared", ex.MODE)
    assert len(splits["train"]) == 1 and not splits["validation"]
    assert provenance[0]["reviewEvidence"][0]["exposure"] == "prior_exposure"
    with pytest.raises(ValueError, match="mode mismatch"):
        trainer.load_prepared(tmp_path/"prepared")


@pytest.mark.parametrize("failure", ["owner", "role", "policy", "scope", "hash", "rights", "dog", "mapping", "identity"])
def test_unsigned_or_incompatible_approvals_fail_closed(tmp_path, failure):
    job, save, a, doc = fixture(tmp_path)
    if failure == "owner": a["approved"] = False
    if failure == "role": a["role"] = "reviewer"
    if failure == "policy": a["policySha256"] = "0"*64
    if failure == "scope": a["scopes"]["singleExposedReviewer"] = False
    if failure == "hash": a["inputHashes"]["predictions"] = "0"*64
    if failure == "rights": a["rights"]["approved"] = False
    if failure == "dog": a["dogId"] = "other-dog"
    if failure == "mapping": a["mapping"]["C"]["anatomicalPaw"] = "LH"
    if failure == "identity": a["identitySpans"][0]["visibleContinuous"] = False
    job["sequences"][0]["exploratoryApproval"] = save("TEST-ONLY-approval.json", a)
    with pytest.raises(ValueError): build(tmp_path, job, save)
    assert not (tmp_path/"prepared").exists()


@pytest.mark.parametrize("failure", ["label_approval", "conflict", "provisional", "unknown", "unreviewed", "visibility", "pose", "mapping", "identity", "rights", "entry_approval", "dog_verification", "timing"])
def test_ineligible_examples_never_train(tmp_path, failure):
    job, save, a, doc = fixture(tmp_path)
    e = job["sequences"][0]
    if failure == "label_approval":
        for item in a["observations"].values(): item["approved"] = False
    if failure in ("conflict", "provisional", "unknown", "unreviewed", "visibility"):
        for obs in doc["observations"]:
            if failure == "conflict": obs["conflicts"] = ["TEST-ONLY dispute"]
            elif failure == "visibility": obs["coreEncoding"]["visibility"] = "uncertain"
            else: obs["assessmentStatus"] = failure
        e["exploratoryLabels"] = save("TEST-ONLY-labels.json", doc)
        a["inputHashes"]["exploratoryLabels"] = e["exploratoryLabels"]["sha256"]
    if failure == "mapping": a["mapping"] = {}; a["identitySpans"] = []
    if failure == "identity": a["identitySpans"] = []
    if failure == "rights": e["rights"]["status"] = "unknown"
    if failure == "entry_approval": e["trainingApproved"] = False
    if failure == "dog_verification": e["dogIdentityVerified"] = False
    if failure == "timing": e["timing"]["sourcePtsVerified"] = False
    if failure == "pose":
        pred = prep.p.load_json(tmp_path/e["predictions"]["path"])
        for frame in pred["frames"]: frame["keypoints"][10]["rawScore"] = 0.1
        e["predictions"] = save("predictions.json", pred)
        a["inputHashes"]["predictions"] = e["predictions"]["sha256"]
        meta = prep.p.load_json(tmp_path/e["metadata"]["path"])
        meta["predictionSha256"] = e["predictions"]["sha256"]
        e["metadata"] = save("metadata.json", meta)
        a["inputHashes"]["metadata"] = e["metadata"]["sha256"]
    e["exploratoryApproval"] = save("TEST-ONLY-approval.json", a)
    report = build(tmp_path, job, save)
    assert not report["trainingReady"]
    if failure not in ("rights", "entry_approval", "dog_verification", "timing"):
        with np.load(tmp_path/"prepared/sequences/example/features.npz", allow_pickle=False) as arrays:
            assert not arrays["target_valid"].any()


def test_mode_split_and_dog_restrictions(tmp_path):
    job, save, a, doc = fixture(tmp_path)
    save("TEST-ONLY-job.json", job)
    with pytest.raises(ValueError, match="mode mismatch"):
        prep.build(tmp_path, tmp_path/"TEST-ONLY-job.json", tmp_path/"strict")
    job["sequences"][0]["split"] = "validation"
    with pytest.raises(ValueError, match="train-only"): build(tmp_path, job, save)
    job["sequences"][0]["split"] = "train"
    other = copy.deepcopy(job["sequences"][0]); other["dogId"] = "other-dog"; other["id"] = "other"
    job["sequences"].append(other)
    with pytest.raises(ValueError, match="one verified dog"): build(tmp_path, job, save)


def test_test_only_optimization_and_checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    from training import train_contact as trainer
    from petlens_gait.contact_model import CanineContactTransformer, ModelConfig, load_checkpoint
    job, save, _, _ = fixture(tmp_path)
    build(tmp_path, job, save)
    splits, _ = trainer.load_prepared(tmp_path/"prepared", ex.MODE)
    torch.set_num_threads(1); torch.manual_seed(19)
    model = CanineContactTransformer(ModelConfig(dropout=0))
    before = model.classifier.weight.detach().clone()
    config = dict(epochs=5, batch_size=1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    history = trainer.fit(model, splits, config, tmp_path/"TEST-ONLY-run",
                          dict(dataPurpose="TEST-ONLY", synthetic=True, trainingMode=ex.MODE,
                               trainOnly=True, independentValidation=False), ex.MODE, optimizer,
                          torch.Generator().manual_seed(19))
    assert all("validation" not in row for row in history)
    assert history[-1]["train"]["loss"] < history[0]["train"]["loss"]
    assert model.projection.weight.grad.abs().sum() > 0
    assert not torch.equal(before, model.classifier.weight)
    assert not (tmp_path/"TEST-ONLY-run/best.pt").exists()
    restored, checkpoint = load_checkpoint(tmp_path/"TEST-ONLY-run/last.pt")
    assert checkpoint["metadata"]["synthetic"] is True
    model.eval(); restored.eval()
    x,y,m,padding = [torch.from_numpy(t).unsqueeze(0) for t in splits["train"][0]]
    torch.testing.assert_close(model(x,padding),restored(x,padding),rtol=0,atol=0)
    with pytest.raises(ValueError, match="bounds"):
        trainer.fit(model, splits, {**config,"epochs":101}, tmp_path/"too-long", {},ex.MODE,optimizer,None)
    with pytest.raises(ValueError, match="synthetic"):
        trainer.train(tmp_path/"TEST-ONLY-job.json", tmp_path,
                      trainer.ROOT/"training/contact_model_config.json", tmp_path/"not-real")
