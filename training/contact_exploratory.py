"""Explicitly signed exploratory label import; no UI, auto-approval or model."""
from pathlib import Path

import numpy as np

from petlens_gait import contact_features as c

MODE = "exploratory_train_only"
SCOPES = ("trainOnly", "sparsePaws", "sourceMovieTiming",
          "singleExposedReviewer", "noGeneralizationClaims")
POLICY = Path(__file__).resolve().parents[1] / "docs/EXPLORATORY_CONTACT_POLICY.md"
NEUTRAL = "identity_neutral_front"
NEUTRAL_POLICY = POLICY.with_name("EXPLORATORY_IDENTITY_NEUTRAL_POLICY.md")


def signed(record):
    return (isinstance(record, dict) and record.get("approved") is True and
            all(isinstance(record.get(k), str) and record[k].strip()
                for k in ("reviewer", "date", "evidence")))


def labels(root, entry, source, arrays, inputs, document, digest):
    """Consume original sparse sidecar plus separate owner/observation approvals."""
    approval = document(root, entry["exploratoryApproval"], inputs)
    c.require(signed(approval) and approval.get("role") == "project_owner" and
              approval.get("trainingApproved") is True,
              "Exploratory owner authorization missing or unsigned")
    c.require(approval.get("policySha256") == digest(POLICY) and
              approval.get("mode") == MODE and
              all(approval.get("scopes", {}).get(k) is True for k in SCOPES),
              "Exploratory policy hash/scope authorization missing")
    expected = {k: entry[k]["sha256"] for k in
                ("predictions", "video", "metadata", "sourceFrames", "exploratoryLabels", "rightsEvidence")}
    expected["sourceVideo"] = source["sourceVideo"]["sha256"]
    neutral = entry.get("supervisionOutput", "anatomical") == NEUTRAL
    if neutral:
        expected["physicalIdentityEvidence"] = entry["physicalIdentityEvidence"]["sha256"]
        c.require(approval.get("identityNeutralPolicySha256") == digest(NEUTRAL_POLICY) and
                  approval.get("scopes", {}).get("identityNeutralOutput") is True and
                  approval.get("physicalOutput") == entry.get("physicalOutput"),
                  "Identity-neutral policy/output authorization missing")
    c.require(approval.get("inputHashes") == expected, "Approval input hash mismatch")
    c.require(c.canonical_dog_id(approval.get("dogId")) == c.canonical_dog_id(entry.get("dogId"))
              and approval.get("provenanceGroup") == entry.get("provenanceGroup")
              and entry.get("split") == "train", "Approval dog/group/train-only mismatch")
    c.require(signed(approval.get("dogIdentity")), "Signed dog/source identity evidence missing")
    rights = approval.get("rights", {})
    c.require(signed(rights) and isinstance(rights.get("attribution"), str) and rights["attribution"].strip(),
              "Exploratory rights approval/attribution missing")
    document(root, entry["rightsEvidence"], inputs)
    doc = document(root, entry["exploratoryLabels"], inputs)
    c.require(doc.get("sourceVideo") == source["sourceVideo"] and
              doc.get("manifestSha256") == entry["sourceFrames"]["sha256"],
              "Sparse labels source provenance mismatch")
    c.require(isinstance(doc.get("reviewer"), str) and doc["reviewer"].strip() and
              doc.get("independenceDeclaration") in ("prior_exposure", "no_prior_exposure"),
              "Original reviewer/exposure declaration missing")
    count = len(arrays["timestamps"])
    result = dict(targets=np.zeros((count, 4), np.float32),
                  target_valid=np.zeros((count, 4), bool),
                  label_valid=np.zeros((count, 4), bool),
                  identity_valid=np.zeros((count, 4), bool),
                  visibility_valid=np.zeros((count, 4), bool),
                  identity_segments=np.full((count, 4), -1, np.int64),
                  target_reasons=np.full((count, 4), "unreviewed", dtype="U48"))
    anatomical = None
    binding = None
    mapping = {}
    if neutral:
        spec = entry["physicalOutput"]
        physical = spec.get("physicalPaw")
        c.require(spec.get("kind") == "tracked_front" and spec.get("anatomicalSide") == "unknown" and
                  "front" in source.get("pawRoles", {}).get(physical, "").casefold() and
                  type(spec.get("firstFrame")) is int and type(spec.get("lastFrame")) is int and
                  0 <= spec["firstFrame"] <= spec["lastFrame"] < count,
                  "Invalid tracked front-paw specification")
        c.require(all(not signed(item) and item.get("anatomicalPaw") is None
                      for item in approval.get("mapping", {}).values()),
                  "Identity-neutral output cannot assign anatomical sides")
        continuity = document(root, entry["physicalIdentityEvidence"], inputs)
        c.require(continuity.get("sourceVideo") == source["sourceVideo"] and
                  continuity.get("physicalOutput") == spec and continuity.get("continuityConfirmed") is True and
                  continuity.get("independenceDeclaration") == doc["independenceDeclaration"],
                  "Physical continuity evidence does not match output/source")
        binding = {**spec, "sourceVideoSha256": source["sourceVideo"]["sha256"],
                   "dogId": c.canonical_dog_id(entry["dogId"]), "datasetId": source["datasetId"]}
        anatomical = result
        result = {k: np.full((count, 1), "unreviewed", dtype="U48") if k == "target_reasons"
                  else np.full((count, 1), -1, np.int64) if k == "identity_segments"
                  else np.zeros((count, 1), dtype=v.dtype) for k, v in result.items()}
        mapping[physical] = "physical:" + physical
    for physical, item in (() if neutral else approval.get("mapping", {}).items()):
        if not signed(item):
            continue
        paw = item.get("anatomicalPaw")
        role = source.get("pawRoles", {}).get(physical, "").casefold()
        allowed = {"LF", "RF"} if "front" in role else {"LH", "RH"} if "hind" in role else set()
        c.require(paw in allowed and paw not in mapping.values(), "Invalid/duplicate anatomical mapping")
        mapping[physical] = paw
    spans = approval.get("identitySpans", [])
    for sid, span in enumerate(spans):
        c.require(signed(span) and span.get("physicalPaw") in mapping and
                  span.get("physicalContinuous" if neutral else "visibleContinuous") is True,
                  "Unverified physical identity span")
        lo, hi = span.get("firstFrame"), span.get("lastFrame")
        c.require(type(lo) is int and type(hi) is int and 0 <= lo <= hi < count, "Invalid identity span")
        if neutral:
            c.require(lo == binding["firstFrame"] and hi == binding["lastFrame"],
                      "Identity span must match physical output binding")
        j = 0 if neutral else c.PAWS.index(mapping[span["physicalPaw"]])
        c.require(np.all(result["identity_segments"][lo:hi+1, j] == -1), "Overlapping identity spans")
        result["identity_segments"][lo:hi+1, j] = sid
        result["identity_valid"][lo:hi+1, j] = True
        if not neutral:
            result["visibility_valid"][lo:hi+1, j] = True
    approved = approval.get("observations", {})
    seen, seen_frames = set(), set()
    for observation in doc.get("observations", []):
        oid = observation["id"]
        c.require(oid not in seen, "Duplicate observation ID")
        seen.add(oid)
        physical = observation["physicalPaw"]
        frame = observation["frame"]
        i = frame["frameIndex"]
        c.require((physical, i) not in seen_frames, "Duplicate physical paw/frame observation")
        seen_frames.add((physical, i))
        c.require(type(i) is int and 0 <= i < count and
                  all(frame.get(k) == source["frames"][i].get(k) for k in
                      ("frameIndex", "originalPts", "originalTimeBase", "timestampSeconds")),
                  "Observation frame provenance mismatch")
        if physical not in mapping:
            continue
        j = 0 if neutral else c.PAWS.index(mapping[physical])
        if (observation.get("assessmentStatus") != "definite" or observation.get("conflicts") or
                observation.get("reportedSupportState") not in ("contacting", "airborne") or
                observation.get("coreEncoding", {}).get("visibility") != "visible"):
            result["target_reasons"][i, j] = "excluded_source_state"
            continue
        if not signed(approved.get(oid)):
            result["target_reasons"][i, j] = "observation_not_approved"
            continue
        if neutral:
            result["visibility_valid"][i, j] = True
        pose_ok = (arrays["observed_mask"][i, [7, 10]].all() if neutral
                   else arrays["observed_mask"][i, c.PAW_INDICES[j]])
        eligible = result["identity_valid"][i, j] and arrays["reference_valid"][i] and pose_ok
        result["targets"][i, j] = float(observation["reportedSupportState"] == "contacting")
        result["label_valid"][i, j] = True
        result["target_valid"][i, j] = eligible
        result["target_reasons"][i, j] = "valid" if eligible else "identity_or_pose_ineligible"
    c.require(set(approved) <= seen, "Approval references unknown observations")
    if neutral:
        result = {**anatomical, **{"physical_"+k: v for k,v in result.items()},
                  "physical_pose_valid": arrays["observed_mask"][:, [7,10]].all(axis=1, keepdims=True)}
    return result, [dict(policy=MODE, owner=approval["reviewer"], physicalOutput=binding,
                         originalReviewer=doc["reviewer"], exposure=doc["independenceDeclaration"],
                         independentValidation=False, authorization=entry["exploratoryApproval"])]
