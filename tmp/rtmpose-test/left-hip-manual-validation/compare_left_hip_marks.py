from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
PREDICTIONS_FILE = (
    ROOT / "tmp" / "rtmpose-test" / "full-video" / "rtdetr-rtmpose-full-video.json"
)
MARKS_FILE = EXPERIMENT_DIR / "manual-left-hip-marks.json"
RESULTS_FILE = EXPERIMENT_DIR / "left-hip-comparison-results.json"


def prediction_by_frame() -> dict[int, dict[str, Any]]:
    payload = json.loads(PREDICTIONS_FILE.read_text(encoding="utf-8"))
    return {int(frame["frameIndex"]): frame for frame in payload["frames"]}


def calculate_results(marks: dict[str, Any]) -> dict[str, Any]:
    predictions = prediction_by_frame()
    results = []
    for entry in marks["frames"]:
        frame_index = int(entry["frameIndex"])
        manual_x = entry.get("manualX")
        manual_y = entry.get("manualY")
        if manual_x is None or manual_y is None:
            raise ValueError(
                f"Frame {frame_index} is not marked. Run mark_left_hips.py "
                "and click the left hip on every frame first."
            )
        frame = predictions.get(frame_index)
        if frame is None or not frame.get("detectionSuccess"):
            raise ValueError(f"No successful RTMPose prediction for frame {frame_index}.")
        hip = next(
            (
                point
                for point in frame.get("keypoints", [])
                if point.get("name") == "left_hip"
            ),
            None,
        )
        if hip is None:
            raise ValueError(f"No left-hip prediction for frame {frame_index}.")
        torso = frame.get("torsoReference")
        if torso is None or float(torso["shoulderToHipLength"]) <= 0:
            raise ValueError(f"Invalid torso reference on frame {frame_index}.")

        pixel_error = math.hypot(
            float(manual_x) - float(hip["x"]),
            float(manual_y) - float(hip["y"]),
        )
        torso_length = float(torso["shoulderToHipLength"])
        results.append(
            {
                "frameIndex": frame_index,
                "manualMark": {
                    "x": float(manual_x),
                    "y": float(manual_y),
                },
                "rtmposePrediction": {
                    "x": float(hip["x"]),
                    "y": float(hip["y"]),
                    "rawScore": float(hip["rawScore"]),
                },
                "euclideanErrorPixels": round(pixel_error, 4),
                "torsoLengthPixels": torso_length,
                "normalizedErrorTorsoLengths": round(pixel_error / torso_length, 6),
            }
        )
    return {
        "description": (
            "Manual marks are user-provided. Errors compare those marks with the "
            "unchanged RTMPose predictions; normalized error divides pixel distance "
            "by the original frame's RTMPose shoulder-to-hip length."
        ),
        "predictionsFile": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
        "manualMarksFile": MARKS_FILE.name,
        "results": results,
    }


def main() -> None:
    if not MARKS_FILE.is_file():
        raise FileNotFoundError(
            f"Manual marks file missing: {MARKS_FILE}. "
            "Run mark_left_hips.py first."
        )
    marks = json.loads(MARKS_FILE.read_text(encoding="utf-8"))
    results = calculate_results(marks)
    RESULTS_FILE.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("Frame | manual (x,y) | RTMPose (x,y) | raw score | error px | error / torso")
    for row in results["results"]:
        manual = row["manualMark"]
        prediction = row["rtmposePrediction"]
        print(
            f"{row['frameIndex']:5d} | "
            f"({manual['x']:.2f},{manual['y']:.2f}) | "
            f"({prediction['x']:.2f},{prediction['y']:.2f}) | "
            f"{prediction['rawScore']:.4f} | "
            f"{row['euclideanErrorPixels']:.2f} | "
            f"{row['normalizedErrorTorsoLengths']:.4f}"
        )
    print(f"\nComparison saved in {RESULTS_FILE}")


if __name__ == "__main__":
    main()
