"""Tests for PetLens candidate walking-cycle detection."""

import copy
import math
import sys
import unittest

import pytest

sys.path.insert(0, "src")

from petlens_gait.cycles import detect_cycles


def make_measurements(positions):
    return [
        {
            "frameIndex": i,
            "timestampSeconds": i * 0.1,
            "identity": 0,
            "normalizedBodyAxisPosition": value,
        }
        for i, value in enumerate(positions)
    ]


class CycleDetectionTests(unittest.TestCase):

    def test_stationary_paw(self):
        result = detect_cycles(make_measurements([0.1] * 30))
        self.assertEqual(len(result[0]["peaks"]), 0)

    def test_single_spike(self):
        positions = [0.0] * 30
        positions[15] = 0.8

        result = detect_cycles(make_measurements(positions))

        # A single spike must not count as a complete cycle.
        self.assertEqual(result[0]["candidateCycleCount"], 0)

    def test_repeating_pattern(self):
        positions = [0.0, 0.1, 0.5, 0.1, 0.0] * 5
        result = detect_cycles(make_measurements(positions))

        self.assertEqual(len(result[0]["peaks"]), 5)
        self.assertEqual(result[0]["candidateCycleCount"], 4)
        self.assertEqual(result[0]["verifiedWalkingCycleCount"], 0)
        self.assertEqual(result[0]["analysisType"], "candidate_peak_to_peak_cycles")

    def test_tracking_gap(self):
        rows = make_measurements([0.0, 0.5, 0.0, 0.5, 0.0])
        rows[2]["frameIndex"] = 20
        # Keep frame order and time consistent so this tests only the gap.
        rows[2]["timestampSeconds"] = 2.0

        result = detect_cycles(rows)
        self.assertEqual(len(result[0]["peaks"]), 0)


if __name__ == "__main__":
    unittest.main()


def test_cycle_intervals_do_not_cross_tracking_gaps():
    from petlens_gait.cycles import detect_cycles

    positions = [
        (0, 0.0), (1, 0.5), (2, 0.0),
        (10, 0.0), (11, 0.6), (12, 0.0),
    ]
    measurements = [
        {
            "identity": 0,
            "frameIndex": frame,
            "timestampSeconds": frame * 0.1,
            "normalizedBodyAxisPosition": position,
        }
        for frame, position in positions
    ]

    result = detect_cycles(measurements)[0]

    assert len(result["peaks"]) == 2
    assert result["candidateCycleCount"] == 0
    assert result["meanCycleSeconds"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("index", [1, 3, 5])
def test_nonfinite_positions_cannot_support_a_cycle(value, index):
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    rows[index]["normalizedBodyAxisPosition"] = value

    result = detect_cycles(rows)[0]

    assert result["candidateCycleCount"] == 0
    assert result["meanCycleSeconds"] is None
    assert all(math.isfinite(peak["position"]) for peak in result["peaks"])


@pytest.mark.parametrize("gap", ["null", "absent_position", "absent_frame"])
def test_missing_prediction_cannot_bridge_two_peaks(gap):
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    if gap == "null":
        rows[3]["normalizedBodyAxisPosition"] = None
    elif gap == "absent_position":
        del rows[3]["normalizedBodyAxisPosition"]
    else:
        del rows[3]

    result = detect_cycles(rows)[0]

    assert len(result["peaks"]) == 2
    assert result["candidateCycleCount"] == 0
    assert result["meanCycleSeconds"] is None


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), None, -0.1, "0.3", True]
)
@pytest.mark.parametrize("index", [1, 3, 5])
def test_invalid_timestamps_fail_explicitly(value, index):
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    rows[index]["timestampSeconds"] = value

    with pytest.raises(ValueError, match="timestamp"):
        detect_cycles(rows)


@pytest.mark.parametrize("value", [0.2, 0.1])
def test_nonincreasing_interior_timestamp_cannot_hide_behind_valid_endpoints(value):
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    rows[3]["timestampSeconds"] = value

    with pytest.raises(ValueError, match="timestamp"):
        detect_cycles(rows)


def test_missing_timestamp_fails_explicitly():
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    del rows[3]["timestampSeconds"]

    with pytest.raises(ValueError, match="timestamp"):
        detect_cycles(rows)


def test_duplicate_frame_cannot_mask_a_missing_prediction():
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    duplicate = dict(rows[3], normalizedBodyAxisPosition=None)
    rows.insert(4, duplicate)

    with pytest.raises(ValueError, match="frame"):
        detect_cycles(rows)


@pytest.mark.parametrize("value", [None, -1, 1.5, float("nan"), True])
def test_invalid_frame_indices_fail_explicitly(value):
    rows = make_measurements([0.0, 0.5, 0.0])
    rows[1]["frameIndex"] = value

    with pytest.raises(ValueError, match="frame"):
        detect_cycles(rows)


def test_peak_suppression_does_not_cross_a_prediction_gap():
    rows = make_measurements([0.0, 0.9, 0.0, None, 0.0, 0.5, 0.0])
    for row in rows:
        row["timestampSeconds"] = row["frameIndex"] * 0.05

    result = detect_cycles(rows)[0]

    assert [peak["frameIndex"] for peak in result["peaks"]] == [1, 5]
    assert result["candidateCycleCount"] == 0


def test_repeated_isolated_spikes_are_only_candidates_never_verified_cycles():
    result = detect_cycles(
        make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    )[0]

    # Position samples alone cannot distinguish brief real motion from spikes.
    assert result["candidateCycleCount"] == 1
    assert result["analysisType"] == "candidate_peak_to_peak_cycles"
    assert result["verifiedWalkingCycleCount"] == 0
    assert all(
        peak["eventType"] == "candidate_forward_position_peak"
        for peak in result["peaks"]
    )
    assert any("spikes" in limitation for limitation in result["limitations"])


def test_valid_cycles_after_a_gap_are_preserved_without_mutating_input():
    rows = make_measurements([0.0, 0.9, 0.0, None] + [0.0, 0.1, 0.5, 0.1, 0.0] * 3)
    before = copy.deepcopy(rows)

    result = detect_cycles(rows)[0]

    assert result["candidateCycleCount"] == 2
    assert result["meanCycleSeconds"] == pytest.approx(0.5)
    assert result["verifiedWalkingCycleCount"] == 0
    assert rows == before


def test_valid_irregular_timestamps_use_elapsed_time():
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    for row, timestamp in zip(rows, [0.0, 0.1, 0.2, 0.4, 0.7, 0.9, 1.0]):
        row["timestampSeconds"] = timestamp

    result = detect_cycles(rows)[0]

    assert result["candidateCycleCount"] == 1
    assert result["meanCycleSeconds"] == pytest.approx(0.8)


def test_a_prediction_gap_affects_only_its_own_identity():
    rows = make_measurements([0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0])
    other_paw = [dict(row, identity=1) for row in rows]
    rows[3]["normalizedBodyAxisPosition"] = None

    result = detect_cycles(rows + other_paw)

    assert result[0]["candidateCycleCount"] == 0
    assert result[1]["candidateCycleCount"] == 1


def test_empty_measurements_have_no_candidates():
    assert detect_cycles([]) == {}
