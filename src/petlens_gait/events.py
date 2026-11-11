"""Conservative, unverified contact/lift-off candidates from supplied evidence.

``detect_events`` accepts time-ordered mappings, independently for each
``(sourceId, identity)``. Required provenance is a nonempty sourceId, a string or
integer physical identity, nonnegative frameIndex and source timestampSeconds.
Invalid provenance/order raises ValueError; timing is never repaired or sorted.

Evidence fields:
* pawPosition: finite {x, y} in source-image pixels; poseConfidence: [0, 1].
* segmentId and identityContinuous=True: a sufficiently certain, segment-local
  physical identity. Unknown identity must be flagged, never guessed.
* groundRelativeSpeed: nonnegative torso lengths / source second, already
  measured relative to visible ground (never body-relative or raw pixel speed).
* motionReference: 'camera_compensated_ground' or 'stationary_camera_ground'.
* groundReferenceReliable=True and groundMotionReliable=True.
* groundClearance: projected height above an explicit ground band, in torso
  lengths; groundClearanceReliable=True. Clearance may be absent, but this first
  conservative rule then abstains: slow motion alone cannot establish contact,
  and fast motion alone cannot distinguish swing from slipping contact.
* missing, invalid, positionSpike: optional boolean rejection flags.

All thresholds below are shared engineering defaults exercised on synthetic
signals, not fitted to a dog or established as biological thresholds. Both low
speed/low clearance and high speed/high clearance require consecutive samples.
The band between them is UNKNOWN, not interpolated contact. Genuine unknowns,
identity/segment changes and gaps reset transition and sequence history. Pending
confirmation also outputs UNKNOWN, but can retain the immediately preceding
supported run when every pending sample supports the opposite state.
If that pending run reverses before confirmation, reacquire consecutive support
from UNKNOWN; do not assemble support from samples on either side of a spike.

No image registration, motion estimation, pose inference, position-peak finding,
annotation edits or clinical/biological verification takes place here. Source
pixel positions never supply missing ground evidence; in particular a pixel
position spike cannot itself trigger an event. Upstream detected spikes should
be flagged. Isolated signal spikes are suppressed by confirmation, and extreme
signals are rejected; sustained plausible upstream errors cannot be ruled out.
"""

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from numbers import Real


CONTACT_SUPPORTED = "CONTACT_SUPPORTED"
SWING_SUPPORTED = "SWING_SUPPORTED"
UNKNOWN = "UNKNOWN"


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


@dataclass(frozen=True)
class EventRules:
    """One reproducible rule set for every source and paw, without dog tuning.

    Speed uses torso lengths/second; clearance uses torso lengths. Confirmation
    is a sample count, not an estimated event time. The gap limit is a sampling
    continuity guard, not a stride-duration rule. Upper bounds reject implausible
    input signals rather than clipping or correcting them. Pose confidence is a
    quality gate only, not a calibrated probability of contact or correctness.
    """

    min_pose_confidence: float = 0.5
    max_contact_speed: float = 0.10
    min_swing_speed: float = 0.25
    max_contact_clearance: float = 0.02
    min_swing_clearance: float = 0.05
    max_speed: float = 5.0
    max_clearance: float = 1.0
    min_clearance: float = -0.02
    min_support_samples: int = 2
    max_observation_gap_seconds: float = 0.25

    def __post_init__(self):
        numeric = asdict(self)
        numeric.pop("min_support_samples")
        if not all(_finite(value) for value in numeric.values()):
            raise ValueError("Rule thresholds must be finite numbers")
        if not (
            0 <= self.min_pose_confidence <= 1
            and 0 <= self.max_contact_speed < self.min_swing_speed <= self.max_speed
            and self.min_clearance <= 0 <= self.max_contact_clearance
            < self.min_swing_clearance <= self.max_clearance
            and self.max_observation_gap_seconds > 0
            and type(self.min_support_samples) is int
            and self.min_support_samples >= 2
        ):
            raise ValueError("Rules require ordered thresholds and >=2 support samples")


DEFAULT_EVENT_RULES = EventRules()


def _identifier(value):
    return type(value) is int or (isinstance(value, str) and bool(value.strip()))


def _validate_provenance(rows):
    previous = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each observation must be a dictionary")
        if not isinstance(row.get("sourceId"), str) or not row["sourceId"].strip():
            raise ValueError("sourceId must identify the source video")
        if not _identifier(row.get("identity")):
            raise ValueError("identity must be a physical paw identifier")
        frame = row.get("frameIndex")
        timestamp = row.get("timestampSeconds")
        if type(frame) is not int or frame < 0:
            raise ValueError("frameIndex must be a nonnegative integer")
        if not _finite(timestamp) or timestamp < 0:
            raise ValueError("timestampSeconds must be finite and nonnegative")
        key = (row["sourceId"], row["identity"])
        earlier = previous.get(key)
        if earlier is not None:
            if frame <= earlier["frameIndex"]:
                raise ValueError("frameIndex must strictly increase per source/paw")
            if timestamp <= earlier["timestampSeconds"]:
                raise ValueError("timestampSeconds must strictly increase per source/paw")
        previous[key] = row


def _classify(row, rules):
    reasons = []
    for flag in ("missing", "invalid", "positionSpike"):
        if row.get(flag, False) is not False:
            reasons.append(flag)
    point = row.get("pawPosition")
    if not isinstance(point, dict) or not all(
        _finite(point.get(axis)) for axis in ("x", "y")
    ):
        reasons.append("missing_or_invalid_paw_position")
    confidence = row.get("poseConfidence")
    if not _finite(confidence) or not rules.min_pose_confidence <= confidence <= 1:
        reasons.append("low_or_invalid_pose_confidence")
    if not _identifier(row.get("segmentId")) or row.get("identityContinuous") is not True:
        reasons.append("identity_uncertain")
    if row.get("groundReferenceReliable") is not True:
        reasons.append("ground_reference_unavailable_or_unreliable")
    if row.get("motionReference") not in (
        "camera_compensated_ground", "stationary_camera_ground"
    ) or row.get("groundMotionReliable") is not True:
        reasons.append("ground_motion_unavailable_or_unreliable")
    speed = row.get("groundRelativeSpeed")
    if not _finite(speed) or not 0 <= speed <= rules.max_speed:
        reasons.append("missing_or_invalid_ground_speed")
    clearance = row.get("groundClearance")
    if row.get("groundClearanceReliable") is not True:
        reasons.append("clearance_unavailable_or_unreliable")
    if not _finite(clearance) or not rules.min_clearance <= clearance <= rules.max_clearance:
        reasons.append("missing_or_invalid_clearance")
    if reasons:
        return UNKNOWN, reasons
    if speed <= rules.max_contact_speed and clearance <= rules.max_contact_clearance:
        return CONTACT_SUPPORTED, ["low_ground_speed_and_low_clearance"]
    if speed >= rules.min_swing_speed and clearance >= rules.min_swing_clearance:
        return SWING_SUPPORTED, ["high_ground_speed_and_clearance"]
    return UNKNOWN, ["ambiguous_or_conflicting_ground_evidence"]


def _source_ref(row):
    return {key: row[key] for key in (
        "observationIndex", "sourceId", "identity", "segmentId",
        "frameIndex", "timestampSeconds",
    )}


def _new_history(sample_count):
    return {
        "stableState": UNKNOWN,
        "stableSupport": deque(maxlen=sample_count),
        "pendingState": UNKNOWN,
        "pendingSupport": deque(maxlen=sample_count),
        "sequence": [],
    }


def detect_events(observations, config=DEFAULT_EVENT_RULES):
    """Return audited states, candidate transitions and contact-to-contact runs.

    The input is deep-copied unchanged into rawObservations, including unknown
    metadata, missing values and nonfinite values. Derived records are separate.
    No NaN sanitization or JSON serialization is performed on this raw archive.
    A missing frame or a time gap beyond the configured limit breaks continuity;
    missing observations must be supplied explicitly or visible as frame gaps.

    Events are bracketed between the last previous-state sample and the first
    next-state sample; frameIndex/timestampSeconds identify the latter, while
    confirmedAt records detection latency. Supporting evidence retains source
    and raw observation indices. Brackets are sampling uncertainty, not validated
    error bounds. Partial events remain visible, but a sequence requires an
    uninterrupted touchdown, lift-off, touchdown within one identity segment.
    Position peaks belong to cycles.detect_cycles and are never merged here.
    """
    if not isinstance(config, EventRules):
        raise ValueError("config must be EventRules")
    raw = deepcopy(list(observations))
    _validate_provenance(raw)
    states, events, sequences = [], [], []
    histories, previous = {}, {}
    evidence_fields = (
        "pawPosition", "poseConfidence", "identityContinuous", "missing",
        "invalid", "positionSpike", "motionReference", "groundReferenceReliable",
        "groundMotionReliable", "groundRelativeSpeed", "groundClearance",
        "groundClearanceReliable",
    )

    for index, row in enumerate(raw):
        key = (row["sourceId"], row["identity"])
        earlier = previous.get(key)
        continuity_reasons = []
        if earlier is not None:
            if row.get("segmentId") != earlier.get("segmentId"):
                continuity_reasons.append("identity_segment_changed")
            if row["frameIndex"] != earlier["frameIndex"] + 1:
                continuity_reasons.append("source_frame_gap")
            if (row["timestampSeconds"] - earlier["timestampSeconds"]
                    > config.max_observation_gap_seconds):
                continuity_reasons.append("source_time_gap")
        if key not in histories or continuity_reasons:
            histories[key] = _new_history(config.min_support_samples)
        history = histories[key]
        previous[key] = row
        evidence_state, reasons = _classify(row, config)
        record = {
            "observationIndex": index,
            "sourceId": row["sourceId"],
            "identity": row["identity"],
            "segmentId": row.get("segmentId"),
            "frameIndex": row["frameIndex"],
            "timestampSeconds": row["timestampSeconds"],
            "state": UNKNOWN,
            "evidenceState": evidence_state,
            "reasons": continuity_reasons + reasons,
            "evidence": {field: deepcopy(row.get(field)) for field in evidence_fields},
        }
        states.append(record)
        if evidence_state == UNKNOWN:
            histories[key] = _new_history(config.min_support_samples)
            continue
        if evidence_state == history["stableState"]:
            if history["pendingSupport"]:
                history = _new_history(config.min_support_samples)
                histories[key] = history
                record["reasons"].append("interrupted_support_run")
            else:
                history["stableSupport"].append(record)
                record["state"] = evidence_state
                continue
        if evidence_state != history["pendingState"]:
            history["pendingState"] = evidence_state
            history["pendingSupport"].clear()
        history["pendingSupport"].append(record)
        if len(history["pendingSupport"]) < config.min_support_samples:
            record["reasons"].append("awaiting_consecutive_support")
            continue

        record["state"] = evidence_state
        if history["stableState"] != UNKNOWN:
            before = history["stableSupport"][-1]
            after = history["pendingSupport"][0]
            event = {
                **_source_ref(after),
                "eventType": (
                    "candidate_touchdown" if evidence_state == CONTACT_SUPPORTED
                    else "candidate_lift_off"
                ),
                "fromState": history["stableState"],
                "toState": evidence_state,
                "boundary": {
                    "lastPrevious": _source_ref(before),
                    "firstNext": _source_ref(after),
                },
                "confirmedAt": _source_ref(record),
                "supportingEvidence": {
                    "previous": deepcopy(list(history["stableSupport"])),
                    "next": deepcopy(list(history["pendingSupport"])),
                },
                "uncertainty": {
                    "biologicallyVerified": False,
                    "timestampIntervalSeconds": [
                        before["timestampSeconds"], after["timestampSeconds"]
                    ],
                    "interpretation": "Candidate transition bracket, not a validated error bound.",
                    "probability": None,
                },
            }
            events.append(event)
            event_index = len(events) - 1
            sequence = history["sequence"]
            if event["eventType"] == "candidate_touchdown":
                if len(sequence) == 2:
                    start = events[sequence[0]]
                    sequences.append({
                        "sequenceType": "candidate_contact_to_contact",
                        "sourceId": row["sourceId"],
                        "identity": row["identity"],
                        "segmentId": row["segmentId"],
                        "eventIndices": [*sequence, event_index],
                        "start": _source_ref(start),
                        "end": _source_ref(event),
                        "candidateDurationSeconds": (
                            event["timestampSeconds"] - start["timestampSeconds"]
                        ),
                        "uncertainty": {
                            "biologicallyVerified": False,
                            "interpretation": "Three candidate events, not a verified stride.",
                        },
                    })
                history["sequence"] = [event_index]
            elif len(sequence) == 1:
                sequence.append(event_index)
        history["stableState"] = evidence_state
        history["stableSupport"] = deque(
            history["pendingSupport"], maxlen=config.min_support_samples
        )
        history["pendingSupport"].clear()
        history["pendingState"] = UNKNOWN

    return {
        "analysisType": "candidate_ground_relative_gait_events",
        "ruleSet": "ground-relative-candidates-v1",
        "config": asdict(config),
        "rawObservations": raw,
        "states": states,
        "events": events,
        "candidateSequences": sequences,
        "candidateSequenceCount": len(sequences),
        "verifiedWalkingCycleCount": 0,
        "limitations": [
            "All states, events and sequences are unverified evidence-based candidates.",
            "Projected ground evidence does not establish force or weight bearing.",
            "Pose scores and rule thresholds are not calibrated event probabilities.",
            "Upstream ground registration, scale, clearance and identity require validation.",
            "Position peaks are separate kinematic candidates; no clinical accuracy is claimed.",
        ],
    }
