"""One canonical image preprocessing path for training and live inference."""

from typing import Final

from PIL import Image, ImageOps

IMAGE_SIZE: Final = 320


def prepare_image(source: Image.Image) -> Image.Image:
    """Crop near-black margins and pad to a square without changing aspect ratio."""
    rgb = ImageOps.exif_transpose(source).convert("RGB")
    mask = rgb.convert("L").point([0] * 9 + [255] * 247)
    bounds = mask.getbbox()
    if bounds is not None:
        rgb = rgb.crop(bounds)
    rgb.thumbnail((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE))
    canvas.paste(rgb, ((IMAGE_SIZE - rgb.width) // 2, (IMAGE_SIZE - rgb.height) // 2))
    return canvas
