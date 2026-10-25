from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "PetLens_Demo_Assets"
GRAPHS = ROOT / "PetLens_Validation_Graphs"
OUTPUT = ROOT / "PetLens_V6_Demo_30s.mp4"
THUMBNAIL = ROOT / "PetLens_V6_Demo_Thumbnail.jpg"
SOURCE_VIDEO = ASSETS / "PetLens-motion-api-demo-h264.mp4"
LOGO_PATH = ASSETS / "petlens-dog-mark.png"
METRICS_PATH = GRAPHS / "metrics.json"
WIDTH, HEIGHT, FPS, DURATION = 1920, 1080, 30, 30
FRAME_COUNT = FPS * DURATION

NAVY = "#091824"
PANEL = "#102635"
PANEL_ALT = "#142e3d"
EDGE = "#29495a"
WHITE = "#f3f7f8"
MUTED = "#a9bbc5"
TEAL = "#5bd3c1"
LIME = "#c8e96a"
AMBER = "#ffc27a"
RED = "#f17b7b"

FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        raise FileNotFoundError(f"Required Arial font is unavailable: {path}")
    return ImageFont.truetype(str(path), size=size)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int,
         color: str = WHITE, bold: bool = False, anchor: str | None = None) -> None:
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
            fill: str, outline: str | None = None, radius: int = 24,
            width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 9), fill=LIME)
    draw.ellipse((1450, -360, 2140, 330), fill="#0d2130")
    draw.ellipse((-400, 820, 270, 1490), fill="#0c202d")
    return image, ImageDraw.Draw(image)


def brand_header(image: Image.Image, draw: ImageDraw.ImageDraw, section: str) -> None:
    rounded(draw, (80, 53, 138, 111), "#ffffff", radius=15)
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo.thumbnail((48, 48), Image.Resampling.LANCZOS)
    image.paste(logo, (85, 58), logo)
    text(draw, (158, 65), "PETLENS", 23, WHITE, True)
    text(draw, (285, 67), "/", 21, MUTED, True)
    text(draw, (311, 69), section.upper(), 16, TEAL, True)
    draw.line((80, 132, 1840, 132), fill=EDGE, width=2)


def footer(draw: ImageDraw.ImageDraw, label: str) -> None:
    draw.line((80, 1004, 1840, 1004), fill=EDGE, width=2)
    text(draw, (82, 1022), label, 17, MUTED)
    text(draw, (1838, 1022), "PETLENS", 17, TEAL, True, anchor="ra")


def wrap(draw: ImageDraw.ImageDraw, value: str, max_width: int,
         face: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str,
              max_width: int, size: int = 22, color: str = MUTED,
              line_gap: int = 11) -> int:
    face = font(size)
    y = xy[1]
    for line in wrap(draw, value, max_width, face):
        draw.text((xy[0], y), line, font=face, fill=color)
        y += size + line_gap
    return y


def badge(draw: ImageDraw.ImageDraw, x: int, y: int, label: str,
          fill: str = "#173e49", color: str = TEAL) -> None:
    face = font(17, True)
    w = draw.textbbox((0, 0), label, font=face)[2] + 30
    rounded(draw, (x, y, x + w, y + 38), fill, radius=17)
    draw.text((x + 15, y + 8), label, font=face, fill=color)


def load_source() -> cv2.VideoCapture:
    if not SOURCE_VIDEO.is_file():
        raise FileNotFoundError(f"Missing genuine source demo: {SOURCE_VIDEO}")
    source = cv2.VideoCapture(str(SOURCE_VIDEO))
    if not source.isOpened():
        raise RuntimeError(f"Could not open source demo: {SOURCE_VIDEO}")
    return source


def research_frame(source: cv2.VideoCapture, seconds: float) -> Image.Image:
    source.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, bgr = source.read()
    if not ok or bgr is None:
        raise RuntimeError(f"Could not read source video at {seconds:.2f}s")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # This crop isolates the genuine research clip from its old title-card layout.
    crop = rgb[365:735, 34:686]
    if crop.size == 0:
        raise RuntimeError("Research-footage crop was empty")
    return Image.fromarray(crop)


def put_graph(image: Image.Image, filename: str, box: tuple[int, int, int, int]) -> None:
    path = GRAPHS / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing validation graph: {path}")
    x1, y1, x2, y2 = box
    graph = Image.open(path).convert("RGB")
    graph.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    x = x1 + ((x2 - x1) - graph.width) // 2
    y = y1 + ((y2 - y1) - graph.height) // 2
    image.paste(graph, (x, y))


def build_metrics() -> dict:
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    model = metrics["pck_at_0_1"]["model"]
    baseline = metrics["pck_at_0_1"]["box_center_baseline"]
    if model["correct"] != 470 or model["visible_keypoints"] != 1104:
        raise ValueError("Current validation metrics differ from the expected reviewed report.")
    if baseline["correct"] != 41 or baseline["visible_keypoints"] != 1104:
        raise ValueError("Current box-center baseline differs from the reviewed report.")
    if metrics["evaluation_protocol"]["independent"] is not False:
        raise ValueError("Expected development-only, non-independent validation data.")
    if metrics["dataset"]["instances"] != 110:
        raise ValueError("Unexpected validation-set instance count.")
    return metrics


def render_scene(name: str, source: cv2.VideoCapture, metrics: dict,
                 source_seconds: float = 0.0) -> Image.Image:
    model = metrics["pck_at_0_1"]["model"]
    baseline = metrics["pck_at_0_1"]["box_center_baseline"]
    model_pct = 100 * model["overall"]
    baseline_pct = 100 * baseline["overall"]

    image, draw = make_canvas()
    if name == "intro":
        brand_header(image, draw, "Canine movement project")
        rounded(draw, (1040, 202, 1780, 922), "#ffffff", radius=44)
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((650, 690), Image.Resampling.LANCZOS)
        image.paste(logo, (1084 + (650-logo.width)//2, 215 + (690-logo.height)//2), logo)
        badge(draw, 110, 247, "CONGRESSIONAL APP CHALLENGE", fill="#183a39", color=LIME)
        text(draw, (112, 347), "PetLens", 92, WHITE, True)
        text(draw, (116, 465), "AI-assisted canine", 39, TEAL, True)
        text(draw, (116, 516), "movement analysis", 39, TEAL, True)
        paragraph(draw, (116, 621), "A real API workflow, an experimental pose study, and a clear line between them.", 760, 25)
        text(draw, (116, 858), "Version 6 reference build", 20, MUTED, True)
        footer(draw, "30-second project demonstration")
    elif name == "clip":
        brand_header(image, draw, "Genuine source clip • API workflow")
        text(draw, (82, 163), "A real walking clip enters the workflow", 40, WHITE, True)
        text(draw, (83, 218), "Research footage shown as supplied; no landmarks are overlaid.", 22, MUTED)
        rounded(draw, (80, 288, 1280, 964), "#ffffff", radius=24)
        footage = research_frame(source, source_seconds)
        footage = ImageOps.fit(footage, (1160, 652), method=Image.Resampling.LANCZOS)
        image.paste(footage, (100, 300))
        rounded(draw, (1320, 288, 1840, 964), PANEL, EDGE, 24, 2)
        badge(draw, 1350, 326, "SOURCE CLIP", fill="#25394a", color=AMBER)
        text(draw, (1350, 400), "DMD research", 29, WHITE, True)
        text(draw, (1350, 440), "video", 29, WHITE, True)
        paragraph(draw, (1350, 515), "This is not a canine osteoarthritis or gait-validation dataset.", 440, 21)
        draw.line((1350, 663, 1808, 663), fill=EDGE, width=2)
        text(draw, (1350, 698), "Shin et al. • PLOS ONE", 19, MUTED, True)
        text(draw, (1350, 736), "2013 • DOI 10.1371/", 18, MUTED)
        text(draw, (1350, 767), "journal.pone.0059875", 18, MUTED)
        footer(draw, "Actual research clip used for the live API demonstration")
    elif name == "api":
        brand_header(image, draw, "Production API • motion-only")
        text(draw, (82, 166), "What the live API actually measured", 42, WHITE, True)
        text(draw, (83, 225), "Results from the real /api/analyze response for this source clip", 23, MUTED)
        cards = [
            ("PIPELINE", "OpenCV whole-picture motion", TEAL),
            ("DECODED FRAMES", "60", LIME),
            ("MOTION-TRACE POINTS", "59", LIME),
            ("STRIDE SYMMETRY", "Not measured", AMBER),
        ]
        positions = [(82, 320), (1002, 320), (82, 576), (1002, 576)]
        for (label, value, color), (x, y) in zip(cards, positions):
            rounded(draw, (x, y, x + 836, y + 218), PANEL, EDGE, 25, 2)
            text(draw, (x + 35, y + 30), label, 18, MUTED, True)
            paragraph(draw, (x + 35, y + 94), value, 760, 30, color)
        rounded(draw, (82, 835, 1838, 964), "#182d36", radius=22)
        text(draw, (116, 865), "Whole-frame motion is not a leg trajectory, gait score, or diagnosis.", 24, WHITE, True)
        footer(draw, "Genuine production API response • no simulated app result")
    elif name == "experiment":
        brand_header(image, draw, "Separate experiment • not app inference")
        badge(draw, 82, 173, "EXPERIMENTAL DEVELOPMENT VALIDATION", fill="#42352b", color=AMBER)
        text(draw, (82, 252), "A separate still-image pose study", 45, WHITE, True)
        text(draw, (84, 329), "AP-10K dog-only validation split", 29, TEAL, True)
        stats = [("110", "dog instances"), ("17", "landmark types"), ("1,104", "visible keypoints")]
        x = 84
        for value, label in stats:
            rounded(draw, (x, 430, x + 500, 600), PANEL, EDGE, 26, 2)
            text(draw, (x + 30, 456), value, 50, LIME, True)
            text(draw, (x + 32, 530), label, 23, MUTED)
            x += 565
        rounded(draw, (84, 662, 1836, 895), "#302d27", "#5e4b37", 26, 2)
        text(draw, (120, 697), "Important scope", 24, AMBER, True)
        paragraph(draw, (120, 749), "Ground-truth dog boxes were supplied. This validation split selected the checkpoint; it is development evidence, not independent testing. The pose model is not the production app inference system.", 1640, 24, WHITE)
        footer(draw, "Still-image localization only • no walking-video or gait validation")
    elif name == "overall":
        brand_header(image, draw, "Experimental validation • overall PCK@0.1")
        text(draw, (82, 158), "The model clears a simple baseline on this split", 39, WHITE, True)
        rounded(draw, (105, 224, 1815, 915), "#ffffff", radius=18)
        put_graph(image, "01-validation-vs-baseline.png", (125, 244, 1795, 895))
        rounded(draw, (82, 920, 1838, 986), "#302d27", "#5e4b37", 18, 2)
        text(draw, (108, 941), f"Development validation • {model['correct']}/{model['visible_keypoints']} vs {baseline['correct']}/{baseline['visible_keypoints']} • ground-truth boxes", 20, AMBER, True)
        footer(draw, "Not an independent test • not end-to-end video accuracy")
    elif name == "keypoints":
        brand_header(image, draw, "Experimental validation • by keypoint")
        text(draw, (82, 158), "PCK@0.1 across 17 AP-10K landmarks", 39, WHITE, True)
        rounded(draw, (90, 224, 1390, 952), "#ffffff", radius=16)
        put_graph(image, "03-per-keypoint-pck.png", (102, 236, 1378, 940))
        rounded(draw, (1420, 224, 1838, 952), PANEL, EDGE, 20, 2)
        badge(draw, 1450, 260, "110 DOG INSTANCES", fill="#183a39", color=LIME)
        text(draw, (1450, 345), f"{model_pct:.1f}%", 58, TEAL, True)
        paragraph(draw, (1452, 420), "overall PCK@0.1", 330, 22, WHITE)
        draw.line((1450, 498, 1808, 498), fill=EDGE, width=2)
        paragraph(draw, (1450, 536), "PCK counts visible landmarks localized within 0.1 of the box-size normalizer.", 340, 22)
        paragraph(draw, (1450, 720), "Every bar is validation-only. The tail-root result remains low.", 340, 21, AMBER)
        footer(draw, "PetLens pose model vs. oracle box-center baseline")
    elif name == "scores":
        brand_header(image, draw, "Experimental validation • prediction scores")
        text(draw, (82, 158), "Model output strength is not calibrated confidence", 39, WHITE, True)
        rounded(draw, (100, 223, 1820, 862), "#ffffff", radius=18)
        put_graph(image, "06-confidence-distribution.png", (120, 242, 1800, 842))
        rounded(draw, (100, 881, 1820, 978), "#302d27", "#5e4b37", 18, 2)
        text(draw, (130, 914), "Peak heatmap scores are uncalibrated — not probabilities that a landmark is correct.", 23, AMBER, True)
        footer(draw, "AP-10K still-image validation • experimental model")
    elif name == "close":
        brand_header(image, draw, "What comes next")
        text(draw, (104, 252), "From movement video", 58, WHITE, True)
        text(draw, (104, 329), "to measurable insights.", 58, TEAL, True)
        paragraph(draw, (108, 464), "PetLens is being developed toward canine movement analysis. Real-world video tracking, gait validation, and independent testing remain necessary.", 980, 29, MUTED, 15)
        rounded(draw, (1100, 245, 1785, 850), "#ffffff", radius=38)
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((610, 545), Image.Resampling.LANCZOS)
        image.paste(logo, (1138 + (610-logo.width)//2, 273 + (545-logo.height)//2), logo)
        badge(draw, 108, 788, "EXPERIMENTAL • DEVELOPMENT VALIDATION", fill="#42352b", color=AMBER)
        footer(draw, "PetLens • more real-world validation ahead")
    else:
        raise ValueError(f"Unknown scene: {name}")
    return image


SCENES = [
    (0, 3, "intro"),
    (3, 9, "clip"),
    (9, 14, "api"),
    (14, 17, "experiment"),
    (17, 21, "overall"),
    (21, 24, "keypoints"),
    (24, 27, "scores"),
    (27, 30, "close"),
]


def render() -> None:
    metrics = build_metrics()
    ffmpeg = Path(__import__("imageio_ffmpeg").get_ffmpeg_exe())
    if not ffmpeg.is_file():
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    source = load_source()
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s:v", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-frames:v", str(FRAME_COUNT), "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(OUTPUT),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    scene_cards: dict[str, Image.Image] = {}
    try:
        for name in dict.fromkeys(scene[2] for scene in SCENES):
            scene_cards[name] = render_scene(name, source, metrics, 5.0)
            scene_cards[name].save(ASSETS / f"card-{name}.png", optimize=True)
        scene_cards["intro"].save(THUMBNAIL, quality=94)

        assert process.stdin is not None
        for frame_index in range(FRAME_COUNT):
            seconds = frame_index / FPS
            scene = next(scene for scene in SCENES if scene[0] <= seconds < scene[1])
            if scene[2] == "clip":
                frame = render_scene("clip", source, metrics, seconds + 1.0)
            else:
                frame = scene_cards[scene[2]]
            process.stdin.write(frame.tobytes())
            if frame_index % FPS == 0:
                print(f"Rendered {seconds:05.1f}s / {DURATION}s", flush=True)
        process.stdin.close()
        stderr = process.stderr.read() if process.stderr else b""
        exit_code = process.wait()
        if exit_code:
            raise RuntimeError(f"FFmpeg failed ({exit_code}): {stderr.decode(errors='replace')}")
    finally:
        source.release()
        if process.poll() is None:
            process.kill()
            process.wait()
    print(f"Created {OUTPUT}")
    print(f"Created {THUMBNAIL}")


if __name__ == "__main__":
    try:
        render()
    except Exception as exc:
        print(f"Demo render failed: {exc}", file=sys.stderr)
        raise
