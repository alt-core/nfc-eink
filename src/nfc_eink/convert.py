"""Image conversion from PIL Image to e-ink pixel array.

Supports 2-color (black/white) and 4-color (black/white/yellow/red) palettes.
Dithering is performed in CIELAB color space for perceptually accurate results.
Requires Pillow (optional dependency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from nfc_eink.protocol import SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from PIL import Image

# Palettes indexed by number of colors.
# "pure" uses ideal RGB values; "tuned" uses values adjusted for actual e-ink panel appearance.
PALETTES_PURE: dict[int, list[tuple[int, int, int]]] = {
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

PALETTES_TUNED: dict[int, list[tuple[int, int, int]]] = {
    2: [
        (0, 0, 0),        # 0 = Black
        (160, 160, 160),  # 1 = White (tuned)
    ],
    4: [
        (0, 0, 0),        # 0 = Black
        (160, 160, 160),  # 1 = White (tuned)
        (200, 128, 0),    # 2 = Yellow (tuned)
        (160, 0, 0),      # 3 = Red (tuned)
    ],
}

_PALETTE_MODES: dict[str, dict[int, list[tuple[int, int, int]]]] = {
    "pure": PALETTES_PURE,
    "tuned": PALETTES_TUNED,
}

# Default palettes (pure)
PALETTES = PALETTES_PURE

# Backward compatibility
EINK_PALETTE = PALETTES[4]


def get_palettes(
    palette: str = "pure",
) -> dict[int, list[tuple[int, int, int]]]:
    """Return palettes for the given mode ('pure' or 'tuned')."""
    if palette not in _PALETTE_MODES:
        raise ValueError(
            f"Unknown palette mode: {palette!r}. "
            f"Available: {', '.join(sorted(_PALETTE_MODES))}"
        )
    return _PALETTE_MODES[palette]

# Dithering algorithm weight matrices.
# Each entry: (list of (dy, dx, weight), divisor)
DITHER_MATRICES: dict[str, tuple[list[tuple[int, int, int]], int]] = {
    "atkinson": (
        [(0, 1, 1), (0, 2, 1), (1, -1, 1), (1, 0, 1), (1, 1, 1), (2, 0, 1)],
        8,
    ),
    "floyd-steinberg": (
        [(0, 1, 7), (1, -1, 3), (1, 0, 5), (1, 1, 1)],
        16,
    ),
    "jarvis": (
        [
            (0, 1, 7), (0, 2, 5),
            (1, -2, 3), (1, -1, 5), (1, 0, 7), (1, 1, 5), (1, 2, 3),
            (2, -2, 1), (2, -1, 3), (2, 0, 5), (2, 1, 3), (2, 2, 1),
        ],
        48,
    ),
    "stucki": (
        [
            (0, 1, 8), (0, 2, 4),
            (1, -2, 2), (1, -1, 4), (1, 0, 8), (1, 1, 4), (1, 2, 2),
            (2, -2, 1), (2, -1, 2), (2, 0, 4), (2, 1, 2), (2, 2, 1),
        ],
        42,
    ),
}

# sRGB to XYZ (D65) matrix
_SRGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])

# D65 reference white
_D65_WHITE = np.array([0.95047, 1.00000, 1.08883])

# CIELAB constants
_LAB_DELTA = 6.0 / 29.0
_LAB_DELTA_SQ = _LAB_DELTA ** 2
_LAB_DELTA_CU = _LAB_DELTA ** 3


def _srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """Convert sRGB (0-255) to linear RGB (0-1)."""
    v = srgb / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _lab_f(t: np.ndarray) -> np.ndarray:
    """CIELAB transfer function."""
    return np.where(t > _LAB_DELTA_CU, np.cbrt(t), t / (3.0 * _LAB_DELTA_SQ) + 4.0 / 29.0)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert RGB (0-255) to CIELAB.

    Args:
        rgb: Array of shape (..., 3) with uint8 or float RGB values.

    Returns:
        Array of same shape with L*, a*, b* values.
    """
    linear = _srgb_to_linear(rgb.astype(np.float64))
    xyz = linear @ _SRGB_TO_XYZ.T
    xyz_norm = xyz / _D65_WHITE
    fx, fy, fz = _lab_f(xyz_norm[..., 0]), _lab_f(xyz_norm[..., 1]), _lab_f(xyz_norm[..., 2])
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1)


# Inverse conversion: CIELAB → RGB

_XYZ_TO_SRGB = np.linalg.inv(_SRGB_TO_XYZ)


def _lab_f_inv(t: np.ndarray) -> np.ndarray:
    """Inverse CIELAB transfer function."""
    return np.where(
        t > _LAB_DELTA,
        t ** 3,
        3.0 * _LAB_DELTA_SQ * (t - 4.0 / 29.0),
    )


def _linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    """Convert linear RGB (0-1) to sRGB (0-1)."""
    v = np.clip(linear, 0.0, 1.0)
    return np.where(
        v <= 0.0031308,
        v * 12.92,
        1.055 * v ** (1.0 / 2.4) - 0.055,
    )


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """Convert CIELAB to RGB (0-255).

    Args:
        lab: Array of shape (..., 3) with L*, a*, b* values.

    Returns:
        Array of same shape with uint8 RGB values, clipped to [0, 255].
    """
    L = lab[..., 0]
    a = lab[..., 1]
    b = lab[..., 2]
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0
    xyz = np.stack([
        _D65_WHITE[0] * _lab_f_inv(fx),
        _D65_WHITE[1] * _lab_f_inv(fy),
        _D65_WHITE[2] * _lab_f_inv(fz),
    ], axis=-1)
    linear = xyz @ _XYZ_TO_SRGB.T
    srgb = _linear_to_srgb(linear)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


# Tone mapping helpers

def _compute_l_scale(
    palette_rgb: list[tuple[int, int, int]],
) -> float | None:
    """Compute L* scale factor for tone mapping.

    Returns L*_max / 100 for the given palette, or None if no scaling
    is needed (L*_max >= 99).
    """
    labs = rgb_to_lab(np.array(palette_rgb, dtype=np.uint8))
    l_max = float(np.max(labs[:, 0]))
    if l_max >= 99.0:
        return None
    return l_max / 100.0


def _tone_map_rgb(
    image_rgb: np.ndarray,
    l_scale: float,
) -> np.ndarray:
    """Apply luminance tone mapping to an RGB image.

    Converts to CIELAB, scales L*, converts back to RGB.

    Args:
        image_rgb: (H, W, 3) uint8 array.
        l_scale: Multiplicative factor for L* channel (0 < l_scale <= 1).

    Returns:
        (H, W, 3) uint8 array with tone-mapped RGB values.
    """
    lab = rgb_to_lab(image_rgb)
    lab[..., 0] *= l_scale
    return lab_to_rgb(lab)


def _dither(
    image_rgb: np.ndarray,
    palette_rgb: np.ndarray,
    method: str = "atkinson",
    l_scale: float | None = None,
) -> np.ndarray:
    """Error diffusion dithering in CIELAB space.

    The inner loop uses plain Python arithmetic to avoid numpy per-pixel
    overhead (creating tiny temporary arrays for each of 120k pixels).

    Args:
        image_rgb: (H, W, 3) uint8 array.
        palette_rgb: (N, 3) uint8 array of palette colors.
        method: Dithering algorithm name.
        l_scale: Optional L* scale factor for tone mapping.

    Returns:
        (H, W) uint8 array of palette indices.
    """
    h, w = image_rgb.shape[:2]

    # Vectorized Lab conversion (fast batch operation)
    palette_lab = rgb_to_lab(palette_rgb)
    image_lab = rgb_to_lab(image_rgb)

    # Tone mapping: compress luminance range to match palette
    if l_scale is not None:
        image_lab[..., 0] *= l_scale

    # Extract to plain Python lists for fast per-pixel access.
    # numpy indexing overhead (~μs per access) dominates when called 120k times.
    working = image_lab.tolist()  # h × w × [L, a, b]
    n_colors = len(palette_lab)
    pal = [
        (float(palette_lab[i, 0]), float(palette_lab[i, 1]), float(palette_lab[i, 2]))
        for i in range(n_colors)
    ]

    result = [[0] * w for _ in range(h)]

    if method == "none":
        for y in range(h):
            row_w = working[y]
            row_r = result[y]
            for x in range(w):
                px = row_w[x]
                pL, pa, pb = px[0], px[1], px[2]
                best_idx = 0
                best_d = float("inf")
                for ci in range(n_colors):
                    cL, ca, cb = pal[ci]
                    d = (pL - cL) ** 2 + (pa - ca) ** 2 + (pb - cb) ** 2
                    if d < best_d:
                        best_d = d
                        best_idx = ci
                row_r[x] = best_idx
        return np.array(result, dtype=np.uint8)

    offsets, divisor = DITHER_MATRICES[method]
    # Pre-compute weight/divisor to avoid repeated division
    weighted_offsets = [(dy, dx, weight / divisor) for dy, dx, weight in offsets]

    for y in range(h):
        row_w = working[y]
        row_r = result[y]
        for x in range(w):
            px = row_w[x]
            pL, pa, pb = px[0], px[1], px[2]

            # Find nearest palette color (inline distance for speed)
            best_idx = 0
            best_d = float("inf")
            for ci in range(n_colors):
                cL, ca, cb = pal[ci]
                d = (pL - cL) ** 2 + (pa - ca) ** 2 + (pb - cb) ** 2
                if d < best_d:
                    best_d = d
                    best_idx = ci

            row_r[x] = best_idx

            # Compute and distribute error
            cL, ca, cb = pal[best_idx]
            eL = pL - cL
            ea = pa - ca
            eb = pb - cb

            for dy, dx, f in weighted_offsets:
                ny = y + dy
                nx = x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    nb = working[ny][nx]
                    nb[0] += eL * f
                    nb[1] += ea * f
                    nb[2] += eb * f

    return np.array(result, dtype=np.uint8)


def _build_palette_image(
    num_colors: int = 4,
    palette_mode: str = "pure",
) -> Image.Image:
    """Build a Pillow palette image for quantization."""
    from PIL import Image as PILImage

    palettes = get_palettes(palette_mode)
    palette = palettes[num_colors]
    palette_img = PILImage.new("P", (1, 1))
    palette_data: list[int] = []
    for r, g, b in palette:
        palette_data.extend([r, g, b])
    palette_data.extend([0, 0, 0] * (256 - len(palette)))
    palette_img.putpalette(palette_data)
    return palette_img


def _quantize_pillow(
    fitted: Image.Image,
    num_colors: int,
    width: int,
    height: int,
    palette_mode: str = "pure",
) -> list[list[int]]:
    """Fallback quantization using Pillow's built-in Floyd-Steinberg dithering.

    Uses RGB-space color distance (Pillow's internal implementation).
    """
    from PIL import Image as PILImage

    palette_img = _build_palette_image(num_colors, palette_mode)
    quantized = fitted.quantize(
        colors=num_colors,
        palette=palette_img,
        dither=PILImage.Dither.FLOYDSTEINBERG,
    )
    pixels_flat = list(quantized.getdata())
    return [
        pixels_flat[y * width : (y + 1) * width]
        for y in range(height)
    ]


def _fit_image(
    image: Image.Image,
    width: int,
    height: int,
    resize: str = "fit",
) -> Image.Image:
    """Resize image to target dimensions, preserving aspect ratio.

    Args:
        image: Source PIL Image.
        width: Target width.
        height: Target height.
        resize: Resize mode.
            'fit': Scale to fit within target, white margins (default).
            'cover': Scale to fill target, crop excess.
    """
    from PIL import Image as PILImage

    image = image.convert("RGB")

    if resize == "cover":
        scale = max(width / image.width, height / image.height)
    else:
        scale = min(width / image.width, height / image.height)

    new_w = int(image.width * scale)
    new_h = int(image.height * scale)

    resized = image.resize((new_w, new_h), PILImage.LANCZOS)

    if resize == "cover":
        # Center crop to target size
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        return resized.crop((left, top, left + width, top + height))
    else:
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
    num_colors: int = 4,
    dither: str = "pillow",
    resize: str = "fit",
    palette: str = "pure",
    tone_map: bool | None = None,
) -> list[list[int]]:
    """Convert a PIL Image to a color index array for e-ink display.

    The image is resized to the target dimensions (preserving aspect ratio),
    then dithered to the target palette.

    Args:
        image: Source PIL Image (any mode).
        width: Target width (default 400).
        height: Target height (default 300).
        num_colors: 2 for black/white, 4 for black/white/yellow/red.
        dither: Dithering algorithm. One of 'pillow' (default),
            'atkinson', 'floyd-steinberg', 'jarvis', 'stucki', 'none'.
            'pillow' uses Pillow's built-in Floyd-Steinberg in RGB space.
            Other methods use CIELAB color space for perceptually accurate
            results but are slower.
        resize: Resize mode. 'fit' (default) scales to fit within target
            with white margins. 'cover' scales to fill target and crops
            the excess.
        palette: Palette mode. 'pure' (default) uses ideal RGB values.
            'tuned' uses colors adjusted for actual panel appearance.
        tone_map: Enable luminance tone mapping to compress the image's
            brightness range to match the palette. None (default) enables
            it automatically for 'tuned' palette.

    Returns:
        2D list of color indices, shape (height, width).
    """
    valid_methods = set(DITHER_MATRICES) | {"none", "pillow"}
    if dither not in valid_methods:
        raise ValueError(
            f"Unknown dither method: {dither!r}. "
            f"Available: {', '.join(sorted(valid_methods))}"
        )

    palettes = get_palettes(palette)

    if num_colors not in palettes:
        raise ValueError(
            f"Unsupported num_colors={num_colors}. "
            f"Supported: {', '.join(str(k) for k in sorted(palettes))}. "
            f"The device may have reported unexpected parameters — "
            f"run 'nfc-eink info' to check raw device data."
        )

    valid_resize = ("fit", "cover")
    if resize not in valid_resize:
        raise ValueError(
            f"Unknown resize mode: {resize!r}. "
            f"Available: {', '.join(valid_resize)}"
        )

    # Resolve tone mapping
    if tone_map is None:
        tone_map = (palette != "pure")

    l_scale: float | None = None
    if tone_map:
        l_scale = _compute_l_scale(palettes[num_colors])

    fitted = _fit_image(image, width, height, resize=resize)

    if dither == "pillow":
        if l_scale is not None:
            from PIL import Image as PILImage

            mapped_rgb = _tone_map_rgb(np.array(fitted, dtype=np.uint8), l_scale)
            fitted = PILImage.fromarray(mapped_rgb)
        return _quantize_pillow(fitted, num_colors, width, height, palette)

    image_rgb = np.array(fitted, dtype=np.uint8)
    palette_rgb = np.array(palettes[num_colors], dtype=np.uint8)

    indices = _dither(image_rgb, palette_rgb, method=dither, l_scale=l_scale)

    return [indices[y].tolist() for y in range(height)]
