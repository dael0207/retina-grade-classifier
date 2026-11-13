"""Shared Korean PDF design primitives for both coursework reports."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# ruff: noqa: EM101, EM102, PLR2004, TRY003

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    HRFlowable,
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

INK: Final = colors.HexColor("#19352E")
TEAL: Final = colors.HexColor("#087F72")
MINT: Final = colors.HexColor("#DDF1EA")
CREAM: Final = colors.HexColor("#F7F2E8")
GRAY: Final = colors.HexColor("#5F6E69")
WHITE: Final = colors.white
CONTENT_WIDTH: Final = 172 * mm


class ReportLayoutError(RuntimeError):
    """A required layout asset or shape is invalid."""


def register_fonts() -> None:
    """Register the Windows Korean fonts embedded in final PDFs."""
    regular = Path("C:/Windows/Fonts/malgun.ttf")
    bold = Path("C:/Windows/Fonts/malgunbd.ttf")
    if not regular.exists() or not bold.exists():
        message = "Malgun Gothic font files are required for Korean PDF output"
        raise ReportLayoutError(message)
    register_font: Callable[[TTFont], None] = pdfmetrics.registerFont
    register_font(TTFont("Malgun", regular))
    register_font(TTFont("Malgun-Bold", bold))


def styles() -> dict[str, ParagraphStyle]:
    """Return a compact editorial style system."""
    register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleKo",
            parent=base["Title"],
            fontName="Malgun-Bold",
            fontSize=26,
            leading=34,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8 * mm,
        ),
        "kicker": ParagraphStyle(
            "KickerKo",
            parent=base["Normal"],
            fontName="Malgun-Bold",
            fontSize=9,
            leading=13,
            textColor=TEAL,
            spaceAfter=3 * mm,
        ),
        "h1": ParagraphStyle(
            "H1Ko",
            parent=base["Heading1"],
            fontName="Malgun-Bold",
            fontSize=18,
            leading=24,
            textColor=INK,
            spaceBefore=2 * mm,
            spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "H2Ko",
            parent=base["Heading2"],
            fontName="Malgun-Bold",
            fontSize=12,
            leading=18,
            textColor=TEAL,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyKo",
            parent=base["BodyText"],
            fontName="Malgun",
            fontSize=9.2,
            leading=15,
            textColor=INK,
            spaceAfter=3 * mm,
        ),
        "small": ParagraphStyle(
            "SmallKo",
            parent=base["BodyText"],
            fontName="Malgun",
            fontSize=7.5,
            leading=11,
            textColor=GRAY,
            spaceAfter=2 * mm,
        ),
        "metric": ParagraphStyle(
            "MetricKo",
            parent=base["Normal"],
            fontName="Malgun-Bold",
            fontSize=18,
            leading=22,
            textColor=TEAL,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabelKo",
            parent=base["Normal"],
            fontName="Malgun",
            fontSize=7.5,
            leading=11,
            textColor=GRAY,
            alignment=TA_CENTER,
        ),
        "caption": ParagraphStyle(
            "CaptionKo",
            parent=base["Normal"],
            fontName="Malgun",
            fontSize=7.5,
            leading=11,
            textColor=GRAY,
            alignment=TA_CENTER,
            spaceBefore=2 * mm,
        ),
    }


def percentage(value: float) -> str:
    """Format a fractional metric as a percentage."""
    return f"{value * 100:.2f}%"


def page_header_footer(canvas: Canvas, document: BaseDocTemplate) -> None:
    """Draw stable page furniture without entering the flow layout."""
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, fill=1, stroke=0)
    canvas.setFont("Malgun", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(19 * mm, 12 * mm, "당뇨망막병증 데이터 활용 과제")
    canvas.drawRightString(191 * mm, 12 * mm, f"{document.page}")
    canvas.restoreState()


def metric_cards(items: Sequence[tuple[str, str]], style: dict[str, ParagraphStyle]) -> Table:
    """Build one row of high-signal metric cards."""
    cells = [
        [Paragraph(value, style["metric"]), Paragraph(label, style["metric_label"])]
        for value, label in items
    ]
    table = Table([cells], colWidths=[CONTENT_WIDTH / len(cells)] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), MINT),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#AFCFC5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    return table


def data_table(rows: Sequence[list[str]], widths: Sequence[float] | None = None) -> Table:
    """Build a readable evidence table with an emphasized header."""
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Malgun-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Malgun"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, CREAM]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D3CF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
            ]
        )
    )
    return table


def chart(path: Path, width: float = 148 * mm) -> Image:
    """Scale a chart while preserving aspect ratio."""
    if not path.exists():
        raise ReportLayoutError(f"Missing chart: {path}")
    image = Image(str(path))
    image.drawHeight = width * image.imageHeight / image.imageWidth
    image.drawWidth = width
    image.hAlign = "CENTER"
    return image


def section_title(kicker: str, title: str, style: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Create a consistent section opening."""
    return [
        Paragraph(kicker, style["kicker"]),
        Paragraph(title, style["h1"]),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#B8CCC5")),
        Spacer(1, 4 * mm),
    ]


def confusion_rows(matrix: Sequence[Sequence[int]]) -> list[list[str]]:
    """Validate and label a five-grade confusion matrix."""
    if len(matrix) != 5 or any(len(row) != 5 for row in matrix):
        raise ValueError("Confusion matrix must be 5 x 5")
    return [
        ["실제 / 예측", "0", "1", "2", "3", "4"],
        *[[str(index), *[f"{value:,}" for value in row]] for index, row in enumerate(matrix)],
    ]
