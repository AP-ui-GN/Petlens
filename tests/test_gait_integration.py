"""Regression tests for the PetLens V2 integration."""

import json
from pathlib import Path

from petlens_gait.integration import analyze_predictions


def test_empty_predictions():
    result = analyze_predictions(
        {"frames": []},
        "tmp/rtmpose-test/paw-tracking-experiment",
    )
    assert result["frameCount"] == 0
    assert result["segments"] == []


def test_dalmatian_saved_prediction_replay():
    path = Path(
        "tmp/rtmpose-test/multi-video-evaluation/runs/"
        "dalmatian-day2-cfr-20261103/predictions.json"
    )

    if not path.exists():
        import pytest
        pytest.skip("Experimental Dalmatian predictions unavailable")

    data = json.loads(path.read_text())
    data["width"] = 1080
    data["height"] = 1920

    result = analyze_predictions(
        data,
        "tmp/rtmpose-test/paw-tracking-experiment",
    )

    assert result["frameCount"] == 177
    assert result["restartAccepted"] is True
    assert len(result["segments"]) == 3

    expected = [
        (0, 77, 124, 0),
        (87, 105, 32, 0),
        (107, 176, 131, 1),
    ]

    for segment, (start, end, measurements, cycles) in zip(
        result["segments"], expected
    ):
        assert (segment["startFrame"], segment["endFrame"]) == (start, end)
        assert segment["report"]["trackedPawMeasurements"] == measurements
        assert segment["report"]["pawSummary"]["0"]["candidateCycleCount"] == cycles
