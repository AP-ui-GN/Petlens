from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
INPUT = ROOT / "tmp" / "rtmpose-test" / "full-video" / "rtdetr-rtmpose-full-video.json"
JSON_OUTPUT = EXPERIMENT_DIR / "body-reference-comparison.json"
REPORT_OUTPUT = EXPERIMENT_DIR / "body-reference-comparison.md"

SCORE_THRESHOLD = 0.80
PAW_JUMP_CUTOFF_BODY_LENGTHS = 0.35
PAW_NAME = "right_back_paw"
METHODS = {
    "A": {
        "label": "Shoulder + AP-10K hip",
        "landmarks": ("left_shoulder", "right_shoulder", "left_hip", "right_hip"),
    },
    "B": {
        "label": "Neck + tail root",
        "landmarks": ("neck", "root_of_tail"),
    },
}


def midpoint(
    first: dict[str, Any], second: dict[str, Any]
) -> tuple[float, float]:
    return (
        (float(first["x"]) + float(second["x"])) / 2,
        (float(first["y"]) + float(second["y"])) / 2,
    )


def distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "maximum": None,
        }
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
        "maximum": max(values),
    }


def make_reference(
    method: str, points: dict[str, dict[str, Any]]
) -> dict[str, float]:
    if method == "A":
        shoulder_center = midpoint(points["left_shoulder"], points["right_shoulder"])
        hip_center = midpoint(points["left_hip"], points["right_hip"])
        center = midpoint(
            {"x": shoulder_center[0], "y": shoulder_center[1]},
            {"x": hip_center[0], "y": hip_center[1]},
        )
        length = distance(shoulder_center, hip_center)
    else:
        center = midpoint(points["neck"], points["root_of_tail"])
        length = distance(
            (float(points["neck"]["x"]), float(points["neck"]["y"])),
            (
                float(points["root_of_tail"]["x"]),
                float(points["root_of_tail"]["y"]),
            ),
        )
    if length <= 1e-6:
        raise ValueError(f"Method {method} produced a zero reference length.")
    return {
        "centerX": center[0],
        "centerY": center[1],
        "length": length,
    }


def build_frame_data(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        frame_index = int(record["frameIndex"])
        points = {
            point["name"]: point
            for point in record.get("keypoints", [])
            if point.get("name") is not None
        }
        frame: dict[str, Any] = {
            "frameIndex": frame_index,
            "detectionSuccess": bool(record.get("detectionSuccess")),
            "methods": {},
        }
        paw = points.get(PAW_NAME)
        paw_ok = bool(
            record.get("detectionSuccess")
            and paw is not None
            and paw.get("x") is not None
            and paw.get("y") is not None
            and paw.get("rawScore") is not None
            and float(paw["rawScore"]) >= SCORE_THRESHOLD
        )
        frame["rightBackPaw"] = {
            "x": float(paw["x"]) if paw and paw.get("x") is not None else None,
            "y": float(paw["y"]) if paw and paw.get("y") is not None else None,
            "rawScore": (
                float(paw["rawScore"])
                if paw and paw.get("rawScore") is not None
                else None
            ),
            "passesThreshold": paw_ok,
        }
        for method, config in METHODS.items():
            landmark_names = config["landmarks"]
            landmarks_present = all(
                name in points
                and points[name].get("x") is not None
                and points[name].get("y") is not None
                and points[name].get("rawScore") is not None
                for name in landmark_names
            )
            passing = bool(
                record.get("detectionSuccess")
                and landmarks_present
                and all(
                    float(points[name]["rawScore"]) >= SCORE_THRESHOLD
                    for name in landmark_names
                )
            )
            reference = (
                make_reference(method, points) if landmarks_present else None
            )
            paw_position = None
            if reference is not None and paw_ok:
                paw_position = {
                    "x": (float(paw["x"]) - reference["centerX"])
                    / reference["length"],
                    "y": (float(paw["y"]) - reference["centerY"])
                    / reference["length"],
                }
            frame["methods"][method] = {
                "referencePassesThreshold": passing,
                "landmarkScores": {
                    name: (
                        float(points[name]["rawScore"])
                        if name in points and points[name].get("rawScore") is not None
                        else None
                    )
                    for name in landmark_names
                },
                "centerX": reference["centerX"] if reference else None,
                "centerY": reference["centerY"] if reference else None,
                "referenceLength": reference["length"] if reference else None,
                "normalizedRightBackPaw": paw_position,
                "pawRelativeAvailable": bool(passing and paw_ok),
            }
        result.append(frame)
    return result


def method_summary(
    frames: list[dict[str, Any]], method: str
) -> dict[str, Any]:
    valid_lengths = [
        frame["methods"][method]["referenceLength"]
        for frame in frames
        if frame["methods"][method]["referencePassesThreshold"]
        and frame["methods"][method]["referenceLength"] is not None
    ]
    length_deltas = []
    for before, after in zip(frames, frames[1:]):
        first = before["methods"][method]
        second = after["methods"][method]
        if not (
            first["referencePassesThreshold"]
            and second["referencePassesThreshold"]
            and first["referenceLength"] is not None
            and second["referenceLength"] is not None
        ):
            continue
        first_length = first["referenceLength"]
        second_length = second["referenceLength"]
        length_deltas.append(
            {
                "fromFrame": before["frameIndex"],
                "toFrame": after["frameIndex"],
                "absolutePixels": abs(second_length - first_length),
                "percentOfPrevious": abs(second_length - first_length)
                / first_length
                * 100,
                "signedPixels": second_length - first_length,
            }
        )

    paw_positions = [
        frame
        for frame in frames
        if frame["methods"][method]["pawRelativeAvailable"]
    ]
    paw_jumps = []
    all_paw_score_jumps = []
    all_paw_score_jump_candidates = []
    for before, after in zip(frames, frames[1:]):
        first = before["methods"][method]
        second = after["methods"][method]
        if not (
            before["rightBackPaw"]["passesThreshold"]
            and after["rightBackPaw"]["passesThreshold"]
            and first["normalizedRightBackPaw"] is not None
            and second["normalizedRightBackPaw"] is not None
        ):
            continue
        p1, p2 = first["normalizedRightBackPaw"], second["normalizedRightBackPaw"]
        jump = distance((p1["x"], p1["y"]), (p2["x"], p2["y"]))
        event = {
            "fromFrame": before["frameIndex"],
            "toFrame": after["frameIndex"],
            "jumpBodyLengthsPerFrame": jump,
            "fromReferencePassesThreshold": first["referencePassesThreshold"],
            "toReferencePassesThreshold": second["referencePassesThreshold"],
        }
        all_paw_score_jump_candidates.append(event)
        if jump > PAW_JUMP_CUTOFF_BODY_LENGTHS:
            all_paw_score_jumps.append(event)
            if first["referencePassesThreshold"] and second["referencePassesThreshold"]:
                paw_jumps.append(event)

    length_values = [float(value) for value in valid_lengths]
    length_delta_pixels = [item["absolutePixels"] for item in length_deltas]
    length_delta_percent = [item["percentOfPrevious"] for item in length_deltas]
    length_cv = (
        statistics.pstdev(length_values) / statistics.fmean(length_values) * 100
        if len(length_values) > 1 and statistics.fmean(length_values) != 0
        else None
    )
    largest_length_changes = sorted(
        length_deltas,
        key=lambda item: item["percentOfPrevious"],
        reverse=True,
    )[:5]
    largest_paw_jumps = []
    for before, after in zip(frames, frames[1:]):
        first = before["methods"][method]
        second = after["methods"][method]
        if not (first["pawRelativeAvailable"] and second["pawRelativeAvailable"]):
            continue
        p1, p2 = first["normalizedRightBackPaw"], second["normalizedRightBackPaw"]
        jump = distance((p1["x"], p1["y"]), (p2["x"], p2["y"]))
        largest_paw_jumps.append(
            {
                "fromFrame": before["frameIndex"],
                "toFrame": after["frameIndex"],
                "jumpBodyLengthsPerFrame": jump,
            }
        )
    largest_paw_jumps.sort(
        key=lambda item: item["jumpBodyLengthsPerFrame"], reverse=True
    )
    all_paw_score_jump_candidates.sort(
        key=lambda item: item["jumpBodyLengthsPerFrame"], reverse=True
    )
    return {
        "label": METHODS[method]["label"],
        "requiredLandmarks": list(METHODS[method]["landmarks"]),
        "reliableReferenceFrames": len(valid_lengths),
        "reliableReferenceFramePercentOf165": len(valid_lengths) / len(frames) * 100,
        "reliableConsecutiveLengthPairs": len(length_deltas),
        "referenceLengthPixels": summarize(length_values),
        "referenceLengthCoefficientOfVariationPercent": length_cv,
        "consecutiveReferenceLengthChangePixels": summarize(length_delta_pixels),
        "consecutiveReferenceLengthChangePercentOfPrevious": summarize(
            length_delta_percent
        ),
        "largestReferenceLengthChanges": largest_length_changes,
        "rightBackPawNormalizedPositionFrames": len(paw_positions),
        "consecutiveRightBackPawPairsChecked": sum(
            1
            for before, after in zip(frames, frames[1:])
            if before["methods"][method]["pawRelativeAvailable"]
            and after["methods"][method]["pawRelativeAvailable"]
        ),
        "rightBackPawJumpsAboveExisting0_35Cutoff": paw_jumps,
        "rightBackPawJumpsAboveCutoffIncludingLowConfidenceReferences": (
            all_paw_score_jumps
        ),
        "rightBackPawPairsWithScorePassingPawsChecked": len(
            all_paw_score_jump_candidates
        ),
        "largestRightBackPawJumps": largest_paw_jumps[:5],
        "largestRightBackPawJumpsIncludingLowConfidenceReferences": (
            all_paw_score_jump_candidates[:5]
        ),
    }


def paired_length_change_summary(
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    paired_changes: dict[str, list[float]] = {"A": [], "B": []}
    paired_percent_changes: dict[str, list[float]] = {"A": [], "B": []}
    pair_indices = []
    for before, after in zip(frames, frames[1:]):
        if not all(
            before["methods"][method]["referencePassesThreshold"]
            and after["methods"][method]["referencePassesThreshold"]
            for method in METHODS
        ):
            continue
        pair_indices.append([before["frameIndex"], after["frameIndex"]])
        for method in METHODS:
            first = before["methods"][method]["referenceLength"]
            second = after["methods"][method]["referenceLength"]
            paired_changes[method].append(abs(second - first))
            paired_percent_changes[method].append(abs(second - first) / first * 100)
    return {
        "consecutivePairsWhereBothMethodsPass": len(pair_indices),
        "framePairs": pair_indices,
        "absolutePixelChanges": {
            method: summarize(values) for method, values in paired_changes.items()
        },
        "percentChangesOfPreviousLength": {
            method: summarize(values)
            for method, values in paired_percent_changes.items()
        },
    }


def create_report(result: dict[str, Any]) -> str:
    summaries = result["methodSummaries"]
    lines = [
        "# Body-reference comparison experiment",
        "",
        "- Source predictions: `../full-video/rtdetr-rtmpose-full-video.json`.",
        "- Frames: 165; original predictions used unchanged; no interpolation.",
        "- Existing raw-score threshold: 0.80.",
        "- Reference availability requires the dog detection and every method landmark at or above 0.80.",
        "- Right-paw coordinates are normalized as `(paw - reference center) / reference length`; paw itself must score at least 0.80.",
        "- Paw jump warning uses the existing experimental cutoff of 0.35 reference lengths per frame.",
        "",
        "## Landmark-definition note",
        "",
        "AP-10K names Left Hip and Right Hip as paired animal-side landmarks. Its README notes that for digitigrade animals such as dogs, its `hip` label is used at the knee-level joint, not necessarily the anatomical pelvis. Method A is therefore reported as the project's current shoulder + AP-10K hip reference, not as a verified shoulder-to-pelvis measurement.",
        "",
        "## Summary",
        "",
        "| Measure | Method A: shoulders + AP-10K hips | Method B: neck + tail root |",
        "|---|---:|---:|",
        f"| Reference passes threshold | {summaries['A']['reliableReferenceFrames']}/165 ({summaries['A']['reliableReferenceFramePercentOf165']:.1f}%) | {summaries['B']['reliableReferenceFrames']}/165 ({summaries['B']['reliableReferenceFramePercentOf165']:.1f}%) |",
        f"| Paw-relative positions available (reference + paw pass) | {summaries['A']['rightBackPawNormalizedPositionFrames']}/165 | {summaries['B']['rightBackPawNormalizedPositionFrames']}/165 |",
        f"| Valid consecutive length comparisons | {summaries['A']['reliableConsecutiveLengthPairs']} | {summaries['B']['reliableConsecutiveLengthPairs']} |",
        f"| Median length change between valid neighbors | {summaries['A']['consecutiveReferenceLengthChangePixels']['median']:.2f} px ({summaries['A']['consecutiveReferenceLengthChangePercentOfPrevious']['median']:.2f}%) | {summaries['B']['consecutiveReferenceLengthChangePixels']['median']:.2f} px ({summaries['B']['consecutiveReferenceLengthChangePercentOfPrevious']['median']:.2f}%) |",
        f"| 95th-percentile length change | {summaries['A']['consecutiveReferenceLengthChangePercentOfPrevious']['p95']:.2f}% | {summaries['B']['consecutiveReferenceLengthChangePercentOfPrevious']['p95']:.2f}% |",
        f"| Length variation across valid frames (coefficient of variation) | {summaries['A']['referenceLengthCoefficientOfVariationPercent']:.2f}% | {summaries['B']['referenceLengthCoefficientOfVariationPercent']:.2f}% |",
        f"| Paw jumps > 0.35 on fully reliable adjacent pairs | {len(summaries['A']['rightBackPawJumpsAboveExisting0_35Cutoff'])} | {len(summaries['B']['rightBackPawJumpsAboveExisting0_35Cutoff'])} |",
        "",
        "Length changes are reported only for consecutive frames where both references pass the same confidence rule. The coefficient of variation measures total frame-to-frame size variation and can reflect real pose/view changes, not just model noise.",
        "",
        f"On the **{result['pairedLengthChangeSummary']['consecutivePairsWhereBothMethodsPass']} same adjacent frame pairs** where both references pass, median percentage length change is "
        f"{result['pairedLengthChangeSummary']['percentChangesOfPreviousLength']['A']['median']:.2f}% for A and "
        f"{result['pairedLengthChangeSummary']['percentChangesOfPreviousLength']['B']['median']:.2f}% for B.",
        "",
        "## Examples at the previously inspected frames",
        "",
        "| Frame | A reference center / length | A paw (x,y) | B reference center / length | B paw (x,y) |",
        "|---:|---|---|---|---|",
    ]
    for frame_index in (45, 55, 66, 77, 100):
        frame = result["frames"][frame_index]
        a = frame["methods"]["A"]
        b = frame["methods"]["B"]
        paw_a = a["normalizedRightBackPaw"]
        paw_b = b["normalizedRightBackPaw"]
        def ref_text(method: dict[str, Any]) -> str:
            if method["referenceLength"] is None:
                return "unavailable"
            return (
                f"({method['centerX']:.1f},{method['centerY']:.1f}) / "
                f"{method['referenceLength']:.1f}px"
            )
        def paw_text(position: dict[str, float] | None) -> str:
            return "unavailable" if position is None else f"({position['x']:.3f},{position['y']:.3f})"
        def validity(method: dict[str, Any]) -> str:
            return "pass" if method["referencePassesThreshold"] else "below threshold"
        def paw_with_validity(method: dict[str, Any]) -> str:
            return f"{paw_text(method['normalizedRightBackPaw'])} ({validity(method)})"
        lines.append(
            f"| {frame_index} | {ref_text(a)} ({validity(a)}) | "
            f"{paw_with_validity(a)} | {ref_text(b)} ({validity(b)}) | "
            f"{paw_with_validity(b)} |"
        )
    lines.extend(
        [
            "",
            "For comparison, normalized paw positions are shown even when a reference fails the 0.80 score check; those values are exploratory and not counted as usable.",
            "",
        ]
    )

    lines.extend(["", "## Largest observed changes", ""])
    for method in ("A", "B"):
        summary = summaries[method]
        lines.append(f"### Method {method}: {summary['label']}")
        lines.append("")
        if summary["largestReferenceLengthChanges"]:
            lines.append("Largest valid consecutive reference-length changes:")
            for change in summary["largestReferenceLengthChanges"][:3]:
                lines.append(
                    f"- Frames {change['fromFrame']}→{change['toFrame']}: "
                    f"{change['signedPixels']:+.2f}px "
                    f"({change['percentOfPrevious']:.1f}%)."
                )
        if summary["rightBackPawJumpsAboveExisting0_35Cutoff"]:
            lines.append("Right-hind-paw normalized jumps above 0.35:")
            for event in summary["rightBackPawJumpsAboveExisting0_35Cutoff"]:
                lines.append(
                    f"- Frames {event['fromFrame']}→{event['toFrame']}: "
                    f"{event['jumpBodyLengthsPerFrame']:.3f} reference lengths."
                )
        else:
            lines.append("No checked right-hind-paw pair exceeded 0.35 reference lengths.")
        unchecked_jumps = summary[
            "rightBackPawJumpsAboveCutoffIncludingLowConfidenceReferences"
        ]
        if unchecked_jumps:
            lines.append(
                "Across all dog-detected adjacent pairs with paw scores passing, "
                "including low-confidence references:"
            )
            for event in unchecked_jumps:
                status = (
                    "both references pass"
                    if event["fromReferencePassesThreshold"]
                    and event["toReferencePassesThreshold"]
                    else "at least one reference fails"
                )
                lines.append(
                    f"- Frames {event['fromFrame']}→{event['toFrame']}: "
                    f"{event['jumpBodyLengthsPerFrame']:.3f} lengths "
                    f"({status})."
                )
        lines.append("")
        largest_jumps = summary["largestRightBackPawJumps"]
        if largest_jumps:
            top = largest_jumps[0]
            lines.append(
                f"Largest checked paw movement: frames {top['fromFrame']}→{top['toFrame']}, "
                f"{top['jumpBodyLengthsPerFrame']:.3f} reference lengths."
            )
            lines.append("")
        all_jumps = summary[
            "largestRightBackPawJumpsIncludingLowConfidenceReferences"
        ]
        if all_jumps:
            top_raw = all_jumps[0]
            top_is_usable_max = bool(
                largest_jumps
                and top_raw["fromFrame"] == largest_jumps[0]["fromFrame"]
                and top_raw["toFrame"] == largest_jumps[0]["toFrame"]
            )
            if not top_is_usable_max:
                status = (
                    "both references pass"
                    if top_raw["fromReferencePassesThreshold"]
                    and top_raw["toReferencePassesThreshold"]
                    else "at least one reference fails"
                )
                lines.append(
                    f"Largest paw movement across all score-passing paw pairs: "
                    f"frames {top_raw['fromFrame']}→{top_raw['toFrame']}, "
                    f"{top_raw['jumpBodyLengthsPerFrame']:.3f} lengths "
                    f"({status})."
                )
                lines.append("")

    lines.extend(
        [
            "## Interpretation limits",
            "",
            "These calculations compare consistency of model-derived reference geometry, not anatomical accuracy. Stable lengths do not prove that the landmarks are correctly placed; confidence scores are not calibrated probabilities; and changes can reflect actual body pose, camera perspective, occlusion, or prediction noise. No manual ground-truth labels were used.",
            "",
            "Official landmark sources: [AP-10K keypoint definitions and FAQ](https://github.com/AlexTheBad/AP-10K#keypoint-definition) and [MMPose AP-10K keypoint mapping](https://github.com/open-mmlab/mmpose/blob/main/configs/_base_/datasets/ap10k.py).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    records = payload.get("frames")
    if not isinstance(records, list) or len(records) != 165:
        raise ValueError(f"Expected 165 frame records in {INPUT}.")
    frames = build_frame_data(records)
    result = {
        "experiment": "comparison of current shoulder+AP-10K-hip and neck+tail-root body references",
        "sourcePredictions": INPUT.relative_to(ROOT).as_posix(),
        "originalPredictionsModified": False,
        "confidenceThreshold": SCORE_THRESHOLD,
        "pawJumpCutoffReferenceLengthsPerFrame": PAW_JUMP_CUTOFF_BODY_LENGTHS,
        "interpolationUsed": False,
        "methodDefinitions": {
            "A": {
                "landmarks": list(METHODS["A"]["landmarks"]),
                "center": "midpoint of the left/right shoulder midpoint and left/right AP-10K hip midpoint",
                "length": "Euclidean distance between shoulder midpoint and AP-10K hip midpoint",
            },
            "B": {
                "landmarks": list(METHODS["B"]["landmarks"]),
                "center": "midpoint between neck and root of tail",
                "length": "Euclidean distance between neck and root of tail",
            },
        },
        "measurementRules": {
            "referencePasses": "Dog detection succeeded and all required method landmarks have raw scores >= 0.80.",
            "rightBackPawPosition": "Requires the method reference and right_back_paw raw score >= 0.80; normalized x/y are (paw-center)/reference length.",
            "consecutiveLengthPairs": "Both adjacent frames must have references passing the method's threshold.",
            "jumpCheck": "Consecutive normalized right-back-paw positions, both available, flagged above 0.35 reference lengths per frame.",
        },
        "ap10kDefinitionNote": "AP-10K README lists left/right hip as paired animal-side keypoints and notes that for digitigrade animals such as dogs, 'hip' is placed at the knee-level landmark; it is not necessarily the anatomical pelvis.",
        "manualGroundTruthUsed": False,
        "frameCount": len(frames),
        "methodSummaries": {
            method: method_summary(frames, method) for method in METHODS
        },
        "pairedLengthChangeSummary": paired_length_change_summary(frames),
        "frames": frames,
    }
    JSON_OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT_OUTPUT.write_text(create_report(result), encoding="utf-8")
    print(json.dumps(result["methodSummaries"], indent=2))
    print(f"\nJSON results: {JSON_OUTPUT}")
    print(f"Report: {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
