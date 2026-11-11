"""Synthetic-only tests; no dog annotations, predictions or models are used."""

import copy
from dataclasses import FrozenInstanceError, replace
import math
import sys

import pytest

sys.path.insert(0, "src")

from petlens_gait.cycles import detect_cycles
from petlens_gait.events import (
    CONTACT_SUPPORTED,
    DEFAULT_EVENT_RULES,
    EventRules,
    SWING_SUPPORTED,
    UNKNOWN,
    detect_events,
)


def observations(pattern):
    """C/S encode independent, explicitly supplied ground evidence."""
    return [
        {
            "sourceId": "synthetic-source",
            "identity": "physical-paw-A",
            "segmentId": 0,
            "frameIndex": i,
            "timestampSeconds": i * 0.05,
            "pawPosition": {"x": 100 + i, "y": 200},
            "poseConfidence": 0.9,
            "identityContinuous": True,
            "motionReference": "camera_compensated_ground",
            "groundReferenceReliable": True,
            "groundMotionReliable": True,
            "groundRelativeSpeed": 0.02 if state == "C" else 0.8,
            "groundClearance": 0.005 if state == "C" else 0.12,
            "groundClearanceReliable": True,
            "missing": False,
            "invalid": False,
            "positionSpike": False,
        }
        for i, state in enumerate(pattern)
    ]


def test_candidate_contact_lift_off_and_contact_to_contact_sequence():
    result = detect_events(observations("SSCCSSCC"))

    assert [row["state"] for row in result["states"]] == [
        UNKNOWN, SWING_SUPPORTED, UNKNOWN, CONTACT_SUPPORTED,
        UNKNOWN, SWING_SUPPORTED, UNKNOWN, CONTACT_SUPPORTED,
    ]
    assert [event["eventType"] for event in result["events"]] == [
        "candidate_touchdown", "candidate_lift_off", "candidate_touchdown"
    ]
    assert [event["frameIndex"] for event in result["events"]] == [2, 4, 6]
    assert [event["confirmedAt"]["frameIndex"] for event in result["events"]] == [3, 5, 7]
    assert result["candidateSequenceCount"] == 1
    sequence = result["candidateSequences"][0]
    assert sequence["eventIndices"] == [0, 1, 2]
    assert sequence["start"]["frameIndex"] == 2
    assert sequence["end"]["frameIndex"] == 6
    assert sequence["candidateDurationSeconds"] == pytest.approx(0.2)
    assert sequence["uncertainty"]["biologicallyVerified"] is False
    assert result["verifiedWalkingCycleCount"] == 0


def test_event_source_brackets_evidence_and_uncertainty_are_auditable():
    rows = observations("SSCC")
    result = detect_events(rows)
    event = result["events"][0]

    assert event["timestampSeconds"] == rows[2]["timestampSeconds"]
    assert event["boundary"]["lastPrevious"]["frameIndex"] == 1
    assert event["boundary"]["firstNext"]["frameIndex"] == 2
    assert event["fromState"] == SWING_SUPPORTED
    assert event["toState"] == CONTACT_SUPPORTED
    assert event["uncertainty"]["timestampIntervalSeconds"] == [0.05, 0.1]
    assert event["uncertainty"]["biologicallyVerified"] is False
    assert event["uncertainty"]["probability"] is None
    for side, indices in (("previous", [0, 1]), ("next", [2, 3])):
        support = event["supportingEvidence"][side]
        assert [record["observationIndex"] for record in support] == indices
        for record in support:
            original = result["rawObservations"][record["observationIndex"]]
            assert record["sourceId"] == original["sourceId"]
            assert record["identity"] == original["identity"]
            assert record["segmentId"] == original["segmentId"]
            assert record["evidence"]["groundRelativeSpeed"] == original["groundRelativeSpeed"]
            assert record["evidence"]["groundClearance"] == original["groundClearance"]


@pytest.mark.parametrize("reference", ["camera_compensated_ground", "stationary_camera_ground"])
def test_ground_evidence_is_invariant_to_camera_motion_and_image_scale(reference):
    stationary = observations("SSCCSSCC")
    moving = copy.deepcopy(stationary)
    for i, row in enumerate(moving):
        # Arbitrary pixel translation, zoom and a large raw-position impulse.
        row["pawPosition"] = {"x": 10000 * (i % 3) + i * 13, "y": i * -200}
        row["motionReference"] = reference
    a, b = detect_events(stationary), detect_events(moving)

    assert [row["state"] for row in a["states"]] == [row["state"] for row in b["states"]]
    assert [(e["eventType"], e["frameIndex"]) for e in a["events"]] == [
        (e["eventType"], e["frameIndex"]) for e in b["events"]
    ]
    assert a["candidateSequences"] == b["candidateSequences"]


@pytest.mark.parametrize("field,value", [
    ("pawPosition", None), ("pawPosition", {}),
    ("pawPosition", {"x": float("nan"), "y": 3}),
    ("pawPosition", {"x": 3, "y": float("inf")}),
    ("pawPosition", {"x": True, "y": 3}),
    ("poseConfidence", 0.1), ("poseConfidence", None),
    ("poseConfidence", float("nan")), ("poseConfidence", 1.1),
    ("poseConfidence", True),
    ("identityContinuous", False), ("identityContinuous", None),
    ("identityContinuous", 1), ("segmentId", None),
    ("groundReferenceReliable", False), ("groundReferenceReliable", None),
    ("groundMotionReliable", False), ("groundClearanceReliable", False),
    ("motionReference", "body_relative"), ("motionReference", "raw_pixels"),
    ("motionReference", None),
    ("groundRelativeSpeed", None), ("groundRelativeSpeed", float("nan")),
    ("groundRelativeSpeed", float("inf")), ("groundRelativeSpeed", -0.1),
    ("groundRelativeSpeed", 6.0), ("groundRelativeSpeed", True),
    ("groundClearance", None), ("groundClearance", float("nan")),
    ("groundClearance", -0.1), ("groundClearance", 1.1),
    ("missing", True), ("invalid", True), ("positionSpike", True),
    ("missing", "false"),
])
def test_invalid_or_uncertain_sample_abstains_and_breaks_events_and_sequences(field, value):
    rows = observations("SSCCSSCC")
    rows[4][field] = value

    result = detect_events(rows)

    assert result["states"][4]["state"] == UNKNOWN
    assert result["states"][4]["evidenceState"] == UNKNOWN
    assert result["states"][4]["reasons"]
    assert result["candidateSequenceCount"] == 0
    assert [event["eventType"] for event in result["events"]] == ["candidate_touchdown"]


@pytest.mark.parametrize("field", [
    "pawPosition", "poseConfidence", "identityContinuous", "segmentId",
    "groundReferenceReliable", "groundMotionReliable", "motionReference",
    "groundRelativeSpeed", "groundClearance", "groundClearanceReliable",
])
def test_essential_evidence_is_never_invented_when_a_field_is_absent(field):
    rows = observations("SSCCSSCC")
    for row in rows:
        del row[field]
        # Familiar body/pixel speed names must not be used as fallbacks.
        row["speedPixelsPerSecond"] = 0.0
        row["normalizedBodyAxisPosition"] = 0.0
    result = detect_events(rows)

    assert all(row["state"] == UNKNOWN for row in result["states"])
    assert result["events"] == []
    assert all(field not in row for row in result["rawObservations"])


@pytest.mark.parametrize("gap", ["missing_frame", "missing_flag", "time_gap", "segment_change"])
def test_sequences_cannot_bridge_continuity_breaks_and_later_detection_recovers(gap):
    rows = observations("SSCCSSSSCCSSCC")
    if gap == "missing_frame":
        del rows[4]
    elif gap == "missing_flag":
        rows[4]["missing"] = True
    elif gap == "time_gap":
        for row in rows[4:]:
            row["timestampSeconds"] += 1.0
    else:
        for row in rows[4:]:
            row["segmentId"] = 1
    result = detect_events(rows)

    assert result["candidateSequenceCount"] == 1
    assert result["candidateSequences"][0]["start"]["frameIndex"] == 8
    assert result["candidateSequences"][0]["end"]["frameIndex"] == 12
    assert all(
        event["boundary"]["lastPrevious"]["frameIndex"] >= 5
        for event in result["events"][1:]
    )


@pytest.mark.parametrize("pattern", ["", "S", "C", "SS", "CC", "SSCC", "SSCCSS", "CCSSCC"])
def test_incomplete_cycles_do_not_create_a_complete_sequence(pattern):
    result = detect_events(observations(pattern))
    assert result["candidateSequenceCount"] == 0
    assert result["candidateSequences"] == []
    assert result["verifiedWalkingCycleCount"] == 0
    if pattern == "SSCCSS":
        assert len(result["events"]) == 2  # Preserve the valid partial events.


def test_stationary_paw_has_contact_support_without_fabricated_touchdown_or_cycle():
    rows = observations("C" * 20)
    for row in rows:
        row["pawPosition"] = {"x": 100, "y": 200}
        row["groundRelativeSpeed"] = 0.0
    result = detect_events(rows)
    assert result["states"][0]["state"] == UNKNOWN
    assert all(row["state"] == CONTACT_SUPPORTED for row in result["states"][1:])
    assert result["events"] == []
    assert result["candidateSequenceCount"] == 0


@pytest.mark.parametrize("pattern", ["CCCCSCCCC", "SSSSCSSSS", "CSCSCSCS"])
def test_single_sample_motion_and_clearance_spikes_cannot_trigger_events(pattern):
    result = detect_events(observations(pattern))
    assert result["events"] == []


def test_interrupted_support_must_be_reconfirmed_on_consecutive_samples():
    result = detect_events(observations("CCSCCSS"))
    assert [row["state"] for row in result["states"]] == [
        UNKNOWN, CONTACT_SUPPORTED, UNKNOWN, UNKNOWN, CONTACT_SUPPORTED,
        UNKNOWN, SWING_SUPPORTED,
    ]
    assert result["states"][3]["reasons"][-2:] == [
        "interrupted_support_run", "awaiting_consecutive_support"
    ]
    assert len(result["events"]) == 1
    assert [row["frameIndex"] for row in result["events"][0]["supportingEvidence"]["previous"]] == [3, 4]
    assert detect_events(observations("CCSCSS"))["events"] == []


def test_raw_pixel_position_peaks_cannot_trigger_ground_contact_events():
    rows = observations("C" * 15)
    peak_rows = []
    for i, row in enumerate(rows):
        row["pawPosition"]["x"] = 1000000 if i in (3, 9) else 100
        peak_rows.append({
            "identity": 0, "frameIndex": i, "timestampSeconds": row["timestampSeconds"],
            "normalizedBodyAxisPosition": 0.8 if i in (3, 9) else 0,
        })
    assert detect_cycles(peak_rows)[0]["candidateCycleCount"] == 1
    assert detect_events(rows)["events"] == []


@pytest.mark.parametrize("speed,clearance", [
    (0.0, 0.12), (0.8, 0.005), (0.15, 0.03), (0.02, 0.04),
])
def test_ambiguous_and_conflicting_evidence_is_unknown(speed, clearance):
    rows = observations("C" * 5)
    for row in rows:
        row.update(groundRelativeSpeed=speed, groundClearance=clearance)
    result = detect_events(rows)
    assert all(row["state"] == UNKNOWN for row in result["states"])
    assert result["events"] == []


def test_exact_shared_support_thresholds_and_longer_confirmation():
    config = replace(DEFAULT_EVENT_RULES, min_support_samples=3)
    rows = observations("SSSCCC")
    for row in rows[:3]:
        row.update(groundRelativeSpeed=config.min_swing_speed,
                   groundClearance=config.min_swing_clearance)
    for row in rows[3:]:
        row.update(groundRelativeSpeed=config.max_contact_speed,
                   groundClearance=config.max_contact_clearance,
                   poseConfidence=config.min_pose_confidence)
    result = detect_events(rows, config)
    assert len(result["events"]) == 1
    assert result["events"][0]["confirmedAt"]["frameIndex"] == 5
    assert result["config"]["min_support_samples"] == 3
    assert DEFAULT_EVENT_RULES.min_support_samples == 2
    with pytest.raises(FrozenInstanceError):
        DEFAULT_EVENT_RULES.min_support_samples = 3


@pytest.mark.parametrize("changes", [
    {"min_support_samples": 1}, {"min_support_samples": True},
    {"min_support_samples": 2.5}, {"max_contact_speed": 0.3},
    {"max_contact_clearance": 0.06}, {"min_pose_confidence": -1},
    {"min_swing_speed": float("nan")}, {"max_speed": float("inf")},
    {"max_observation_gap_seconds": 0}, {"min_clearance": 0.01},
    {"max_contact_speed": True},
])
def test_invalid_shared_rules_fail_explicitly(changes):
    with pytest.raises(ValueError):
        EventRules(**changes)


@pytest.mark.parametrize("value", [None, -0.1, float("nan"), float("inf"), -float("inf"), "0.2", True])
def test_invalid_timestamps_raise_without_repair_or_input_mutation(value):
    rows = observations("SSCCSSCC")
    rows[3]["timestampSeconds"] = value
    before = copy.deepcopy(rows)
    with pytest.raises(ValueError, match="timestampSeconds"):
        detect_events(rows)
    assert repr(rows) == repr(before)


@pytest.mark.parametrize("value", [0.1, 0.05])
def test_duplicate_and_decreasing_timestamps_are_rejected(value):
    rows = observations("SSCC")
    rows[3]["timestampSeconds"] = value
    with pytest.raises(ValueError, match="timestampSeconds"):
        detect_events(rows)


@pytest.mark.parametrize("value", [None, -1, 1.5, True, float("nan")])
def test_invalid_frame_indices_fail_explicitly(value):
    rows = observations("SSCC")
    rows[2]["frameIndex"] = value
    with pytest.raises(ValueError, match="frameIndex"):
        detect_events(rows)


@pytest.mark.parametrize("mode", ["duplicate", "out_of_order"])
def test_frame_order_is_validated_and_never_silently_sorted(mode):
    rows = observations("SSCC")
    if mode == "duplicate":
        rows.insert(2, copy.deepcopy(rows[1]))
    else:
        rows[1], rows[2] = rows[2], rows[1]
    with pytest.raises(ValueError, match="frameIndex"):
        detect_events(rows)


@pytest.mark.parametrize("field", ["frameIndex", "timestampSeconds", "sourceId", "identity"])
def test_missing_provenance_fails_explicitly(field):
    rows = observations("SSCC")
    del rows[2][field]
    with pytest.raises(ValueError, match=field):
        detect_events(rows)


def test_valid_irregular_source_timing_is_preserved():
    rows = observations("SSCCSSCC")
    times = [0.0, 0.03, 0.08, 0.13, 0.2, 0.24, 0.32, 0.4]
    for row, timestamp in zip(rows, times):
        row["timestampSeconds"] = timestamp
    result = detect_events(rows)
    assert [e["timestampSeconds"] for e in result["events"]] == [0.08, 0.2, 0.32]
    assert result["candidateSequences"][0]["candidateDurationSeconds"] == pytest.approx(0.24)


@pytest.mark.parametrize("separation", ["sourceId", "identity"])
def test_paw_and_source_histories_are_independent(separation):
    first = observations("SSCCSSCC")
    second = copy.deepcopy(first)
    for row in second:
        row[separation] = "other"
    first[4]["identityContinuous"] = False
    interleaved = [row for pair in zip(first, second) for row in pair]
    result = detect_events(interleaved)

    assert result["candidateSequenceCount"] == 1
    assert result["candidateSequences"][0][separation] == "other"
    assert all(e["boundary"]["lastPrevious"][separation] == e[separation]
               for e in result["events"])


def test_source_inputs_and_nested_unknown_metadata_are_preserved_exactly():
    rows = observations("SSCCSSCC")
    rows[0]["custom"] = {"original": [None, 0, "do not change"], "empty": {}}
    before = copy.deepcopy(rows)
    result = detect_events(iter(rows))
    assert rows == before
    assert result["rawObservations"] == before
    result["rawObservations"][0]["custom"]["original"].append("output edit")
    result["events"][0]["supportingEvidence"]["next"][0]["evidence"]["pawPosition"]["x"] = -99
    assert rows == before
    assert result["rawObservations"][2]["pawPosition"] == before[2]["pawPosition"]


def test_nonfinite_raw_evidence_is_preserved_without_sanitization():
    rows = observations("SSCC")
    rows[2]["groundRelativeSpeed"] = float("nan")
    rows[2]["pawPosition"]["x"] = float("inf")
    result = detect_events(rows)
    assert math.isnan(rows[2]["groundRelativeSpeed"])
    assert math.isnan(result["rawObservations"][2]["groundRelativeSpeed"])
    assert result["rawObservations"][2]["pawPosition"]["x"] == float("inf")
    assert result["states"][2]["state"] == UNKNOWN
    assert result["events"] == []
