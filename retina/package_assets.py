"""Create compact standalone-viewer assets without altering source JPEGs."""

from pathlib import Path
from typing import Final

from PIL import Image, ImageOps

THUMBNAIL_LONG_EDGE: Final = 960
JPEG_QUALITY: Final = 88


def prepare_thumbnail(source: Image.Image) -> Image.Image:
    """Remove near-black margins and constrain the long edge without distortion."""
    rgb = ImageOps.exif_transpose(source).convert("RGB")
    mask = rgb.convert("L").point([0] * 9 + [255] * 247)
    bounds = mask.getbbox()
    if bounds is not None:
        rgb = rgb.crop(bounds)
    rgb.thumbnail((THUMBNAIL_LONG_EDGE, THUMBNAIL_LONG_EDGE), Image.Resampling.LANCZOS)
    return rgb


def create_assignment1_thumbnails(root: Path, names: tuple[str, ...]) -> None:
    """Write viewer thumbnails from already verified original images."""
    destination = root / "outputs/assignment1/images"
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        with Image.open(root / f"data/images/{name}.jpg") as source:
            thumbnail = prepare_thumbnail(source)
            thumbnail.save(
                destination / f"{name}.jpg",
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
            )
