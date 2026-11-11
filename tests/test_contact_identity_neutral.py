"""TEST-ONLY auxiliary physical-paw fixtures; never real approval or training."""
import copy

import numpy as np
import pytest

from tests.test_contact_exploratory import fixture as base_fixture, signature, build
from training import contact_exploratory as ex
from training import prepare_contact_sequences as prep


def fixture(root):
    job, save, approval, doc = base_fixture(root)
    job["supervisionOutput"] = ex.NEUTRAL
    e = job["sequences"][0]
    spec = dict(kind="tracked_front", physicalPaw="C", anatomicalSide="unknown", firstFrame=0, lastFrame=3)
    e.update(supervisionOutput=ex.NEUTRAL, physicalOutput=spec)
    approval.update(physicalOutput=spec, identityNeutralPolicySha256=prep.p.digest(ex.NEUTRAL_POLICY))
    approval["scopes"]["identityNeutralOutput"] = True
    approval["identitySpans"][0]["physicalContinuous"] = True
    approval["mapping"] = {p:dict(approved=False, anatomicalPaw=None) for p in "ABCD"}
    continuity = dict(sourceVideo=doc["sourceVideo"], physicalOutput=spec,
                      continuityConfirmed=True, independenceDeclaration="prior_exposure",
                      evidence="TEST-ONLY explicit human physical continuity report, not anatomical side")
    e["physicalIdentityEvidence"] = save("TEST-ONLY-physical-continuity.json",continuity)
    approval["inputHashes"]["physicalIdentityEvidence"] = e["physicalIdentityEvidence"]["sha256"]
    # A different forepaw's definite state must not supervise the C readout.
    other = copy.deepcopy(doc["observations"][2])
    other.update(id="D2", physicalPaw="D", reportedSupportState="contacting")
    doc["observations"].append(other)
    approval["observations"]["D2"] = signature()
    e["exploratoryLabels"] = save("TEST-ONLY-labels.json", doc)
    approval["inputHashes"]["exploratoryLabels"] = e["exploratoryLabels"]["sha256"]
    e["exploratoryApproval"] = save("TEST-ONLY-approval.json", approval)
    return job, save, approval, doc


def test_neutral_mapping_masks_and_strict_separation(tmp_path):
    job,save,approval,doc = fixture(tmp_path)
    report = build(tmp_path,job,save)
    assert report["trainingReady"]
    assert set(report["sequences"]["example"]["approvedTargets"]) == {"physical:C"}
    with np.load(tmp_path/"prepared/sequences/example/features.npz",allow_pickle=False) as a:
        assert not a["target_valid"].any() and not a["identity_valid"].any()
        assert a["physical_target_valid"].shape == (4,1)
        assert a["physical_target_valid"][:,0].tolist() == [True,False,True,False]
        assert a["physical_targets"][[0,2],0].tolist() == [1,0]
        assert a["physical_identity_valid"].all()
    pytest.importorskip("torch")
    from training import train_contact as trainer
    splits, provenance = trainer.load_prepared(tmp_path/"prepared",ex.MODE,ex.NEUTRAL)
    assert splits["train"][0][1].shape == (128,1)
    binding = provenance[0]["physicalOutput"]
    assert binding["physicalPaw"] == "C" and binding["anatomicalSide"] == "unknown"
    assert binding["sourceVideoSha256"] == doc["sourceVideo"]["sha256"]
    with pytest.raises(ValueError, match="supervision output mismatch"):
        trainer.load_prepared(tmp_path/"prepared",ex.MODE)
    job["trainingMode"] = "strict";save("TEST-ONLY-job.json",job)
    with pytest.raises(ValueError, match="one exploratory source"):
        prep.build(tmp_path,tmp_path/"TEST-ONLY-job.json",tmp_path/"strict")


@pytest.mark.parametrize("failure",["owner","scope","policy","output","continuity","anatomical","span","rights","identity"])
def test_neutral_requires_explicit_approvals(tmp_path,failure):
    job,save,a,doc = fixture(tmp_path)
    if failure == "owner": a["approved"] = False
    if failure == "scope": a["scopes"]["identityNeutralOutput"] = False
    if failure == "policy": a["identityNeutralPolicySha256"] = "0"*64
    if failure == "output": a["physicalOutput"] = {**a["physicalOutput"],"physicalPaw":"D"}
    if failure == "continuity": a["inputHashes"]["physicalIdentityEvidence"] = "0"*64
    if failure == "anatomical": a["mapping"]["C"] = signature(anatomicalPaw="LF")
    if failure == "span": a["identitySpans"][0]["lastFrame"] = 2
    if failure == "rights": a["rights"]["approved"] = False
    if failure == "identity": a["dogIdentity"]["approved"] = False
    job["sequences"][0]["exploratoryApproval"] = save("TEST-ONLY-approval.json",a)
    with pytest.raises(ValueError): build(tmp_path,job,save)
    assert not (tmp_path/"prepared").exists()


@pytest.mark.parametrize("status,conflicts",[("provisional",[]),("unknown",[]),("unreviewed",[]),("definite",["disputed"])])
def test_neutral_excluded_labels_never_approved(tmp_path,status,conflicts):
    job,save,a,doc = fixture(tmp_path)
    for obs in doc["observations"]:
        obs.update(assessmentStatus=status, conflicts=conflicts)
    e=job["sequences"][0]
    e["exploratoryLabels"] = save("TEST-ONLY-labels.json",doc)
    a["inputHashes"]["exploratoryLabels"] = e["exploratoryLabels"]["sha256"]
    e["exploratoryApproval"] = save("TEST-ONLY-approval.json",a)
    assert not build(tmp_path,job,save)["trainingReady"]
    with np.load(tmp_path/"prepared/sequences/example/features.npz",allow_pickle=False) as arrays:
        assert not arrays["physical_target_valid"].any() and not arrays["target_valid"].any()


@pytest.mark.parametrize("joint",[7,10])
def test_missing_front_input_cannot_be_assigned_by_guess(tmp_path,joint):
    job,save,a,_ = fixture(tmp_path);e=job["sequences"][0]
    pred=prep.p.load_json(tmp_path/e["predictions"]["path"])
    for frame in pred["frames"]: frame["keypoints"][joint]["rawScore"]=0.1
    e["predictions"] = save("predictions.json",pred)
    meta=prep.p.load_json(tmp_path/e["metadata"]["path"])
    meta["predictionSha256"]=e["predictions"]["sha256"]
    e["metadata"]=save("metadata.json",meta)
    for k in ("metadata","predictions"): a["inputHashes"][k]=e[k]["sha256"]
    e["exploratoryApproval"]=save("TEST-ONLY-approval.json",a)
    assert not build(tmp_path,job,save)["trainingReady"]


def test_test_only_neutral_gradients_output_and_checkpoint(tmp_path):
    torch=pytest.importorskip("torch")
    from training import train_contact as trainer
    from petlens_gait.contact_model import ModelConfig, CanineContactTransformer, masked_contact_loss, load_checkpoint
    from petlens_gait.contact_identity_neutral import IdentityNeutralContactModel, load_neutral_checkpoint
    job,save,_,_=fixture(tmp_path); build(tmp_path,job,save)
    splits,provenance=trainer.load_prepared(tmp_path/"prepared",ex.MODE,ex.NEUTRAL)
    binding=provenance[0]["physicalOutput"]
    torch.set_num_threads(1);torch.manual_seed(19)
    model=IdentityNeutralContactModel(ModelConfig(dropout=0),binding)
    x,y,mask,pad=[torch.from_numpy(v).unsqueeze(0) for v in splits["train"][0]]
    assert model(x,pad).shape==(1,128,1)
    assert CanineContactTransformer()(x,pad).shape==(1,128,4)
    model.eval(); expected=model(x,pad).detach().clone()
    with torch.no_grad():
        model.backbone.classifier.weight.fill_(1000)
        model.backbone.classifier.bias.fill_(-1000)
    torch.testing.assert_close(model(x,pad),expected,rtol=0,atol=0)
    anatomical_before=model.backbone.classifier.weight.detach().clone()
    physical_before=model.physical_head.weight.detach().clone()
    encoder_before=model.backbone.projection.weight.detach().clone()
    logits=model(x,pad); logits.retain_grad()
    unknown=y.clone(); unknown[~mask]=float("nan")
    masked_contact_loss(logits,unknown,mask,pad).backward()
    assert logits.grad[~mask].eq(0).all()
    optimizer=torch.optim.AdamW(model.parameters(),lr=0.001)
    metadata=dict(synthetic=True,dataPurpose="TEST-ONLY",physicalOutput=binding,
                  supervisionOutput=ex.NEUTRAL,trainOnly=True,independentValidation=False)
    history=trainer.fit(model,splits,dict(epochs=5,batch_size=1,supervisionOutput=ex.NEUTRAL),
                        tmp_path/"TEST-ONLY-run",metadata,ex.MODE,optimizer,torch.Generator().manual_seed(19))
    assert history[-1]["train"]["loss"] < history[0]["train"]["loss"]
    assert not torch.equal(physical_before,model.physical_head.weight)
    assert not torch.equal(encoder_before,model.backbone.projection.weight)
    assert model.backbone.projection.weight.grad.abs().sum()>0
    assert model.backbone.classifier.weight.grad is None
    torch.testing.assert_close(anatomical_before,model.backbone.classifier.weight,rtol=0,atol=0)
    restored,record=load_neutral_checkpoint(tmp_path/"TEST-ONLY-run/last.pt")
    model.eval();restored.eval()
    torch.testing.assert_close(model(x,pad),restored(x,pad),rtol=0,atol=0)
    assert record["binding"]==binding and record["metadata"]["synthetic"]
    with pytest.raises(ValueError,match="Incompatible checkpoint"):
        load_checkpoint(tmp_path/"TEST-ONLY-run/last.pt")
    assert not (tmp_path/"TEST-ONLY-run/best.pt").exists()
    with pytest.raises(ValueError,match="exact checkpoint"):
        restored.predict(x,binding={**binding,"physicalPaw":"D"},physical_eligible=mask,padding_mask=pad)
    result=restored.predict(x,binding=binding,physical_eligible=mask,padding_mask=pad)
    assert result["contact_probability"].shape==(1,128,1)
    assert result["states"][~mask].eq(-1).all()
