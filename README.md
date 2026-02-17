# nfc-eink

[日本語](README.ja.md)

Python library for NFC e-ink card displays.

Supports 4 device variants (2 resolutions x 2 color modes):
- 400x300 / 296x128
- 4-color (black/white/yellow/red) / 2-color (black/white)

This library is an [nfcpy](https://github.com/nfcpy/nfcpy)-based implementation of the protocol described in [@niw's gist](https://gist.github.com/niw/3885b22d502bb1e145984d41568f202d#file-ezsignepaperprotocol-md). This project is independently developed and is not affiliated with or endorsed by the original protocol author.

> **Disclaimer:** This library was created for personal use. No warranty is provided. Use at your own risk — the author is not responsible for any damage to your devices.

> **Note:** This project was built 100% with [Claude Code](https://claude.ai/claude-code).

## Installation

```bash
pip install "nfc-eink[cli] @ git+https://github.com/alt-core/nfc-eink.git"
```

## Quick Start

### Python API

```python
from nfc_eink import EInkCard
from PIL import Image

with EInkCard() as card:
    card.send_image(Image.open("photo.png"))
    card.refresh()
```

### CLI

```bash
# Send an image to the e-ink card
nfc-eink send photo.png

# Fill the display (crop excess instead of adding margins)
nfc-eink send photo.png --resize cover

# Clear the display to white
nfc-eink clear

# Show device info
nfc-eink info

# Solid color fill (for display testing / calibration)
nfc-eink diag black
nfc-eink diag white
nfc-eink diag yellow   # 4-color devices only
nfc-eink diag red      # 4-color devices only

# Block mapping test
nfc-eink diag stripe
```

## Requirements

- Python 3.9+
- USB NFC reader (tested with Sony RC-S380 PaSoRi)
- [nfcpy](https://github.com/nfcpy/nfcpy) for NFC communication
- [lzallright](https://github.com/vlaci/lzallright) for LZO image compression

## Supported Devices

| Resolution | Colors | Palette |
|-----------|--------|---------|
| 400x300 | 4 | Black, White, Yellow, Red |
| 400x300 | 2 | Black, White |
| 296x128 | 4 | Black, White, Yellow, Red |
| 296x128 | 2 | Black, White |

Device parameters (resolution, color depth, block layout) are auto-detected via the 00D1 device info command.

## Dithering

Image conversion uses error diffusion dithering in [CIELAB](https://en.wikipedia.org/wiki/CIELAB_color_space) color space for perceptually accurate color mapping. See [docs/dithering.md](docs/dithering.md) for details.

| Algorithm | Default | Description |
|-----------|:-------:|-------------|
| `pillow` | yes | Pillow built-in (Floyd-Steinberg in RGB space, fast) |
| `atkinson` | | High contrast, ideal for limited palettes (CIELAB) |
| `floyd-steinberg` | | Standard error diffusion (CIELAB) |
| `jarvis` | | Smoothest, best for photos (CIELAB) |
| `stucki` | | Similar to Jarvis (CIELAB) |
| `none` | | Nearest color only (CIELAB) |

```python
with EInkCard() as card:
    card.send_image(Image.open("photo.png"), dither="jarvis")
    card.refresh()
```

```bash
nfc-eink send photo.png --dither jarvis
```

## Advanced Usage

```python
from nfc_eink import EInkCard

# Use raw pixel data (array of color indices matching device dimensions)
pixels = [[1] * 400 for _ in range(300)]  # all white
with EInkCard() as card:
    card.send_image(pixels)
    card.refresh()
```

## Demo

`examples/tree_demo.py` — an interactive demo that grows unique L-system trees on e-ink cards. Each device gets a deterministic tree shape based on its serial number, and each touch advances the growth by one step.

```bash
# Run the demo (waits for NFC cards in a loop)
python examples/tree_demo.py

# Preview mode: generate step images as PNG without NFC hardware
python examples/tree_demo.py --preview DEMO001
```

## License

MIT
