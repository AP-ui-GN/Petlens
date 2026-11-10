"""Detect candidate position oscillations, never verified ground-contact cycles."""

import math


def _finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def detect_cycles(measurements, min_position=0.2, min_interval=0.3):
    """Find candidate peak-to-peak intervals for each supplied paw identity.

    Missing/nonfinite positions split runs; no peak suppression or interval can
    cross a run boundary. Invalid frame indices or timestamps raise ValueError
    rather than returning a partial report with silently repaired timing.
    Identity correctness and ground-contact events are not verified here.
    """
    result = {}

    for identity in sorted(set(m["identity"] for m in measurements)):
        rows = [m for m in measurements if m["identity"] == identity]
        if any(
            type(row.get("frameIndex")) is not int or row["frameIndex"] < 0
            for row in rows
        ):
            raise ValueError("frameIndex must be a nonnegative integer")
        rows = sorted(rows, key=lambda m: m["frameIndex"])

        runs = []
        run = []
        previous = None
        for row in rows:
            if previous is not None and row["frameIndex"] == previous["frameIndex"]:
                raise ValueError("Duplicate frameIndex for the same paw identity")
            timestamp = row.get("timestampSeconds")
            if (
                not _finite_number(timestamp)
                or timestamp < 0
                or (
                    previous is not None
                    and timestamp <= previous["timestampSeconds"]
                )
            ):
                raise ValueError(
                    "timestampSeconds must be finite, nonnegative and strictly "
                    "increasing in frame order for each paw identity"
                )
            previous = row

            valid = _finite_number(row.get("normalizedBodyAxisPosition"))
            if run and (
                not valid or row["frameIndex"] != run[-1]["frameIndex"] + 1
            ):
                runs.append(run)
                run = []
            if valid:
                run.append(row)
        if run:
            runs.append(run)

        peaks = []
        intervals = []
        for run in runs:
            run_peaks = []
            for i in range(1, len(run) - 1):
                previous, current, following = run[i - 1:i + 2]
                a = previous["normalizedBodyAxisPosition"]
                b = current["normalizedBodyAxisPosition"]
                c = following["normalizedBodyAxisPosition"]

                if not (b > a and b >= c and b > min_position):
                    continue

                peak = {
                    "frameIndex": current["frameIndex"],
                    "timestampSeconds": current["timestampSeconds"],
                    "position": b,
                    "eventType": "candidate_forward_position_peak",
                }
                if run_peaks and (
                    current["timestampSeconds"] - run_peaks[-1]["timestampSeconds"]
                    < min_interval
                ):
                    if b > run_peaks[-1]["position"]:
                        run_peaks[-1] = peak
                    continue

                run_peaks.append(peak)

            peaks.extend(run_peaks)
            intervals.extend(
                end["timestampSeconds"] - start["timestampSeconds"]
                for start, end in zip(run_peaks, run_peaks[1:])
            )

        result[identity] = {
            "analysisType": "candidate_peak_to_peak_cycles",
            "verifiedWalkingCycleCount": 0,
            "peaks": peaks,
            "candidateCycleCount": len(intervals),
            # Compatibility name: this is candidate peak-to-peak timing only.
            "meanCycleSeconds": (
                sum(intervals) / len(intervals) if intervals else None
            ),
            "limitations": [
                "Position peaks and intervals are candidates, not verified "
                "ground contacts or walking cycles.",
                "Repeated isolated spikes can produce candidate intervals; "
                "position samples alone do not verify a physical stride.",
            ],
        }

    return result
