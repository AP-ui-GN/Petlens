"""Contract, provenance and leakage tests; no networks or neural inference."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petlens_gait import contact_features as c
from training import prepare_contact_sequences as prep
from training import prepare_paw_annotations as p
from training import gait_event_review as review

ROOT = Path(__file__).resolve().parents[1]


def sequence(count=4, fps=60):
    source = dict(frameCount=count, frameWidth=1000, frameHeight=800,
                  sourceVideo=dict(path="video.mp4", sha256="a" * 64),
                  frames=[dict(frameIndex=i, originalPts=i, originalTimeBase=f"1/{fps}",
                               timestampSeconds=i/fps) for i in range(count)])
    frames = []
    for i in range(count):
        points = [dict(name=n, x=250+j*10, y=350+j*3, rawScore=1.46) for j, n in enumerate(c.NAMES)]
        points[3].update(x=200, y=300)
        points[4].update(x=400, y=300)
        frames.append(dict(frameIndex=i, timestampSeconds=i/fps, detectionSuccess=True, keypoints=points))
    pred = dict(frameCount=count, frames=frames, fps=fps,
                detectorModel="PekingU/rtdetr_r50vd_coco_o365", poseModel="OpenMMLab RTMPose-m AP-10K",
                keypointSchema="AP-10K, 17 keypoints", rawPredictionsWereSmoothedOrCorrected=False,
                videoSha256="a"*64)
    return pred, source


def test_body_normalization_precision_and_raw_scores():
    pred, source = sequence()
    before = copy.deepcopy(pred)
    data = c.convert_sequence(pred, source)
    assert data["features"].shape == (4, 69)
    assert data["features"].dtype == np.float32
    np.testing.assert_array_equal(data["features"][:, 2:68:4], np.float32(1.46))
    assert data["features"][0, 3*4] == -.5  # neck relative to midpoint
    assert data["features"][0, 4*4] == .5   # tail-root
    assert data["features"][0, -1] == 0
    assert data["delta_seconds"].dtype == np.float64
    np.testing.assert_array_equal(data["original_pts"], np.arange(4))
    assert np.all(data["original_time_bases"] == "1/60")
    assert pred == before


@pytest.mark.parametrize("scale,dx,dy", [(1, 70, 10), (1.5, 20, 15), (.5, 10, 10)])
def test_translation_and_scale_invariance(scale, dx, dy):
    pred, source = sequence()
    transformed = copy.deepcopy(pred)
    for frame in transformed["frames"]:
        for point in frame["keypoints"]:
            point["x"] = point["x"] * scale + dx
            point["y"] = point["y"] * scale + dy
    np.testing.assert_allclose(c.convert_sequence(pred, source)["features"],
                               c.convert_sequence(transformed, source)["features"], atol=1e-6)


@pytest.mark.parametrize("fps", [12, 30, 60])
def test_native_elapsed_times(fps):
    pred, source = sequence(fps=fps)
    arrays = c.convert_sequence(pred, source)
    np.testing.assert_allclose(arrays["delta_seconds"], [0, 1/fps, 1/fps, 1/fps], atol=1e-15)
    np.testing.assert_allclose(arrays["features"][1:, -1], 1/fps)


@pytest.mark.parametrize("failure", ["absent", "nan", "inf", "low", "outside", "detector", "huge_score"])
def test_unreliable_points_are_masked_without_clipping_or_interpolation(failure):
    pred, source = sequence()
    point = pred["frames"][1]["keypoints"][13]
    if failure == "absent":
        pred["frames"][1]["keypoints"].pop(13)
    elif failure == "nan":
        point["x"] = float("nan")
    elif failure == "inf":
        point["rawScore"] = float("inf")
    elif failure == "low":
        point["rawScore"] = .1
    elif failure == "outside":
        point["x"] = -1
    elif failure == "huge_score":
        point["rawScore"] = 1e100
    else:
        pred["frames"][1]["detectionSuccess"] = False
    data = c.convert_sequence(pred, source)
    assert not data["observed_mask"][1, 13]
    assert np.all(data["features"][1, 13*4:13*4+2] == 0)
    assert np.isfinite(data["features"]).all()
    assert data["observation_reasons"][1, 13] != "observed"
    assert data["observed_mask"][0, 13] and data["observed_mask"][2, 13]
    if failure == "low":
        assert data["features"][1, 13*4+2] == np.float32(.1)


@pytest.mark.parametrize("failure", ["missing_neck", "low_neck", "low_tail", "zero_scale"])
def test_missing_body_reference_never_uses_anatomical_fallback(failure):
    pred, source = sequence()
    points = pred["frames"][1]["keypoints"]
    if failure == "missing_neck":
        points.pop(3)
    elif failure == "low_neck":
        points[3]["rawScore"] = .6
    elif failure == "low_tail":
        points[4]["rawScore"] = .7
    else:
        points[4].update(x=points[3]["x"], y=points[3]["y"])
    data = c.convert_sequence(pred, source)
    assert not data["reference_valid"][1]
    assert np.all(data["features"][1, :68].reshape(17, 4)[:, :2] == 0)
    windows = c.make_windows(data["reference_valid"], data["timestamps"])
    assert windows["segment_ids"].tolist() == [0, -1, 1, 1]
    assert not np.any(windows["window_indices"] == 1)


@pytest.mark.parametrize("failure", ["count", "timestamp", "pts", "timebase", "duplicate_frame", "duplicate_joint", "unknown_joint", "nan_time"])
def test_invalid_structure_and_source_timing_fail(failure):
    pred, source = sequence()
    if failure == "count":
        pred["frameCount"] += 1
    elif failure == "timestamp":
        pred["frames"][1]["timestampSeconds"] = 0
    elif failure == "pts":
        source["frames"][1].pop("originalPts")
    elif failure == "timebase":
        source["frames"][1]["originalTimeBase"] = "1/0"
    elif failure == "duplicate_frame":
        source["frames"][1]["frameIndex"] = 0
    elif failure == "duplicate_joint":
        pred["frames"][0]["keypoints"].append(pred["frames"][0]["keypoints"][0].copy())
    elif failure == "unknown_joint":
        pred["frames"][0]["keypoints"][0]["name"] = "invented_heel"
    else:
        source["frames"][1]["timestampSeconds"] = float("nan")
    with pytest.raises(ValueError):
        c.convert_sequence(pred, source)


def test_windows_padding_overlap_gaps_and_identity_breaks():
    result = c.make_windows(np.ones(190, dtype=bool), np.arange(190)/60)
    assert result["window_indices"].shape == (2, 128)
    assert result["window_indices"][1, 0] == 64
    assert result["padding_mask"][1].sum() == 2
    assert np.all(result["window_indices"][1, -2:] == -1)
    none = c.make_windows(np.zeros(3, dtype=bool), np.arange(3)/60)
    assert none["window_indices"].shape == (0, 128)
    identity = np.zeros((4, 4), dtype=np.int64)
    identity[2:, 0] = -1
    result = c.make_windows(np.ones(4, dtype=bool), np.arange(4)/60, identity)
    assert result["segment_ids"].tolist() == [0, 0, 1, 1]
    result = c.make_windows(np.ones(4, dtype=bool), np.array([0, .01, .5, .51]))
    assert result["segment_ids"].tolist() == [0, 0, 1, 1]


@pytest.mark.parametrize("key,a,b", [("dogId", " Dog:ABC ", "dog:abc"),
                                   ("provenanceGroup", "Publication:X", "publication:x"),
                                   ("lineageHashes", ["same-video"], ["same-video"])])
def test_cross_split_dog_publication_and_derivative_leakage(key, a, b):
    rows = [{"dogId": "one", "split": "train", key: a},
            {"dogId": "two", "split": "test", key: b}]
    with pytest.raises(ValueError, match="Split leakage|Conflicting dog"):
        c.validate_partitions(rows)


def test_same_source_cannot_become_two_dogs_in_one_split():
    with pytest.raises(ValueError, match="Conflicting dog identities"):
        c.validate_partitions([dict(dogId="one", split="train", lineageHashes=["source"]),
                               dict(dogId="two", split="train", lineageHashes=["source"])])


def job_fixture(root, labeled=False):
    def save(name, value):
        path = root / name
        path.write_text(json.dumps(value, allow_nan=False))
        return dict(path=name, sha256=p.digest(path))
    video = root / "video.mp4"
    video.write_bytes(b"synthetic source bytes; never decoded")
    video_ref = dict(path=video.name, sha256=p.digest(video))
    pred, source = sequence()
    source.update(sourceVideo=video_ref, datasetId="synthetic-contact-fixture", selectedFrames=list(range(4)))
    pred["videoSha256"] = video_ref["sha256"]
    source_ref = save("native.json", source)
    pred_ref = save("predictions.json", pred)
    metadata = dict(schemaVersion=1, datasetId=source["datasetId"], videoSha256=video_ref["sha256"],
                    predictionSha256=pred_ref["sha256"], sourceFrameCount=4, fps=60,
                    frameWidth=1000, frameHeight=800, frames=source["frames"])
    schema = dict(schema_version="petlens.ap10k-17.v1", keypoints=[dict(id=n) for n in c.NAMES])
    entry = dict(id="example", predictions=pred_ref, metadata=save("metadata.json", metadata),
                 sourceFrames=source_ref, video=video_ref, dogId="Dog:ONE", dogIdentityVerified=True,
                 provenanceGroup="owned:one", split="train", trainingApproved=True,
                 rights=dict(status="cleared", evidence="Synthetic fixture"),
                 timing=dict(sourceType="native", nativeVerified=True, evidence="Synthetic integer clock"))
    if labeled:
        entry["reviews"] = []
        for pair, mapping in [("fore", dict(A="LF", B="RF")), ("hind", dict(A="LH", B="RH"))]:
            drafts = []
            for reviewer in ("r1", "r2", "adjudicator"):
                draft = review.initial_draft(source, source_ref["sha256"])
                draft.update(reviewer=reviewer, independenceDeclaration="no_prior_exposure",
                             pawDescriptions={paw: f"Verified physical {name}" for paw, name in mapping.items()})
                for i, paws in draft["observations"].items():
                    for obs in paws.values():
                        obs.update(visibility="visible", continuity="start" if i == "0" else "continuous",
                                   supportState="contacting" if int(i) % 2 == 0 else "airborne")
                drafts.append(save(f"{pair}-{reviewer}.json", draft))
            drafts[2].update(reviewers=["r1", "r2"], evidence="Explicit synthetic adjudication")
            entry["reviews"].append(dict(pair=pair, mapping=mapping,
                 mappingEvidence=dict(verified=True, reviewer="adjudicator", evidence="Synthetic mapping"),
                 reviews=drafts[:2], adjudication=drafts[2]))
    return dict(schemaVersion=1, keypointSchema=save("schema.json", schema), sequences=[entry]), save


def build_job(root, job, save, name="output"):
    ref = save("job.json", job)
    return prep.build(root, root / ref["path"], root / name)


def test_unlabeled_export_is_inspectable_and_preserves_source_numbers(tmp_path):
    job, save = job_fixture(tmp_path)
    job["sequences"][0].update(dogId=None, dogIdentityVerified=False)
    original = (tmp_path / "predictions.json").read_bytes()
    report = build_job(tmp_path, job, save)
    assert not report["trainingReady"]
    assert report["sequences"]["example"]["converted"]
    folder = tmp_path / "output/sequences/example"
    with np.load(folder / "features.npz", allow_pickle=False) as data:
        assert not data["target_valid"].any()
        assert not data["identity_valid"].any()
        assert np.isfinite(data["features"]).all()
        assert data["features"][0, 2] == np.float32(1.46)
        assert data["targets"].sum() == 0  # placeholders; all loss weights zero
    assert (tmp_path / "predictions.json").read_bytes() == original
    assert json.loads((folder / "raw-observations.json").read_text())["frames"][0]["keypoints"][0]["rawScore"] == 1.46
    with pytest.raises(ValueError, match="Output already exists"):
        build_job(tmp_path, job, save)


def test_two_independent_pairs_and_explicit_adjudication_supply_targets(tmp_path):
    job, save = job_fixture(tmp_path, labeled=True)
    report = build_job(tmp_path, job, save)
    assert report["trainingReady"], report["blockers"]
    with np.load(tmp_path / "output/sequences/example/features.npz", allow_pickle=False) as data:
        assert data["target_valid"].all()
        np.testing.assert_array_equal(data["targets"][:, 0], [1, 0, 1, 0])
        assert data["identity_valid"].all()
        assert data["padding_mask"].sum() == 124


@pytest.mark.parametrize("failure", ["no_adjudication", "one_reviewer", "same_reviewer", "unmapped", "exposed", "disagreement", "uncertain", "occluded", "broken"])
def test_unsafe_contact_supervision_remains_masked(tmp_path, failure):
    job, save = job_fixture(tmp_path, labeled=True)
    pair = job["sequences"][0]["reviews"][0]
    if failure == "no_adjudication":
        pair.pop("adjudication")
    elif failure == "one_reviewer":
        pair["reviews"].pop()
    elif failure == "same_reviewer":
        pair["reviews"][1] = pair["reviews"][0]
    elif failure == "unmapped":
        pair["mapping"] = {}
    elif failure == "exposed":
        pair["exposureRecords"] = [save("exposure.json", dict(sourceVideo=job["sequences"][0]["video"],
                    reviewer="r1", independence=dict(proposedDeclaration="prior_exposure")))]
    else:
        refs = [pair["reviews"][1]] if failure == "disagreement" else pair["reviews"] + [pair["adjudication"]]
        for ref in refs:
            draft = json.loads((tmp_path / ref["path"]).read_text())
            obs = draft["observations"]["1"]["A"]
            if failure == "disagreement":
                obs["supportState"] = "contacting"
            elif failure == "uncertain":
                obs["supportState"] = "uncertain"
            elif failure == "occluded":
                obs.update(supportState="occluded", visibility="occluded")
            else:
                obs["continuity"] = "broken"
            updated = save(ref["path"], draft)
            ref["sha256"] = updated["sha256"]
    report = build_job(tmp_path, job, save)
    with np.load(tmp_path / "output/sequences/example/features.npz", allow_pickle=False) as data:
        assert not data["target_valid"][1, 0]
        assert data["target_valid"][:, 2:].all()  # unaffected hind pair remains valid
    if failure in ("no_adjudication", "one_reviewer", "same_reviewer", "unmapped", "exposed"):
        assert not report["trainingReady"]


@pytest.mark.parametrize("failure", ["hash", "schema", "video", "duplicate_json", "fit_test_dogs", "leakage"])
def test_unsafe_jobs_fail_before_creating_output(tmp_path, failure):
    job, save = job_fixture(tmp_path)
    entry = job["sequences"][0]
    if failure == "hash":
        entry["predictions"]["sha256"] = "0"*64
    elif failure == "schema":
        job["keypointSchema"] = save("bad-schema.json", dict(schema_version="invented", keypoints=[]))
    elif failure == "video":
        entry["video"]["sha256"] = "0"*64
    elif failure == "duplicate_json":
        (tmp_path / "predictions.json").write_text('{"frames": [], "frames": []}')
        entry["predictions"]["sha256"] = p.digest(tmp_path / "predictions.json")
    elif failure == "fit_test_dogs":
        job["normalizationFitDogIds"] = ["test-dog"]
    else:
        other = copy.deepcopy(entry)
        other.update(id="other", split="test")
        job["sequences"].append(other)
    with pytest.raises(ValueError):
        build_job(tmp_path, job, save)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("source_type", ["unknown", "screen_recording", "resampled"])
def test_monotonic_pts_does_not_establish_native_capture(tmp_path, source_type):
    job, save = job_fixture(tmp_path, labeled=True)
    job["sequences"][0]["timing"]["sourceType"] = source_type
    report = build_job(tmp_path, job, save)
    assert not report["trainingReady"]
    assert not report["sequences"]["example"]["nativeTimingEvaluationEligible"]


def test_legacy_list_predictions_require_explicit_provenance(tmp_path):
    job, save = job_fixture(tmp_path)
    pred = json.loads((tmp_path / "predictions.json").read_text())
    entry = job["sequences"][0]
    entry["predictions"] = save("legacy.json", pred["frames"])
    meta = json.loads((tmp_path / "metadata.json").read_text())
    meta["predictionSha256"] = entry["predictions"]["sha256"]
    entry["metadata"] = save("metadata.json", meta)
    with pytest.raises((ValueError, KeyError)):
        build_job(tmp_path, job, save)
    entry["predictionEnvelope"] = {k: v for k, v in pred.items() if k != "frames"}
    assert build_job(tmp_path, job, save)["converted"]


def test_explicit_saved_prefix_keeps_original_indices_and_timebase(tmp_path):
    job, save = job_fixture(tmp_path)
    entry = job["sequences"][0]
    pred = json.loads((tmp_path / "predictions.json").read_text())
    pred["frames"] = pred["frames"][:2]
    pred["frameCount"] = 2
    entry["predictions"] = save("predictions.json", pred)
    meta = json.loads((tmp_path / "metadata.json").read_text())
    meta["predictionSha256"] = entry["predictions"]["sha256"]
    entry["metadata"] = save("metadata.json", meta)
    with pytest.raises(ValueError, match="count mismatch"):
        build_job(tmp_path, job, save)
    entry["sourceFrameRange"] = [0, 1]
    report = build_job(tmp_path, job, save)
    assert report["sequences"]["example"]["frameCount"] == 2
    with np.load(tmp_path / "output/sequences/example/features.npz", allow_pickle=False) as data:
        assert data["frame_indices"].tolist() == [0, 1]
        assert data["original_time_bases"].tolist() == ["1/60", "1/60"]


def test_source_frame_map_list_uses_explicit_original_file_reference(tmp_path):
    job, save = job_fixture(tmp_path)
    entry = job["sequences"][0]
    source = json.loads((tmp_path / "native.json").read_text())
    entry["sourceFrames"] = save("frame-map.json", source["frames"])
    entry["sourceVideo"] = source["sourceVideo"]
    assert build_job(tmp_path, job, save)["converted"]


def test_cli_require_training_ready_reports_missing_evidence(tmp_path):
    job, save = job_fixture(tmp_path)
    save("job.json", job)
    assert prep.main(["--root", str(tmp_path), "--job", str(tmp_path / "job.json"),
                      "--output-dir", str(tmp_path / "output"), "--require-training-ready"]) == 3
    assert (tmp_path / "output/validation.json").is_file()


def test_saved_dogreid_rejection_cannot_be_overridden_by_job_approval(tmp_path):
    job, save = job_fixture(tmp_path, labeled=True)
    folder = tmp_path / "reports/dogreid-1553"
    folder.mkdir(parents=True)
    save("reports/dogreid-1553/screened-videos.json", [dict(sha256=job["sequences"][0]["video"]["sha256"],
                                                       training_approved=False)])
    report = build_job(tmp_path, job, save)
    assert "dogreid_training_not_approved" in report["sequences"]["example"]["blockers"]


def test_known_husky_cannot_be_claimed_native_even_with_valid_clock(tmp_path):
    job, save = job_fixture(tmp_path, labeled=True)
    (tmp_path / "reports/husky-evaluation").mkdir(parents=True)
    save("reports/husky-evaluation/annotation-manifest-v1.json",
         dict(video=job["sequences"][0]["video"], originalSource=dict(sha256="c"*64)))
    report = build_job(tmp_path, job, save)
    assert not report["sequences"]["example"]["nativeTimingEvaluationEligible"]


def test_known_dog02_exclusion_is_preserved_even_if_job_claims_training(tmp_path):
    job, save = job_fixture(tmp_path, labeled=True)
    (tmp_path / "training").mkdir()
    save("training/paw_annotation_sources.json", dict(sequences=[
        dict(group="dog02", predictions=job["sequences"][0]["predictions"], video=job["sequences"][0]["video"]) ]))
    report = build_job(tmp_path, job, save)
    assert "existing_exploratory_only_policy" in report["sequences"]["example"]["blockers"]


def test_nonfinite_file_observations_have_explicit_finite_audit_tags(tmp_path):
    job, save = job_fixture(tmp_path)
    pred_path = tmp_path / "predictions.json"
    # Valid JSON exponent overflow is handled as missing; JSON NaN literals fail.
    pred_path.write_text(pred_path.read_text().replace('"rawScore": 1.46', '"rawScore": 1e999', 1))
    entry = job["sequences"][0]
    entry["predictions"]["sha256"] = p.digest(pred_path)
    meta = json.loads((tmp_path / "metadata.json").read_text())
    meta["predictionSha256"] = entry["predictions"]["sha256"]
    entry["metadata"] = save("metadata.json", meta)
    build_job(tmp_path, job, save)
    with np.load(tmp_path / "output/sequences/example/features.npz", allow_pickle=False) as arrays:
        assert np.isfinite(arrays["features"]).all()
        assert not arrays["observed_mask"][0, 0]
    raw = json.loads((tmp_path / "output/sequences/example/raw-observations.json").read_text())
    assert raw["frames"][0]["keypoints"][0]["rawScore"] == {"invalidNumeric": "inf"}


def real_job():
    config = p.load_json(ROOT / "training/paw_annotation_sources.json")
    manifest_path = ROOT / "reports/gait-event-review-v1/frame-manifest.json"
    manifest_ref = dict(path=str(manifest_path.relative_to(ROOT)), sha256=p.digest(manifest_path))
    entries = []
    for original in config["sequences"]:
        entry = {k: copy.deepcopy(original[k]) for k in ("group", "predictions", "metadata", "video", "split")}
        entry.update(id=original["group"], sourceFrames=dict(manifest_ref, group="gait-"+original["group"]))
        if entry["group"] == "dog02":
            path = ROOT / "tmp/rtmpose-test/multi-video-evaluation/inputs/dog02-conversion.json"
            entry["conversion"] = dict(path=str(path.relative_to(ROOT)), sha256=p.digest(path))
            zip_path = ROOT / "reports/gait-event-review-v1/reviews/review-d684d28c840a475ba7833f1c045d2504.zip"
            entry["reviews"] = [dict(pair="hind", reviews=[dict(path=str(zip_path.relative_to(ROOT)), sha256=p.digest(zip_path))])]
        entries.append(entry)
    return dict(schemaVersion=1, keypointSchema=config["keypointSchema"], sequences=entries)


def test_real_dog02_and_dalmatian_conversion_preserves_all_existing_inputs(tmp_path):
    job = real_job()
    refs = [s[k] for s in job["sequences"] for k in ("predictions", "metadata", "video")]
    proposal = ROOT / "reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.proposal.json"
    before = {r["path"]: p.digest(ROOT / r["path"]) for r in refs}
    before[str(proposal.relative_to(ROOT))] = p.digest(proposal)
    job_path = tmp_path / "real-job.json"
    job_path.write_text(json.dumps(job))
    report = prep.build(ROOT, job_path, tmp_path / "real-output")
    assert not report["trainingReady"]
    for group, count in [("dog02", 60), ("dalmatian", 177)]:
        r = report["sequences"][group]
        assert r["converted"] and r["frameCount"] == count
        assert r["rawScoreRange"][1] > 1
        assert r["independentValidTargets"]["LH"]["valid"] == 0
        with np.load(tmp_path / "real-output/sequences" / group / "features.npz", allow_pickle=False) as arrays:
            assert arrays["features"].shape == (count, 69)
            assert not arrays["target_valid"].any()
            assert np.isfinite(arrays["features"]).all()
    assert report["sequences"]["dalmatian"]["failedOrIncompletePoseFrames"] == 3
    evidence = report["sequences"]["dog02"]["reviewEvidence"][0]
    assert not evidence["independent"]
    assert evidence["exposedReviewers"] == ["reviewer-1"]
    assert all(p.digest(ROOT / name) == sha for name, sha in before.items())


def test_decoded_pose_replay_keeps_provenance_for_contact_preparation(tmp_path):
    """Decode real S004 frames with saved poses, without running a model."""
    from petlens_gait.inference import infer

    job = json.loads((ROOT / "reports/canine-contact-batch-v1/identity-neutral-exploratory/training-job.json").read_text())
    entry = job["sequences"][0]
    video = ROOT / entry["video"]["path"]
    if not video.is_file():
        pytest.skip("Local S004 video unavailable")
    saved = json.loads((ROOT / entry["predictions"]["path"]).read_text())
    metadata = json.loads((ROOT / entry["metadata"]["path"]).read_text())
    source = json.loads((ROOT / entry["sourceFrames"]["path"]).read_text())["datasets"][entry["sourceFrames"]["group"]]
    rows = iter(saved["frames"])

    def replay(_image):
        row = copy.deepcopy(next(rows))
        row.pop("frameIndex")
        row.pop("timestampSeconds")
        return row

    decoded = infer(video, tmp_path, replay)
    assert decoded.get("videoSha256") == entry["video"]["sha256"] == p.digest(video)
    # This is the same saved-prediction validator used by the preparer.
    p.validate_predictions(decoded, metadata, c.NAMES)
    actual = c.convert_sequence(decoded, source)
    expected = c.convert_sequence(saved, source)
    assert actual["features"].shape == (60, 69)
    np.testing.assert_array_equal(actual["features"], expected["features"])
    np.testing.assert_array_equal(actual["observed_mask"], expected["observed_mask"])
    assert [f["keypoints"] for f in decoded["frames"]] == [f["keypoints"] for f in saved["frames"]]
    assert decoded["fps"] == saved["fps"] == 12
