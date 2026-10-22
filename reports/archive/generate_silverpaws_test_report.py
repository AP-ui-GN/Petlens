#!/usr/bin/env python3
"""Create a plain-language PDF from standalone SilverPaws test outputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


MOSS = colors.HexColor("#164E4A")
MOSS_DARK = colors.HexColor("#103C39")
PEACH = colors.HexColor("#E88B73")
PEACH_LIGHT = colors.HexColor("#FBE5DC")
OAT = colors.HexColor("#F7F4EE")
SAGE = colors.HexColor("#E6F0E7")
TEXT = colors.HexColor("#203B3A")
MUTED = colors.HexColor("#637573")
LINE = colors.HexColor("#D8E0DA")
AMBER = colors.HexColor("#C87932")


@dataclass(frozen=True)
class TestCase:
    title: str
    source: str
    license: str
    source_url: str | None
    frames: int
    fps: float
    mean_confidence: float
    left_valid: int
    right_valid: int
    score: float | None
    asymmetry: float | None
    interpretation: str
    status: str


class HorizontalRule(Flowable):
    def __init__(self, width: float, color: colors.Color = LINE, thickness: float = 0.8):
        super().__init__()
        self.width = width
        self.height = thickness + 8
        self.color = color
        self.thickness = thickness

    def draw(self) -> None:
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 4, self.width, 4)


def load_test(path: Path, title: str, source: str, license_name: str, source_url: str | None, interpretation: str, status: str) -> TestCase:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    metrics = data["metrics"]
    keypoints = data["keypoints"]
    confidences = [point[2] for frame in keypoints for point in frame]

    return TestCase(
        title=title,
        source=source,
        license=license_name,
        source_url=source_url,
        frames=metrics["frame_count"],
        fps=float(data["fps"]),
        mean_confidence=float(sum(confidences) / len(confidences)),
        left_valid=int(metrics["valid_left_ankle_frames"]),
        right_valid=int(metrics["valid_right_ankle_frames"]),
        score=metrics["stride_symmetry_score"],
        asymmetry=metrics["asymmetry_percent"],
        interpretation=interpretation,
        status=status,
    )


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=32,
            textColor=MOSS_DARK,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "HeadingOne",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=MOSS_DARK,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "HeadingTwo",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=MOSS_DARK,
            spaceBefore=9,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=TEXT,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=MOSS_DARK,
            spaceAfter=2,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
    }


def callout(text: str, style: ParagraphStyle, background: colors.Color = SAGE) -> Table:
    table = Table([[Paragraph(text, style)]], colWidths=[6.65 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def metric_bar(label: str, value: float | None, styles: dict[str, ParagraphStyle], note: str) -> Table:
    value_text = "Unavailable" if value is None else f"{value:.1f}%"
    fill = 0 if value is None else max(0.0, min(100.0, value))
    bar_width = 4.1 * inch
    filled_width = bar_width * fill / 100
    bar = Table(
        [["", ""]],
        colWidths=[max(filled_width, 0.01), max(bar_width - filled_width, 0.01)],
        rowHeights=[0.12 * inch],
    )
    bar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PEACH if value is not None else LINE),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E9E7E1")),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    content = [
        [
            Paragraph(f"<b>{label}</b>", styles["body"]),
            Paragraph(f"<b>{value_text}</b>", styles["body"]),
        ],
        [bar, ""],
        [Paragraph(note, styles["small"]), ""],
    ]
    table = Table(content, colWidths=[bar_width, 1.55 * inch])
    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("SPAN", (0, 1), (1, 1)),
                ("SPAN", (0, 2), (1, 2)),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def build_report(output: Path, tests: list[TestCase]) -> None:
    styles = make_styles()
    document = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="SilverPaws AI Internet Video Test Report",
        author="SilverPaws AI",
    )

    usable_width = 7.2 * inch
    story: list[Any] = []
    story.extend(
        [
            Paragraph("SilverPaws AI", styles["title"]),
            Paragraph("Internet video test report", styles["subtitle"]),
            Paragraph(
                "A clear, constructive review of what the first MoveNet Thunder tests can tell us today.",
                styles["subtitle"],
            ),
            Spacer(1, 0.14 * inch),
            callout(
                "Bottom line: the pipeline runs successfully, but the model is not yet reliable enough to make pet-specific gait claims from every video. One clip produced no usable ankle signal; the other produced a strong symmetry score, but the model may have been following a nearby human.",
                styles["callout"],
                PEACH_LIGHT,
            ),
            Spacer(1, 0.12 * inch),
            Paragraph("What was tested", styles["h1"]),
            Paragraph(
                "Two publicly available dog videos were downloaded temporarily and analyzed outside the beta web app. Each test used the same MoveNet Thunder model, the same 0.20 confidence threshold, and the same first 120 frames so the comparison is fair.",
                styles["body"],
            ),
        ]
    )

    summary_rows = [
        [
            Paragraph("<b>Test</b>", styles["body"]),
            Paragraph("<b>Confident ankle frames</b>", styles["body"]),
            Paragraph("<b>Symmetry</b>", styles["body"]),
            Paragraph("<b>Meaning</b>", styles["body"]),
        ]
    ]
    for test in tests:
        valid = f"{test.left_valid} left / {test.right_valid} right"
        score = "Unavailable" if test.score is None else f"{test.score * 100:.1f}/100"
        summary_rows.append(
            [
                Paragraph(test.title, styles["body"]),
                Paragraph(valid, styles["body"]),
                Paragraph(score, styles["body"]),
                Paragraph(test.status, styles["body"]),
            ]
        )
    summary = Table(summary_rows, colWidths=[1.8 * inch, 1.45 * inch, 0.95 * inch, 2.45 * inch])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), MOSS),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), OAT),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([summary, Spacer(1, 0.12 * inch)])

    story.append(Paragraph("Test 1: dog and human walking clip", styles["h1"]))
    story.append(Paragraph("Raw measurements", styles["h2"]))
    story.append(
        Paragraph(
            f"<b>Measurement:</b> {tests[0].frames} frames at {tests[0].fps:.0f} frames per second. "
            f"Average confidence across all keypoints was {tests[0].mean_confidence:.3f}. "
            "Neither ankle reached the confidence threshold in any frame.",
            styles["body"],
        )
    )
    story.append(metric_bar("Stride symmetry score", tests[0].score, styles, "No score was reported because there was not enough confident ankle data."))
    story.append(Paragraph("Interpretation", styles["h2"]))
    story.append(
        callout(
            "<b>Constructive reading:</b> this is a useful failure, not a bad result. The validator correctly refused to turn weak detections into a confident number. The next improvement is subject selection: the clip contains both dogs and people, so a single-person model has an ambiguous target.",
            styles["callout"],
            SAGE,
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("Test 2: trained dogs hurdle clip", styles["h1"]))
    story.append(Paragraph("Raw measurements", styles["h2"]))
    story.append(
        Paragraph(
            f"<b>Measurement:</b> {tests[1].frames} frames at {tests[1].fps:.0f} frames per second. "
            f"Average confidence across all keypoints was {tests[1].mean_confidence:.3f}. "
            f"The left ankle was confident in {tests[1].left_valid} frames and the right ankle in {tests[1].right_valid} frames.",
            styles["body"],
        )
    )
    story.append(metric_bar("Stride symmetry score", tests[1].score * 100 if tests[1].score is not None else None, styles, "This is a motion-similarity measurement, not a diagnosis."))
    story.append(metric_bar("Estimated asymmetry", tests[1].asymmetry, styles, "Lower is more similar within this clip."))
    story.append(Paragraph("Interpretation", styles["h2"]))
    story.append(
        callout(
            "<b>Constructive reading:</b> the pipeline can produce a stable, explainable number when the detections are strong. However, the result is not proof that the dog was tracked: MoveNet Thunder is trained on human pose, and the historical clip includes people. Treat this as a pipeline success and a model-validation warning at the same time.",
            styles["callout"],
            PEACH_LIGHT,
        )
    )

    story.append(Paragraph("How the number is calculated", styles["h1"]))
    story.append(
        Paragraph(
            "For each frame, the validator reads the normalized vertical position of the detected left and right ankle. It adds the frame-to-frame movement for each side, then compares the two totals:",
            styles["body"],
        )
    )
    formula = Table(
        [[Paragraph("<b>symmetry = 1 - |left motion - right motion| / (left motion + right motion)</b>", styles["center"])]],
        colWidths=[usable_width],
    )
    formula.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), OAT),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend(
        [
            formula,
            Spacer(1, 0.08 * inch),
            Paragraph(
                "A score near 1.0 means the two detected sides moved similarly in that clip. It does not identify the cause of a movement pattern, and it cannot say whether a pet is healthy or injured.",
                styles["body"],
            ),
            Paragraph("What to do next", styles["h1"]),
            Paragraph(
                "<b>1. Use pet-specific pose detection.</b> Replace or supplement MoveNet Thunder with a model trained on dogs and cats, or add a subject-detection and cropping step before pose estimation.",
                styles["body"],
            ),
            Paragraph(
                "<b>2. Build a small labeled test set.</b> Collect at least 20 to 30 short clips with different breeds, camera angles, lighting, and walking surfaces. Mark whether the intended pet is actually detected.",
                styles["body"],
            ),
            Paragraph(
                "<b>3. Keep rejecting weak input.</b> The current validator already handles this correctly: if there are not enough confident ankle frames, it reports the metric as unavailable instead of inventing a reassuring score.",
                styles["body"],
            ),
            Paragraph(
                "<b>4. Compare a pet with itself.</b> For a useful wellness trend, repeat recordings with the same camera position and compare a pet's current observations with its own baseline.",
                styles["body"],
            ),
            Paragraph(
                "<b>5. Keep the language observational.</b> Say “the detected motion was less symmetric in this clip,” not “your pet has arthritis.” A veterinarian should interpret concerning changes.",
                styles["body"],
            ),
        ]
    )

    story.append(PageBreak())
    story.append(Paragraph("Sources and limitations", styles["h1"]))
    for test in tests:
        story.append(
            KeepTogether(
                [
                    Paragraph(f"<b>{test.title}</b>", styles["h2"]),
                    Paragraph(f"Source: {test.source}", styles["body"]),
                    Paragraph(f"License: {test.license}", styles["body"]),
                    Paragraph(f"Link: {test.source_url}" if test.source_url else "Link: Not provided", styles["small"]),
                ]
            )
        )
    story.extend(
        [
            Paragraph("Important limitations", styles["h2"]),
            Paragraph(
                "This report evaluates an engineering prototype. MoveNet Thunder is a pretrained human-pose model, not a validated veterinary or animal-pose model. Public videos may include people, occlusion, unusual camera angles, and uncontrolled motion. The score is not a medical diagnosis, emergency assessment, or substitute for a veterinarian.",
                styles["body"],
            ),
            callout(
                "If a pet shows pain, sudden weakness, collapse, breathing trouble, or another urgent change, contact a qualified veterinarian or emergency clinic directly. Do not wait for an app result.",
                styles["callout"],
                PEACH_LIGHT,
            ),
            Spacer(1, 0.18 * inch),
            Paragraph(
                "SilverPaws AI beta | Experimental educational software | Generated from standalone internet-video tests",
                styles["center"],
            ),
        ]
    )

    def draw_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(MOSS)
        canvas.rect(0, letter[1] - 0.16 * inch, letter[0], 0.16 * inch, stroke=0, fill=1)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(letter[0] - 0.65 * inch, 0.35 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a SilverPaws internet-video test report.")
    parser.add_argument("first_json", type=Path)
    parser.add_argument("second_json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/silverpaws-internet-video-test-report.pdf"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tests = [
        load_test(
            args.first_json,
            "Test 1: dog + human walking",
            "Wikimedia Commons file: Interspecific behavioural synchronization",
            "CC BY 4.0 (Duranton, Bedossa, Gaunet)",
            "https://commons.wikimedia.org/wiki/File:Interspecific-behavioural-synchronization-dogs-exhibit-locomotor-synchrony-with-humans-41598_2017_12577_MOESM2_ESM.ogv",
            "The model did not produce enough confident ankle detections to support a symmetry score.",
            "No usable gait signal",
        ),
        load_test(
            args.second_json,
            "Test 2: trained dogs hurdle clip",
            "Wikimedia Commons file: Hurdle Jumping by Trained Dogs (1899)",
            "Public domain historical film",
            "https://commons.wikimedia.org/wiki/File:Hurdle_Jumping_by_Trained_Dogs_-_1899_-_American_Mutoscope_and_Biograph_(US)_-_EYE_FLM75062_-_OB_685436.ogv",
            "The model produced a strong symmetry score, but the detected subject may be a nearby human rather than the dog.",
            "Strong signal, needs subject validation",
        ),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_report(args.output, tests)
    print(f"Created {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())