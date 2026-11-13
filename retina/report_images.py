"""Actual retinal-image presentation helpers for PDF reports."""

from pathlib import Path
from typing import Final

from PIL import Image as PILImage
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

ROOT: Final = Path(__file__).resolve().parents[1]


class ReportImageError(RuntimeError):
    """A required report image cannot be rendered."""


def _report_thumbnail(source: Path) -> Path:
    """Create a bounded derivative while preserving the verified original JPEG."""
    destination = ROOT / "output/report-preview/assets" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return destination
    with PILImage.open(source) as original:
        prepared = original.convert("RGB")
        prepared.thumbnail((1000, 1000), PILImage.Resampling.LANCZOS)
        prepared.save(destination, format="JPEG", quality=86, optimize=True)
    return destination


def paired_images(
    left: Path,
    right: Path,
    title: str,
    labels: str,
    style: dict[str, ParagraphStyle],
) -> KeepTogether:
    """Present one actual bilateral example with source labels."""
    missing = [str(path) for path in (left, right) if not path.exists()]
    if missing:
        message = f"Missing retinal examples: {', '.join(missing)}"
        raise ReportImageError(message)
    left_thumb = _report_thumbnail(left)
    right_thumb = _report_thumbnail(right)
    size = 68 * mm
    with PILImage.open(left_thumb) as left_source, PILImage.open(right_thumb) as right_source:
        left_ratio = left_source.width / left_source.height
        right_ratio = right_source.width / right_source.height
    left_width = min(size, size * left_ratio)
    left_height = min(size, size / left_ratio)
    right_width = min(size, size * right_ratio)
    right_height = min(size, size / right_ratio)
    images = Table(
        [
            [
                Image(str(left_thumb), left_width, left_height),
                Image(str(right_thumb), right_width, right_height),
            ]
        ],
        colWidths=[82 * mm] * 2,
        rowHeights=[size],
    )
    images.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return KeepTogether(
        [
            Paragraph(title, style["h2"]),
            images,
            Paragraph(labels, style["caption"]),
            Spacer(1, 2 * mm),
        ]
    )
