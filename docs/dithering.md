# Dithering Algorithms

[Japanese](dithering.ja.md)

## Background

The 4-color e-ink devices supported by this library use the following palette:

| Index | Color | RGB (for quantization) |
|:-----:|:-----:|:---:|
| 0 | Black | (0, 0, 0) |
| 1 | White | (255, 255, 255) |
| 2 | Yellow | (255, 255, 0) |
| 3 | Red | (255, 0, 0) |

When reducing a full-color image to these 4 colors, simply mapping each pixel to the nearest palette color loses all gradients and intermediate tones. Dithering diffuses the quantization error to neighboring pixels, reproducing the original color tone at a macro level.

### Palette RGB Values vs Actual Display Colors

The palette RGB values above are **idealized** and do not match the actual colors produced by e-ink displays. Due to e-ink characteristics:

- **Black**: Not perfectly black; slightly grayish
- **White**: Not pure white; closer to cream or light gray
- **Yellow**: A muted yellow, less vivid than (255, 255, 0)
- **Red**: Tends toward orange, with a hue shift from pure (255, 0, 0)

Since dithering approximates input colors as a mixture of palette colors, any discrepancy between the palette's CIELAB values and the actual display output causes suboptimal nearest-color selection and error diffusion directions. For example, if the actual red is more orange-like but the algorithm assumes pure red (255, 0, 0), intermediate color mappings will be less accurate.

Ideally, each color should be measured on the physical device with a colorimeter, and those measured RGB values should be used as the palette. The current implementation does not perform this calibration and uses idealized RGB values. You can use `nfc-eink diag black/white/yellow/red` to display solid fills of each color for visual inspection.

### Issues with Pillow-Only Dithering

Pillow's `Image.quantize()` Floyd-Steinberg dithering (RGB space) has two problems:

1. **Color distance in RGB space**: Euclidean distance in RGB does not match human color perception. With this heavily skewed palette (no blue, green, or purple), intermediate colors tend to be incorrectly mapped to yellow or red.
2. **Fixed algorithm**: Pillow only supports Floyd-Steinberg dithering, which is not optimal for extremely constrained palettes.

## Color Space: RGB vs CIELAB

### The Problem with RGB

RGB is an additive color space based on light mixing, and does not correspond to perceptual "closeness" of colors. For example:

- In RGB distance, `(0, 100, 0)` (dark green) and `(0, 0, 100)` (dark blue) are equidistant, yet blue appears much darker to the human eye.
- Saturated colors (yellow, red) can be disproportionately judged as "close."

### CIELAB (L\*a\*b\*)

CIELAB is a perceptually uniform color space defined by the International Commission on Illumination (CIE) in 1976:

- **L\***: Lightness (0=black, 100=white)
- **a\***: Red-Green axis (positive=red, negative=green)
- **b\***: Yellow-Blue axis (positive=yellow, negative=blue)

Euclidean distance in CIELAB space (CIE76 ΔE) is approximately proportional to the perceived difference between two colors. This improves:

- Nearest-color selection accuracy
- Error diffusion vectors become perceptually meaningful

### RGB → CIELAB Conversion

The conversion involves three steps:

1. **sRGB gamma expansion**: Non-linear sRGB (0-255) → linear RGB (0-1)
   - When `v ≤ 0.04045`: `v / 12.92`
   - Otherwise: `((v + 0.055) / 1.055) ^ 2.4`

2. **Linear RGB → CIE XYZ**: 3×3 matrix transformation (D65 illuminant)

3. **XYZ → CIELAB**: Non-linear transformation
   - `f(t) = t^(1/3)` when t > δ³
   - `f(t) = t/(3δ²) + 4/29` otherwise
   - where δ = 6/29

## Dithering Algorithms

### How Error Diffusion Dithering Works

Error diffusion dithering operates as follows:

1. Scan the image from top-left to bottom-right
2. For each pixel, find the nearest palette color
3. Compute the quantization error (difference between original and chosen color)
4. Add the weighted error to unprocessed neighboring pixels

The weight distribution pattern differs by algorithm. `*` marks the current pixel, numbers are weights, divided by the denominator.

### Floyd-Steinberg (1976)

```
        * 7
    3 5 1
    (÷ 16)
```

- Distributes 100% of error to 4 neighbors
- The most standard algorithm
- Produces smooth results, but can appear "muddy" with extremely limited palettes
- Fast (only 4 pixel writes)

### Atkinson (1984)

```
        * 1 1
    1 1 1
        1
    (÷ 8)
```

- Distributes **75%** of error to 6 neighbors (25% is discarded)
- Designed by Bill Atkinson for the 1-bit Macintosh display
- By discarding part of the error:
  - Contrast is preserved
  - Shadow detail is sacrificed, but the overall impression is crisp
  - Prevents the "muddy" appearance common with extremely limited palettes
- Well-suited for extremely constrained palettes like 4-color e-ink

### Jarvis-Judice-Ninke (1976)

```
            * 7 5
    3 5 7 5 3
    1 3 5 3 1
    (÷ 48)
```

- Distributes 100% of error to 12 neighbors
- Widest error spread; produces the smoothest results
- Excellent for photographic gradient reproduction
- Slower (12 pixel writes)

### Stucki (1981)

```
            * 8 4
    2 4 8 4 2
    1 2 4 2 1
    (÷ 42)
```

- Same 12-neighbor pattern as Jarvis but with different weights
- Nearly identical quality to Jarvis
- Slightly higher weight on closer neighbors

## Design in This Library

### Algorithm Selection

The `dither` parameter in `convert_image()` selects the algorithm:

```python
from nfc_eink.convert import convert_image
from PIL import Image

img = Image.open("photo.png")

# Pillow built-in Floyd-Steinberg (default) — fast, RGB space
pixels = convert_image(img, dither='pillow')

# Atkinson — high contrast, ideal for limited palettes (CIELAB)
pixels = convert_image(img, dither='atkinson')

# Floyd-Steinberg — standard error diffusion (CIELAB)
pixels = convert_image(img, dither='floyd-steinberg')

# Jarvis-Judice-Ninke — smoothest, best for photos (CIELAB)
pixels = convert_image(img, dither='jarvis')

# Stucki — similar quality to Jarvis (CIELAB)
pixels = convert_image(img, dither='stucki')

# No dithering — nearest color only (CIELAB)
pixels = convert_image(img, dither='none')
```

CLI usage:

```bash
nfc-eink send photo.png                        # default: pillow
nfc-eink send photo.png --dither atkinson      # CIELAB Atkinson
nfc-eink send photo.png --dither floyd-steinberg
nfc-eink send photo.png --dither none
```

### Pillow (Default)

`dither='pillow'` (default) uses Pillow's built-in `Image.quantize()` with Floyd-Steinberg dithering in RGB space. It is fast and stable, but color mapping accuracy is lower than the CIELAB-based methods since it uses Euclidean distance in RGB space.

The CIELAB-based algorithms (`atkinson`, `floyd-steinberg`, `jarvis`, `stucki`, `none`) offer better perceptual color accuracy but are slower (1-2 seconds at 400x300).

### Implementation Details

- All color distance calculations are performed in CIELAB space (CIE76 ΔE)
- RGB → CIELAB conversion is implemented from standard formulas (no external dependency)
- Each algorithm is simply a different weight matrix (shared core processing)
- 2-color (black/white) mode also uses the same CIELAB-based implementation
- A Pillow built-in quantize fallback is also available

## References

- Floyd, R.W. and Steinberg, L. (1976). "An Adaptive Algorithm for Spatial Greyscale." *Proceedings of the Society for Information Display*, 17(2), 75-77.
- Atkinson, B. (1984). Developed for HyperCard on the original Macintosh. No formal paper exists, but the algorithm is widely documented.
- Jarvis, J.F., Judice, C.N. and Ninke, W.H. (1976). "A Survey of Techniques for the Display of Continuous Tone Pictures on Bilevel Displays." *Computer Graphics and Image Processing*, 5(1), 13-40.
- Stucki, P. (1981). "MECCA - a multiple-error correcting computation algorithm for bilevel image hardcopy reproduction." IBM Research Report RZ1060.
- CIE (1976). "Official Recommendations on Uniform Color Spaces, Color-Difference Equations, and Psychometric Color Terms." CIE Publication No. 15, Supplement 2.
- Tanner Helland. "[Image Dithering: Eleven Algorithms and Source Code](https://tannerhelland.com/2012/12/28/dithering-eleven-algorithms-source-code.html)."
