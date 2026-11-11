"""Offline saved-pose adapter; no inference, training, downloads or video writes.

Run from the repository root::

    python -m training.prepare_contact_sequences --job job.json --output-dir NEW
    python -m training.prepare_contact_sequences --job job.json --output-dir NEW \
        --require-training-ready

Inspection is the default (--inspect is also accepted). Exit 0 means conversion
succeeded, not training readiness; --require-training-ready exits 3 on blockers
after writing the report. Invalid provenance/structure exits 2, without export.

Job schema (paths relative to --root, hashes required on every file reference)::

    {"schemaVersion": 1, "keypointSchema": {"path": "...", "sha256": "..."},
     "sequences": [{"id": "example", "predictions": {"path": "...", "sha256": "..."},
       "metadata": {"path": "...", "sha256": "..."},
       "sourceFrames": {"path": "...", "sha256": "...", "group": "gait-dalmatian"},
       "video": {"path": "...", "sha256": "..."},
       "dogId": null, "dogIdentityVerified": false, "split": "unassigned",
       "provenanceGroup": null, "trainingApproved": false,
       "rights": {"status": "unknown", "evidence": ""},
       "timing": {"sourceType": "unknown", "nativeVerified": false, "evidence": ""},
       "reviews": []}]}

sourceFrames accepts the existing gait manifest (select group), a single source
metadata object, or S004's source-frame-map list (dimensions from metadata and
sourceVideo from metadata or an explicit job file reference). Its sourceVideo
file is hash-checked. A different working video needs
metadata.originalVideoSha256 or an explicit conversion record; all frame times
are checked. Optional sourceFrameRange=[0,last] selects an explicitly declared
saved prefix, never an invented timeline. Optional predictionEnvelope supplies
missing provenance fields for legacy list-only/partial envelopes; it cannot
override recorded fields. Optional conversion and ancestors are hashed refs.

reviews entries reuse existing A/B JSON or ZIP exports::

    {"pair": "hind", "mapping": {"A": "LH", "B": "RH"},
     "mappingEvidence": {"verified": true, "reviewer": "human", "evidence": "..."},
     "reviews": [{"path": "...", "sha256": "..."}, {"path": "...", "sha256": "..."}],
     "adjudication": {"path": "...", "sha256": "...", "reviewers": ["r1", "r2"],
                      "evidence": "Human reconciliation of these two reviews"},
     "exposureRecords": [{"path": "...", "sha256": "..."}]}

Adjudication is another existing-format review JSON, explicitly linked to two
independent original reviewers. No flag alone finalizes a source review. Only
unanimous visible/continuous definite observations may become targets; conflicts
remain masked even if an adjudication asserts a definite state. Fore pair uses
LF/RF. Unmapped/unsigned/unadjudicated reviews remain inspectable with zero loss
weight. Known later Dog02 exposure records override legacy blind declarations.

Outputs: manifest.json and validation.json plus sequences/<id>/{features.npz,
manifest.json,validation.json,raw-observations.json}. Load NPZ with
allow_pickle=False. Gather a window with valid indices ONLY; -1 is padding,
never a Python negative array index. Pad features/targets with zero and combine
target_valid with ~padding_mask. Window targets must not supervise padding.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from petlens_gait import contact_features as c
from training import gait_event_review as review
from training import prepare_paw_annotations as p


def _write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _audit_numbers(value):
    """Keep finite source numbers at JSON precision; tag invalid floats explicitly."""
    if isinstance(value, float) and not c.finite(value):
        return {"invalidNumeric": repr(value)}
    if isinstance(value, dict):
        return {k: _audit_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_audit_numbers(v) for v in value]
    return value


def _file(root, record, inputs):
    c.require(isinstance(record, dict) and isinstance(record.get("path"), str) and
              isinstance(record.get("sha256"), str) and
              re.fullmatch(r"[0-9a-f]{64}", record["sha256"]), "Expected hashed file reference")
    path = p.checked(root, record)
    inputs[str(path.relative_to(root))] = record["sha256"]
    return path


def _document(root, record, inputs):
    return p.load_json(_file(root, record, inputs))


def _json_bytes(raw):
    # Reuse duplicate-key/nonfinite rejection without extracting ZIP members.
    def pairs(items):
        result = {}
        for key, value in items:
            c.require(key not in result, "Duplicate review JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Nonfinite review JSON value: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _load_review(root, record, source, manifest_hash, inputs):
    path = _file(root, record, inputs)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            required = {"manifest.json", "review.json", "frame-manifest.json", "validation.json"}
            c.require(set(archive.namelist()) == required and len(archive.namelist()) == 4,
                      "Unexpected/duplicate review ZIP members")
            c.require(all(i.file_size <= 20_000_000 for i in archive.infolist()), "Oversized review ZIP")
            raw = {name: archive.read(name) for name in required}
        envelope = _json_bytes(raw["manifest.json"])
        c.require(envelope.get("manifestSha256") == manifest_hash and
                  envelope.get("sourceVideo") == source["sourceVideo"], "Review ZIP source mismatch")
        hashes = envelope.get("outputSha256", {})
        for name in required - {"manifest.json"}:
            c.require(hashes.get(name) == review.digest_bytes(raw[name]), "Review ZIP member hash mismatch")
        c.require(_json_bytes(raw["frame-manifest.json"]) == source, "Review frame metadata mismatch")
        draft = _json_bytes(raw["review.json"])
        c.require(envelope.get("reviewer") == draft.get("reviewer"), "Review ZIP reviewer mismatch")
    else:
        draft = p.load_json(path)
    review.validate(source, manifest_hash, draft)
    return draft


def _exposed_reviewers(root, pair, source, inputs):
    records = list(pair.get("exposureRecords", []))
    known = root / "reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.proposal.json"
    if known.is_file():
        records.append(dict(path=str(known.relative_to(root)), sha256=p.digest(known)))
    exposed = set()
    for record in records:
        doc = _document(root, record, inputs)
        if doc.get("sourceVideo", {}).get("sha256") != source["sourceVideo"]["sha256"]:
            continue
        declaration = doc.get("independence", {}).get("proposedDeclaration")
        if declaration == "prior_exposure" or doc.get("independenceDeclaration") == "prior_exposure":
            c.require(isinstance(doc.get("reviewer"), str) and doc["reviewer"].strip(),
                      "Exposure record lacks reviewer")
            exposed.add(doc["reviewer"].strip())
    return exposed


def _labels(root, specs, source, manifest_hash, arrays, inputs):
    count = len(arrays["timestamps"])
    result = dict(targets=np.zeros((count, 4), dtype=np.float32),
                  target_valid=np.zeros((count, 4), dtype=bool),
                  identity_valid=np.zeros((count, 4), dtype=bool),
                  visibility_valid=np.zeros((count, 4), dtype=bool),
                  label_valid=np.zeros((count, 4), dtype=bool),
                  identity_segments=np.full((count, 4), -1, dtype=np.int64),
                  target_reasons=np.full((count, 4), "unreviewed", dtype="U48"))
    findings, seen_pairs = [], set()
    for spec in specs:
        pair = spec.get("pair")
        c.require(pair in ("fore", "hind") and pair not in seen_pairs, "Duplicate/unknown review pair")
        seen_pairs.add(pair)
        drafts = [_load_review(root, r, source, manifest_hash, inputs) for r in spec.get("reviews", [])]
        exposure = _exposed_reviewers(root, spec, source, inputs)
        reviewer_ids = [d["reviewer"].strip() for d in drafts]
        independent = (len(drafts) == 2 and len(set(reviewer_ids)) == 2 and all(reviewer_ids) and
                       all(d["independenceDeclaration"] == "no_prior_exposure" and
                           d["reviewer"].strip() not in exposure for d in drafts))
        mapping = spec.get("mapping", {})
        evidence = spec.get("mappingEvidence", {})
        expected = {"fore": {"LF", "RF"}, "hind": {"LH", "RH"}}[pair]
        mapped = (set(mapping) == {"A", "B"} and set(mapping.values()) == expected and
                  evidence.get("verified") is True and bool(evidence.get("reviewer", "").strip()) and
                  bool(evidence.get("evidence", "").strip()))
        adjudication = spec.get("adjudication")
        final = None
        if adjudication:
            final = _load_review(root, adjudication, source, manifest_hash, inputs)
        adjudicated = (final is not None and independent and
                       set(adjudication.get("reviewers", [])) == set(reviewer_ids) and
                       bool(adjudication.get("evidence", "").strip()) and
                       final["independenceDeclaration"] == "no_prior_exposure" and
                       bool(final["reviewer"].strip()) and final["reviewer"].strip() not in exposure)
        findings.append(dict(pair=pair, reviewers=reviewer_ids, independent=independent,
                             exposedReviewers=sorted(exposure), mappingVerified=mapped,
                             adjudicated=adjudicated))
        if not mapped:
            columns = [c.PAWS.index(paw) for paw in expected]
            result["target_reasons"][:, columns] = "anatomical_mapping_unverified"
            continue
        for physical, paw in mapping.items():
            j = c.PAWS.index(paw)
            sid, last = -1, None
            for key in source["selectedFrames"]:
                i = int(key)
                if i >= count:
                    continue
                observation = final["observations"][str(i)][physical] if final else None
                reason = "review_not_independent" if not independent else "not_adjudicated"
                if not adjudicated:
                    result["target_reasons"][i, j] = reason
                    continue
                originals = [d["observations"][str(i)][physical] for d in drafts]
                same = all(all(o[f] == observation[f] for f in ("visibility", "continuity", "supportState"))
                           for o in originals)
                visible = same and observation["visibility"] == "visible"
                continuous = same and observation["continuity"] in ("start", "continuous")
                known = same and observation["supportState"] in ("contacting", "airborne")
                result["visibility_valid"][i, j] = visible
                result["identity_valid"][i, j] = continuous and visible
                if continuous and visible:
                    if last != i - 1 or observation["continuity"] == "start":
                        sid += 1
                    result["identity_segments"][i, j] = sid
                    last = i
                else:
                    last = None
                if not same:
                    reason = "reviewer_disagreement"
                elif not visible:
                    reason = observation["visibility"]
                elif not continuous:
                    reason = "identity_" + observation["continuity"]
                elif not known:
                    reason = observation["supportState"]
                else:
                    result["label_valid"][i, j] = True
                    result["targets"][i, j] = float(observation["supportState"] == "contacting")
                    pose_ok = arrays["reference_valid"][i] and arrays["observed_mask"][i, c.PAW_INDICES[j]]
                    result["target_valid"][i, j] = pose_ok
                    reason = "valid" if pose_ok else "pose_ineligible"
                result["target_reasons"][i, j] = reason
    return result, findings


def _known_policies(root, hashes, entry, source, inputs):
    """Preserve recorded Dog02 exclusions/publication grouping/Husky timing ban."""
    excluded, timing_ban = False, False
    publication_group = None
    config_path = root / "training/paw_annotation_sources.json"
    if config_path.is_file():
        config = _document(root, dict(path=str(config_path.relative_to(root)), sha256=p.digest(config_path)), inputs)
        for old in config["sequences"]:
            if old["group"] == "dog02":
                known_hashes = {old[k]["sha256"] for k in ("predictions", "video")}
                if hashes & known_hashes:
                    excluded = True
                    publication_group = "publication:shin-2013"
    source_name = source["sourceVideo"].get("path", "")
    if "pone.0059875.s00" in source_name:
        publication_group = "publication:shin-2013"
        excluded |= "s003" in source_name
    husky_path = root / "reports/husky-evaluation/annotation-manifest-v1.json"
    if husky_path.is_file():
        husky = _document(root, dict(path=str(husky_path.relative_to(root)), sha256=p.digest(husky_path)), inputs)
        timing_ban = bool(hashes & {husky["video"]["sha256"], husky["originalSource"]["sha256"]})
    # Historical uncertain-origin cream-dog derivatives cannot attest native FPS.
    for name in ("dog-walking-test-01.mp4", "petlens-dog-walking-trimmed.mp4"):
        path = root / "tmp/petlens-v2-unseen" / name
        if path.is_file() and p.digest(path) in hashes:
            timing_ban = True
    excluded |= entry.get("group") == "dog02"
    return excluded, timing_ban, publication_group


def _prepare_one(root, entry, names, mode="strict"):
    inputs = {}
    raw_predictions = _document(root, entry["predictions"], inputs)
    metadata = _document(root, entry["metadata"], inputs)
    original_frames = _document(root, entry["sourceFrames"], inputs)
    manifest_hash = entry["sourceFrames"]["sha256"]
    if isinstance(original_frames, dict) and "datasets" in original_frames:
        group = entry["sourceFrames"].get("group")
        c.require(group in original_frames["datasets"], "Choose a sourceFrames group")
        source = copy.deepcopy(original_frames["datasets"][group])
    elif isinstance(original_frames, list):
        source = dict(frames=original_frames, frameCount=len(original_frames),
                      frameWidth=metadata["frameWidth"], frameHeight=metadata["frameHeight"],
                      sourceVideo=metadata.get("sourceVideo", entry.get("sourceVideo")))
    else:
        source = copy.deepcopy(original_frames)
    _file(root, source["sourceVideo"], inputs)
    _file(root, entry["video"], inputs)
    c.require(metadata.get("videoSha256") == entry["video"]["sha256"], "Metadata/video hash mismatch")
    c.require(metadata.get("predictionSha256") == entry["predictions"]["sha256"],
              "Metadata/prediction hash mismatch")
    envelope = entry.get("predictionEnvelope", {})
    predictions = dict(frames=raw_predictions) if isinstance(raw_predictions, list) else dict(raw_predictions)
    for key, value in envelope.items():
        c.require(key not in predictions or predictions[key] == value, "Prediction envelope cannot override saved fields")
        predictions[key] = value
    c.require(predictions.get("videoSha256") == entry["video"]["sha256"], "Prediction/video hash mismatch")
    if "sourceFrameRange" in entry:
        first, last = entry["sourceFrameRange"]
        c.require(type(first) is int and first == 0 and type(last) is int and
                  0 <= last < source["frameCount"] and last+1 == predictions["frameCount"],
                  "Only an explicitly declared saved prefix is supported")
        source["frames"] = source["frames"][:last+1]
        source["frameCount"] = last+1
        c.require(metadata["sourceFrameCount"] == len(metadata["frames"]) and
                  metadata["sourceFrameCount"] >= last+1, "Invalid prefix metadata count")
        # An explicitly requested prefix is a view of existing frame references,
        # not a new inferred timeline or an edit to the saved source manifest.
        metadata = dict(metadata, sourceFrameCount=last+1, frames=metadata["frames"][:last+1])
        c.require(not entry.get("reviews"), "Prefix review metadata needs a dedicated source manifest")
    conversion = None
    if entry.get("conversion"):
        conversion = _document(root, entry["conversion"], inputs)
        c.require(conversion.get("outputSha256") == entry["video"]["sha256"], "Conversion working-video hash mismatch")
        from petlens_gait.ground import validate_alignment
        validate_alignment(predictions, source, conversion)
    elif source["sourceVideo"]["sha256"] != entry["video"]["sha256"]:
        c.require(metadata.get("originalVideoSha256") == source["sourceVideo"]["sha256"],
                  "Missing original/derivative source linkage")
    arrays = c.convert_sequence(predictions, source)
    # Existing validator rejects malformed structure/model/schema/timing. Remove
    # only nonfinite point triples in this validation view: the converter has
    # already recorded their missingness, and raw audit data is never changed.
    view = copy.deepcopy(predictions)
    for frame in view["frames"]:
        frame["keypoints"] = [point for point in frame["keypoints"]
                              if all(c.finite(point.get(k)) for k in ("x", "y", "rawScore"))]
    p.validate_predictions(view, metadata, names)
    if metadata.get("originalVideoSha256"):
        c.require(metadata["originalVideoSha256"] == source["sourceVideo"]["sha256"],
                  "Original-video hash mismatch")
    c.require((metadata["frameWidth"], metadata["frameHeight"]) ==
              (source["frameWidth"], source["frameHeight"]), "Original/working dimension mismatch")
    if mode == "exploratory_train_only":
        from training.contact_exploratory import labels as exploratory_labels
        labels, review_findings = exploratory_labels(root, entry, source, arrays, inputs, _document, p.digest)
    else:
        labels, review_findings = _labels(root, entry.get("reviews", []), source, manifest_hash, arrays, inputs)
    arrays.update(labels)
    neutral = entry.get("supervisionOutput", "anatomical") == "identity_neutral_front"
    window_identity = (np.repeat(arrays["physical_identity_segments"], 4, axis=1) if neutral
                       else arrays["identity_segments"])
    arrays.update(c.make_windows(arrays["reference_valid"], arrays["timestamps"], window_identity))
    supervised = ({k: arrays["physical_"+k] for k in
                   ("targets", "target_valid", "label_valid", "identity_valid", "visibility_valid")}
                  if neutral else arrays)
    output_names = ("physical:" + entry["physicalOutput"]["physicalPaw"],) if neutral else c.PAWS
    for ancestor in entry.get("ancestors", []):
        _file(root, ancestor, inputs)
    lineage = {entry["predictions"]["sha256"], entry["video"]["sha256"], source["sourceVideo"]["sha256"]}
    lineage.update(r["sha256"] for r in entry.get("ancestors", []))
    excluded, timing_ban, publication = _known_policies(root, lineage, entry, source, inputs)
    record = dict(id=entry["id"], dogId=c.canonical_dog_id(entry.get("dogId")),
                  split=entry.get("split", "unassigned"),
                  provenanceGroup=publication or entry.get("provenanceGroup"), lineageHashes=sorted(lineage))
    timing = entry.get("timing", {})
    timing_eligible = (not timing_ban and timing.get("sourceType") == "native" and
                       timing.get("nativeVerified") is True and bool(timing.get("evidence", "").strip()))
    blockers = []
    if not record["dogId"] or entry.get("dogIdentityVerified") is not True:
        blockers.append("verified_dog_identity_missing")
    if not record["provenanceGroup"]:
        blockers.append("provenance_group_missing")
    if record["split"] not in ("train", "validation", "test"):
        blockers.append("training_split_unassigned_or_exploratory")
    if entry.get("trainingApproved") is not True:
        blockers.append("training_not_approved")
    if excluded:
        blockers.append("existing_exploratory_only_policy")
    # Approval already recorded in the DogReID manifest cannot be bypassed by job flags.
    screened = root / "reports/dogreid-1553/screened-videos.json"
    if screened.is_file():
        screen_doc = _document(root, dict(path=str(screened.relative_to(root)), sha256=p.digest(screened)), inputs)
        rows = screen_doc if isinstance(screen_doc, list) else screen_doc.get("videos", [])
        for row in rows:
            if row.get("sha256") in lineage and row.get("training_approved") is not True:
                blockers.append("dogreid_training_not_approved")
    rights = entry.get("rights", {})
    if rights.get("status") != "cleared" or not rights.get("evidence", "").strip():
        blockers.append("commercial_rights_unresolved")
    movie_timing = (mode == "exploratory_train_only" and not timing_ban and
                    timing.get("sourceType") == "source_movie" and
                    timing.get("sourcePtsVerified") is True and bool(timing.get("evidence", "").strip()))
    if not timing_eligible and not movie_timing:
        blockers.append("native_timing_unverified_or_excluded")
    counts = {}
    for j, paw in enumerate(output_names):
        valid = supervised["target_valid"][:, j]
        counts[paw] = dict(valid=int(valid.sum()), contacting=int(np.sum(valid & (supervised["targets"][:, j] == 1))),
                           airborne=int(np.sum(valid & (supervised["targets"][:, j] == 0))))
    if not supervised["label_valid"].any():
        blockers.append("approved_sparse_contact_labels_missing" if mode == "exploratory_train_only"
                        else "independent_adjudicated_contact_labels_missing")
    if not supervised["identity_valid"].any():
        blockers.append("verified_physical_paw_identity_missing")
    if not supervised["target_valid"].any():
        blockers.append("no_supervised_pose_eligible_paw_frames")
    if not arrays["window_indices"].size:
        blockers.append("no_eligible_temporal_windows")
    raw_scores = [point["rawScore"] for frame in predictions["frames"] for point in frame["keypoints"]
                  if c.finite(point.get("rawScore"))]
    windows = arrays["window_indices"]
    window_supervised = [bool(supervised["target_valid"][row[row >= 0]].any()) for row in windows]
    report = dict(converted=True, frameCount=predictions["frameCount"], featureShape=list(arrays["features"].shape),
                  referenceValidFrames=int(arrays["reference_valid"].sum()),
                  failedOrIncompletePoseFrames=sum(len(f["keypoints"]) != 17 or not f["detectionSuccess"]
                                                   for f in predictions["frames"]),
                  rawScoreRange=[min(raw_scores), max(raw_scores)] if raw_scores else None,
                  rawScoresAboveOne=sum(s > 1 for s in raw_scores), rawScoresAreProbabilities=False,
                  observationReasons=dict(Counter(arrays["observation_reasons"].flat)),
                  referenceReasons=dict(Counter(arrays["reference_reasons"].flat)),
                  targetReasons=dict(Counter(arrays["physical_target_reasons" if neutral else "target_reasons"].flat)),
                  identityEligiblePawFrames={paw: int(supervised["identity_valid"][:, j].sum()) for j, paw in enumerate(output_names)},
                  visibleReviewedPawFrames={paw: int(supervised["visibility_valid"][:, j].sum()) for j, paw in enumerate(output_names)},
                  excludedFeatureFrames=int((~arrays["reference_valid"]).sum()),
                  independentValidTargets=counts, reviewEvidence=review_findings,
                  temporalWindows=len(windows), supervisedWindows=sum(window_supervised),
                  featureOnlyWindows=len(windows)-sum(window_supervised),
                  nativeTimingEvaluationEligible=timing_eligible,
                  trainingReady=not blockers, blockers=blockers)
    if mode == "exploratory_train_only":
        report["approvedTargets"] = report.pop("independentValidTargets")
    manifest = dict(schemaVersion=c.VERSION, **record, inputs=inputs, sourceVideo=source["sourceVideo"],
                    workingVideo=entry["video"], sourceFrames=source["frames"],
                    channelOrder=list(c.CHANNELS), pawOrder=list(c.PAWS), policy=c.POLICY,
                    dogIdentityVerified=entry.get("dogIdentityVerified") is True,
                    rights=rights, timing=timing, trainingApproved=entry.get("trainingApproved") is True,
                    reviewEvidence=review_findings, reviewSpecifications=entry.get("reviews", []),
                    sourceFrameRange=entry.get("sourceFrameRange"),
                    identityPolicy="Model channels and feature windows never confirm physical identity",
                    normalization="Per-frame neck/tail midpoint and distance; no fitted statistics",
                    paddingPolicy="window_indices=-1; padding_mask=True; gather nonnegative indices only",
                    trainingReady=report["trainingReady"])
    manifest["trainingMode"] = mode
    manifest["supervisionOutput"] = entry.get("supervisionOutput", "anatomical")
    manifest["physicalOutput"] = review_findings[0]["physicalOutput"] if neutral else None
    manifest["nativeTimingEvaluationEligible"] = timing_eligible
    manifest["independentValidation"] = False if mode == "exploratory_train_only" else None
    return arrays, manifest, report, _audit_numbers(raw_predictions)


def build(root, job_path, output, mode="strict"):
    root, job_path, output = Path(root).resolve(), Path(job_path).resolve(), Path(output).absolute()
    c.require(not output.exists(), f"Output already exists: {output}")
    job_hash = p.digest(job_path)
    job = p.load_json(job_path)
    c.require(mode in ("strict", "exploratory_train_only") and
              job.get("trainingMode", "strict") == mode, "Training mode mismatch")
    supervision = job.get("supervisionOutput", "anatomical")
    c.require(supervision in ("anatomical", "identity_neutral_front") and
              all(e.get("supervisionOutput", "anatomical") == supervision for e in job.get("sequences", [])),
              "Supervision output mismatch")
    if supervision == "identity_neutral_front":
        c.require(mode == "exploratory_train_only" and len(job["sequences"]) == 1,
                  "Identity-neutral supervision requires one exploratory source")
    if mode == "exploratory_train_only":
        c.require(all(e.get("split") == "train" for e in job.get("sequences", [])),
                  "Exploratory mode accepts train-only sources")
        dogs = {c.canonical_dog_id(e.get("dogId")) for e in job.get("sequences", [])}
        c.require(len(dogs) == 1 and None not in dogs, "Exploratory mode requires one verified dog group")
    c.require(job.get("schemaVersion") == 1 and isinstance(job.get("sequences"), list) and job["sequences"],
              "Expected contact conversion job schemaVersion=1 with sequences")
    c.require(not job.get("normalizationFitDogIds"), "This adapter cannot fit normalization on any dogs")
    schema_inputs = {}
    schema = _document(root, job["keypointSchema"], schema_inputs)
    names = [point["id"] for point in schema["keypoints"]]
    c.require(schema.get("schema_version") == "petlens.ap10k-17.v1" and names == list(c.NAMES),
              "AP-10K keypoint schema mismatch")
    ids = [entry.get("id") for entry in job["sequences"]]
    c.require(all(isinstance(i, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", i) for i in ids)
              and len(set(ids)) == len(ids), "Unsafe/duplicate sequence IDs")
    prepared = [_prepare_one(root, entry, names, mode) for entry in job["sequences"]]
    records = [manifest for _, manifest, _, _ in prepared]
    c.validate_partitions(records)
    # Reuse the existing DogReID dog-key split invariant without running its UI/report builder.
    helper = ROOT / "reports/dogreid-1553/build_review.py"
    spec = importlib.util.spec_from_file_location("petlens_contact_identity_splits", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_identity_splits([dict(identity_group_key=r["dogId"], petlens_split=r["split"])
                                    for r in records if r["dogId"]])
    c.require(p.digest(job_path) == job_hash, "Job changed during preparation")
    # Recheck ALL consumed inputs before creating output; no existing output is overwritten.
    for _, manifest, _, _ in prepared:
        for name, sha in {**schema_inputs, **manifest["inputs"]}.items():
            p.checked(root, dict(path=name, sha256=sha))
    reports = {m["id"]: r for _, m, r, _ in prepared}
    blockers = [f"{sid}: {reason}" for sid, r in reports.items() for reason in r["blockers"]]
    # Coverage is a collection-level four-paw training gate, not a per-clip demand.
    for paw in c.PAWS if mode == "strict" else ():
        train = [r["independentValidTargets"][paw] for m, r in zip(records, reports.values()) if m["split"] == "train"]
        if not train or any(sum(row[state] for row in train) == 0 for state in ("contacting", "airborne")):
            blockers.append(f"training_cohort_missing_both_states_{paw}")
    summary = dict(schemaVersion=c.VERSION, converted=True, trainingReady=not blockers,
                   blockers=blockers, sequences=reports,
                   note="Conversion is not measured contact accuracy; no model trained or run.")
    summary["trainingMode"] = mode
    output.mkdir(parents=True, exist_ok=False)
    for arrays, manifest, report, raw in prepared:
        folder = output / "sequences" / manifest["id"]
        folder.mkdir(parents=True)
        with (folder / "features.npz").open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        _write(folder / "raw-observations.json", raw)
        _write(folder / "validation.json", report)
        manifest["outputs"] = {name: p.digest(folder / name) for name in
                               ("features.npz", "raw-observations.json", "validation.json")}
        _write(folder / "manifest.json", manifest)
    _write(output / "validation.json", summary)
    _write(output / "manifest.json", dict(schemaVersion=c.VERSION, jobSha256=job_hash,
           adapterSha256=p.digest(Path(c.__file__)), preparerSha256=p.digest(Path(__file__)),
           job=job, keypointSchema=job["keypointSchema"], channelOrder=list(c.CHANNELS), pawOrder=list(c.PAWS),
           policy=c.POLICY, trainingMode=mode, supervisionOutput=supervision, trainingReady=summary["trainingReady"],
           sequences=[dict(id=m["id"], manifest=f"sequences/{m['id']}/manifest.json",
                           sha256=p.digest(output / "sequences" / m["id"] / "manifest.json")) for m in records]))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--training-mode", choices=("strict", "exploratory_train_only"), default="strict")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", action="store_true", help="Export even when contact labels are absent (default)")
    mode.add_argument("--require-training-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = build(args.root, args.job, args.output_dir, args.training_mode)
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, OverflowError) as exc:
        print(f"Contact feature preparation failed: {exc}", file=sys.stderr)
        return 2
    for name, report in summary["sequences"].items():
        print(f"{name}: {report['frameCount']} frames -> {report['featureShape']}; "
              f"training-ready={report['trainingReady']}")
    print(json.dumps(dict(trainingReady=summary["trainingReady"], blockers=summary["blockers"]), indent=2))
    return 3 if args.require_training_ready and not summary["trainingReady"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
