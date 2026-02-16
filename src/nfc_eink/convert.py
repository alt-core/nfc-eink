"""Image conversion from PIL Image to e-ink pixel array.

Supports 2-color (black/white) and 4-color (black/white/yellow/red) palettes.
Requires Pillow (optional dependency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nfc_eink.protocol import SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from PIL import Image

# Palettes indexed by number of colors
PALETTES: dict[int, list[tuple[int, int, int]]] = {
    2: [
        (0, 0, 0),        # 0 = Black
        (255, 255, 255),  # 1 = White
    ],
    4: [
        (0, 0, 0),        # 0 = Black
        (255, 255, 255),  # 1 = White
        (255, 255, 0),    # 2 = Yellow
        (255, 0, 0),      # 3 = Red
    ],
}

# Backward compatibility
EINK_PALETTE = PALETTES[4]


def _build_palette_image(num_colors: int = 4) -> Image.Image:
    """Build a Pillow palette image for quantization."""
    from PIL import Image as PILImage

    palette = PALETTES[num_colors]
    palette_img = PILImage.new("P", (1, 1))
    palette_data: list[int] = []
    for r, g, b in palette:
        palette_data.extend([r, g, b])
    palette_data.extend([0, 0, 0] * (256 - len(palette)))
    palette_img.putpalette(palette_data)
    return palette_img


def _fit_image(
    image: Image.Image,
    width: int,
    height: int,
) -> Image.Image:
    """Resize image to fit within target dimensions, preserving aspect ratio.

    The image is centered on a white background.
    """
    from PIL import Image as PILImage

    image = image.convert("RGB")

    scale = min(width / image.width, height / image.height)
    new_w = int(image.width * scale)
    new_h = int(image.height * scale)

    resized = image.resize((new_w, new_h), PILImage.LANCZOS)

    result = PILImage.new("RGB", (width, height), (255, 255, 255))
    offset_x = (width - new_w) // 2
    offset_y = (height - new_h) // 2
    result.paste(resized, (offset_x, offset_y))
    return result


def convert_image(
    image: Image.Image,
    width: int = SCREEN_WIDTH,
    height: int = SCREEN_HEIGHT,
    num_colors: int = 4,
) -> list[list[int]]:
    """Convert a PIL Image to a color index array for e-ink display.

    The image is resized to fit the target dimensions (preserving aspect ratio,
    white background), then quantized with Floyd-Steinberg dithering.

    Args:
        image: Source PIL Image (any mode).
        width: Target width (default 400).
        height: Target height (default 300).
        num_colors: 2 for black/white, 4 for black/white/yellow/red.

    Returns:
        2D list of color indices, shape (height, width).
    """
    fitted = _fit_image(image, width, height)
    palette_img = _build_palette_image(num_colors)

    quantized = fitted.quantize(
        colors=num_colors,
        palette=palette_img,
        dither=1,  # Floyd-Steinberg
    )

    pixels_flat = list(quantized.getdata())
    return [
        pixels_flat[y * width : (y + 1) * width]
        for y in range(height)
    ]
