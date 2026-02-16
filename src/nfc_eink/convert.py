"""Image conversion from PIL Image to 4-color e-ink pixel array.

Requires Pillow (optional dependency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nfc_eink.protocol import SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from PIL import Image

# E-ink 4-color palette: Black, White, Yellow, Red
EINK_PALETTE: list[tuple[int, int, int]] = [
    (0, 0, 0),        # 0 = Black
    (255, 255, 255),  # 1 = White
    (255, 255, 0),    # 2 = Yellow
    (255, 0, 0),      # 3 = Red
]


def _build_palette_image() -> Image.Image:
    """Build a Pillow palette image for quantization."""
    from PIL import Image as PILImage

    palette_img = PILImage.new("P", (1, 1))
    # Palette data: 256 entries × 3 channels = 768 bytes
    palette_data = []
    for r, g, b in EINK_PALETTE:
        palette_data.extend([r, g, b])
    # Fill remaining palette entries with black
    palette_data.extend([0, 0, 0] * (256 - len(EINK_PALETTE)))
    palette_img.putpalette(palette_data)
    return palette_img


def _fit_image(
    image: Image.Image,
    width: int = SCREEN_WIDTH,
    height: int = SCREEN_HEIGHT,
) -> Image.Image:
    """Resize image to fit within target dimensions, preserving aspect ratio.

    The image is resized to fit within width x height, then centered
    on a white background.

    Args:
        image: Source PIL Image.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        Resized RGB image of exactly width x height.
    """
    from PIL import Image as PILImage

    image = image.convert("RGB")

    # Calculate scale to fit within target
    scale = min(width / image.width, height / image.height)
    new_w = int(image.width * scale)
    new_h = int(image.height * scale)

    resized = image.resize((new_w, new_h), PILImage.LANCZOS)

    # Center on white background
    result = PILImage.new("RGB", (width, height), (255, 255, 255))
    offset_x = (width - new_w) // 2
    offset_y = (height - new_h) // 2
    result.paste(resized, (offset_x, offset_y))
    return result


def convert_image(
    image: Image.Image,
    width: int = SCREEN_WIDTH,
    height: int = SCREEN_HEIGHT,
) -> list[list[int]]:
    """Convert a PIL Image to a 4-color index array for e-ink display.

    The image is resized to fit the target dimensions (preserving aspect ratio,
    white background), then quantized to 4 colors with Floyd-Steinberg dithering.

    Args:
        image: Source PIL Image (any mode).
        width: Target width (default 400).
        height: Target height (default 300).

    Returns:
        2D list of color indices, shape (height, width).
        Values: 0=Black, 1=White, 2=Yellow, 3=Red.
    """
    fitted = _fit_image(image, width, height)
    palette_img = _build_palette_image()

    # Quantize with Floyd-Steinberg dithering
    quantized = fitted.quantize(
        colors=len(EINK_PALETTE),
        palette=palette_img,
        dither=1,  # Floyd-Steinberg
    )

    # Convert palette indices to 2D list
    pixels_flat = list(quantized.getdata())
    return [
        pixels_flat[y * width : (y + 1) * width]
        for y in range(height)
    ]
