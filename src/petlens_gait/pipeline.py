"""Combine PetLens paw tracking with gait analysis."""

from petlens_gait.metrics import calculate_metrics
from petlens_gait.cycles import detect_cycles


def analyze_gait(prediction_frames, tracking_frames):
    """Produce a structured exploratory gait report."""
    measurements = calculate_metrics(
        prediction_frames,
        tracking_frames,
    )
    cycles = detect_cycles(measurements)

    frame_count = len(tracking_frames)
    possible_paws = frame_count * 2
    tracked_paws = len(measurements)

    summary = {}

    for identity, result in cycles.items():
        summary[str(identity)] = {
            "candidateCycleCount": result["candidateCycleCount"],
            "meanCycleSeconds": result["meanCycleSeconds"],
            "candidatePeakCount": len(result["peaks"]),
        }

    return {
        "analysisType": "exploratory_hind_paw_gait",
        "frameCount": frame_count,
        "trackedPawMeasurements": tracked_paws,
        "trackingCoverage": (
            tracked_paws / possible_paws
            if possible_paws else 0.0
        ),
        "pawSummary": summary,
        "cycles": {
            str(identity): result
            for identity, result in cycles.items()
        },
        "measurements": measurements,
        "limitations": [
            "Paw identities are local to the tracking segment.",
            "Candidate peaks are not verified footfalls.",
            "Results are not veterinary diagnoses.",
        ],
    }
