#!/usr/bin/env python3
"""Analyze one movement clip and print the result as JSON.

This is the process boundary between the API server and the analysis code. The
server spawns it per upload, so the contract is deliberately simple: one JSON
object out, and an exit code the server can map to an HTTP status.

Exit codes:
    0  analysis finished, JSON contains the result
    2  the clip itself was the problem (missing, unreadable, not a video)
    1  the pipeline failed for another reason

Example:
    python scripts/analyze_clip.py tmp/walk.mp4 --pet-name Mabel
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure movement in a pet walking clip and score wellness factors."
    )
    parser.add_argument("video", type=Path, help="Path to an MP4/MOV/WebM clip.")
    parser.add_argument(
        "--pet-name",
        default=None,
        help="Name used to address the pet in the observation text.",
    )
    parser.add_argument(
        "--previous-overall",
        type=float,
        default=None,
        help="Overall score of the previous saved walk, for the trend sentence.",
    )
    parser.add_argument(
        "--previous-pipeline",
        default=None,
        help="Pipeline that produced --previous-overall. Trends need a match.",
    )
    parser.add_argument(
        "--no-pose",
        action="store_true",
        help="Skip pose detection and measure picture motion only.",
    )
    parser.add_argument(
        "--request-id",
        default=None,
        help="Correlation ID supplied by the API for cross-process diagnostics.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Also write the JSON result to this path.",
    )
    parser.add_argument(
        "--debug-video",
        type=Path,
        default=None,
        help="Write a skeleton video for local inspection. The API never does this.",
    )
    return parser.parse_args()


def attach_request_id(result: dict, request_id: str | None) -> dict:
    """Attach the API correlation ID without changing measurement fields."""

    if not request_id:
        return result
    if result.get("ok") is True:
        diagnostics = result.get("diagnostics")
        if not isinstance(diagnostics, dict):
            diagnostics = {}
            result["diagnostics"] = diagnostics
        diagnostics["requestId"] = request_id
    else:
        result["requestId"] = request_id
    return result


def write_json(path: Path, result: dict) -> None:
    """Replace the output file only after the JSON is fully written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(result) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()

    # Imported here so --help works without OpenCV installed.
    from gait_engine.pipeline import analyze_clip

    motion_ready = None
    if args.output_json is not None and not args.no_pose:
        output_path = args.output_json

        def motion_ready(result: dict, destination: Path = output_path) -> None:
            write_json(destination, attach_request_id(result, args.request_id))

    try:
        result = analyze_clip(
            args.video,
            pet_name=args.pet_name,
            previous_overall=args.previous_overall,
            previous_pipeline=args.previous_pipeline,
            use_pose=not args.no_pose,
            motion_ready=motion_ready,
        )
        exit_code = 0
    except (FileNotFoundError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
        exit_code = 2
    except Exception as exc:  # noqa: BLE001 - always answer with JSON
        result = {
            "ok": False,
            "error": f"The analysis pipeline failed: {type(exc).__name__}: {exc}",
        }
        exit_code = 1

    result = attach_request_id(result, args.request_id)

    if args.debug_video and exit_code == 0:
        from gait_engine.debug_video import write_debug_video

        write_debug_video(args.video, args.debug_video)
    payload = json.dumps(result)
    if args.output_json:
        write_json(args.output_json, result)
    print(payload)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
