from __future__ import annotations

import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
VIDEO = ROOT / "tmp" / "4300700-sd_426_240_30fps.mp4"
FRAME_DIR = EXPERIMENT_DIR / "frames"
MARKS_FILE = EXPERIMENT_DIR / "manual-left-hip-marks.json"
FRAME_INDICES = (45, 55, 77, 100)
MAX_REQUEST_BYTES = 4096

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Manual left-hip marking</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; }
    body { max-width: 1100px; margin: 0 auto; padding: 1rem; color: #202124; }
    h1 { margin-bottom: .35rem; }
    .intro { margin-top: 0; color: #444; }
    #status { min-height: 1.5em; font-weight: 600; }
    #frames { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    article { border: 1px solid #bbb; border-radius: 8px; padding: .65rem; }
    article h2 { margin: 0 0 .45rem; font-size: 1.05rem; }
    .image-wrap { position: relative; }
    img { display: block; width: 100%; height: auto; cursor: crosshair; }
    .marker {
      display: none; position: absolute; width: 18px; height: 18px;
      border: 3px solid #e00000; border-radius: 50%; transform: translate(-50%, -50%);
      pointer-events: none; box-sizing: border-box;
    }
    .mark-info { min-height: 1.5em; margin: .4rem 0; font-size: .9rem; }
    button { padding: .45rem .7rem; cursor: pointer; }
    @media (max-width: 650px) {
      #frames { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <h1>Manual left-hip marking</h1>
  <p class="intro">Click the dog's left hip on each original frame. Your click is saved
  right away. Click again to correct it; the red circle shows your current mark.
  Coordinates are measured in original-image pixels. No model predictions are shown.</p>
  <p id="status" role="status">Loading frames…</p>
  <main id="frames"></main>
  <script>
    const root = document.getElementById("frames");
    const statusLine = document.getElementById("status");

    function showMark(entry, card) {
      const marker = card.querySelector(".marker");
      const info = card.querySelector(".mark-info");
      if (entry.manualX === null || entry.manualY === null) {
        marker.style.display = "none";
        info.textContent = "Not marked yet";
        return;
      }
      const image = card.querySelector("img");
      marker.style.left = `${entry.manualX / entry.imageWidth * image.clientWidth}px`;
      marker.style.top = `${entry.manualY / entry.imageHeight * image.clientHeight}px`;
      marker.style.display = "block";
      info.textContent = `Saved: x=${entry.manualX.toFixed(2)}, y=${entry.manualY.toFixed(2)} px`;
    }

    async function sendMark(frameIndex, values) {
      const response = await fetch("/api/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frameIndex, ...values })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save mark");
      return result.frame;
    }

    function addFrame(entry) {
      const card = document.createElement("article");
      const heading = document.createElement("h2");
      heading.textContent = `Frame ${entry.frameIndex}`;
      const wrap = document.createElement("div");
      wrap.className = "image-wrap";
      const image = document.createElement("img");
      image.src = `/frames/${entry.frameIndex}`;
      image.alt = `Original video frame ${entry.frameIndex}; click the dog's left hip`;
      image.draggable = false;
      const marker = document.createElement("span");
      marker.className = "marker";
      wrap.append(image, marker);
      const info = document.createElement("p");
      info.className = "mark-info";
      const clearButton = document.createElement("button");
      clearButton.type = "button";
      clearButton.textContent = "Clear mark";
      clearButton.addEventListener("click", async () => {
        try {
          const updated = await sendMark(entry.frameIndex, { clear: true });
          Object.assign(entry, updated);
          showMark(entry, card);
          statusLine.textContent = `Frame ${entry.frameIndex} mark cleared.`;
        } catch (error) {
          statusLine.textContent = error.message;
        }
      });
      image.addEventListener("click", async (event) => {
        const bounds = image.getBoundingClientRect();
        if (!bounds.width || !bounds.height) return;
        const x = Math.max(0, Math.min(
          entry.imageWidth,
          (event.clientX - bounds.left) * image.naturalWidth / bounds.width
        ));
        const y = Math.max(0, Math.min(
          entry.imageHeight,
          (event.clientY - bounds.top) * image.naturalHeight / bounds.height
        ));
        try {
          const updated = await sendMark(entry.frameIndex, {
            x: Math.round(x * 100) / 100,
            y: Math.round(y * 100) / 100
          });
          Object.assign(entry, updated);
          showMark(entry, card);
          statusLine.textContent = `Frame ${entry.frameIndex} mark saved.`;
        } catch (error) {
          statusLine.textContent = error.message;
        }
      });
      image.addEventListener("load", () => showMark(entry, card));
      window.addEventListener("resize", () => showMark(entry, card));
      card.append(heading, wrap, info, clearButton);
      root.append(card);
      showMark(entry, card);
    }

    fetch("/api/frames")
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load frames");
        data.frames.forEach(addFrame);
        statusLine.textContent = "Click the left hip in each of the four frames.";
      })
      .catch((error) => { statusLine.textContent = error.message; });
  </script>
</body>
</html>
"""


def load_marks() -> dict[str, Any]:
    if not MARKS_FILE.is_file():
        raise FileNotFoundError(
            f"Manual mark template is missing: {MARKS_FILE}. "
            "Run this script with --prepare first."
        )
    marks = json.loads(MARKS_FILE.read_text(encoding="utf-8"))
    indices = tuple(int(entry["frameIndex"]) for entry in marks.get("frames", []))
    if indices != FRAME_INDICES:
        raise ValueError(
            f"Expected manual-mark entries for frames {FRAME_INDICES}; got {indices}."
        )
    return marks


def save_marks(marks: dict[str, Any]) -> None:
    temporary = MARKS_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(marks, indent=2) + "\n", encoding="utf-8")
    temporary.replace(MARKS_FILE)


def extract_frames() -> dict[str, Any]:
    if not VIDEO.is_file():
        raise FileNotFoundError(f"Source video is missing: {VIDEO}")
    existing_entries = {}
    if MARKS_FILE.is_file():
        existing = json.loads(MARKS_FILE.read_text(encoding="utf-8"))
        existing_entries = {
            int(entry["frameIndex"]): entry for entry in existing.get("frames", [])
        }
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open source video: {VIDEO}")
    frame_entries = []
    try:
        for frame_index in FRAME_INDICES:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, image = capture.read()
            if not success:
                raise RuntimeError(f"Could not read video frame {frame_index}.")
            height, width = image.shape[:2]
            image_path = FRAME_DIR / f"frame-{frame_index:03d}.jpg"
            if not cv2.imwrite(str(image_path), image):
                raise RuntimeError(f"Could not save unannotated frame: {image_path}")
            old_entry = existing_entries.get(frame_index, {})
            frame_entries.append(
                {
                    "frameIndex": frame_index,
                    "image": image_path.relative_to(EXPERIMENT_DIR).as_posix(),
                    "imageWidth": width,
                    "imageHeight": height,
                    "manualX": old_entry.get("manualX"),
                    "manualY": old_entry.get("manualY"),
                }
            )
    finally:
        capture.release()

    template = {
        "description": (
            "Manual left-hip clicks only. Coordinates are in original-frame pixels "
            "with origin at the top-left. RTMPose predictions are stored separately."
        ),
        "sourceVideo": VIDEO.relative_to(ROOT).as_posix(),
        "frames": frame_entries,
    }
    save_marks(template)
    if existing_entries:
        preserved = sum(
            entry["manualX"] is not None and entry["manualY"] is not None
            for entry in frame_entries
        )
        print(f"Preserved {preserved} existing manual marks.")
    return template


def api_frames() -> bytes:
    marks = load_marks()
    public_frames = []
    for entry in marks["frames"]:
        public_frames.append(
            {
                "frameIndex": int(entry["frameIndex"]),
                "imageWidth": int(entry["imageWidth"]),
                "imageHeight": int(entry["imageHeight"]),
                "manualX": entry.get("manualX"),
                "manualY": entry.get("manualY"),
            }
        )
    return json.dumps({"frames": public_frames}).encode("utf-8")


def update_mark(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    frame_index = payload.get("frameIndex")
    if isinstance(frame_index, bool) or not isinstance(frame_index, int):
        raise ValueError("frameIndex must be an integer.")
    marks = load_marks()
    entry = next(
        (frame for frame in marks["frames"] if frame["frameIndex"] == frame_index),
        None,
    )
    if entry is None:
        raise ValueError("Unknown frame index.")
    if payload.get("clear") is True:
        entry["manualX"] = None
        entry["manualY"] = None
    else:
        x, y = payload.get("x"), payload.get("y")
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not math.isfinite(x)
            or not math.isfinite(y)
        ):
            raise ValueError("x and y must be finite numbers.")
        if not (0 <= x <= entry["imageWidth"] and 0 <= y <= entry["imageHeight"]):
            raise ValueError("Click coordinates are outside the original frame.")
        entry["manualX"] = round(float(x), 2)
        entry["manualY"] = round(float(y), 2)
    save_marks(marks)
    return entry


def make_handler() -> type[BaseHTTPRequestHandler]:
    class MarkingHandler(BaseHTTPRequestHandler):
        def respond(self, status_code: int, body: bytes, content_type: str) -> None:
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def respond_json(self, status_code: int, value: dict[str, Any]) -> None:
            self.respond(
                status_code,
                json.dumps(value).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.respond(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/frames":
                try:
                    self.respond(
                        200,
                        api_frames(),
                        "application/json; charset=utf-8",
                    )
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                    self.respond_json(500, {"error": str(error)})
                return
            if path.startswith("/frames/"):
                name = path.removeprefix("/frames/")
                allowed_names = {
                    f"frame-{frame_index:03d}" for frame_index in FRAME_INDICES
                }
                if name not in {str(frame_index) for frame_index in FRAME_INDICES}:
                    self.respond_json(404, {"error": "Frame not found."})
                    return
                frame_index = int(name)
                image_path = FRAME_DIR / f"frame-{frame_index:03d}.jpg"
                if image_path.stem not in allowed_names or not image_path.is_file():
                    self.respond_json(404, {"error": "Frame image is unavailable."})
                    return
                self.respond(
                    200,
                    image_path.read_bytes(),
                    "image/jpeg",
                )
                return
            self.respond_json(404, {"error": "Not found."})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/mark":
                self.respond_json(404, {"error": "Not found."})
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if not 0 < content_length <= MAX_REQUEST_BYTES:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(content_length))
                entry = update_mark(payload)
                public_entry = {
                    key: entry[key]
                    for key in (
                        "frameIndex",
                        "imageWidth",
                        "imageHeight",
                        "manualX",
                        "manualY",
                    )
                }
                self.respond_json(200, {"frame": public_entry})
            except (
                OSError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
            ) as error:
                self.respond_json(400, {"error": str(error)})

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[manual-marking] {self.address_string()} - {format % args}")

    return MarkingHandler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve a browser interface for manual left-hip marking."
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Extract the four original frames before starting the web server.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535.")
    if args.prepare or not MARKS_FILE.is_file():
        template = extract_frames()
        print(f"Prepared {len(template['frames'])} original frames.")
    else:
        load_marks()

    server = HTTPServer((args.host, args.port), make_handler())
    print(f"Manual marking page: http://localhost:{args.port}/", flush=True)
    print("Forward this port in the VS Code Ports panel to open it in your browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping manual marking server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
