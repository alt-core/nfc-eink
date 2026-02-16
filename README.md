# nfc-eink

[日本語](README.ja.md)

Python library for NFC e-ink card displays (400x300, 4-color).

This library is an [nfcpy](https://github.com/nfcpy/nfcpy)-based implementation of the protocol described in [@niw's gist](https://gist.github.com/niw/3885b22d502bb1e145984d41568f202d#file-ezsignepaperprotocol-md). This project is independently developed and is not affiliated with or endorsed by the original protocol author.

## Installation

```bash
pip install nfc-eink[cli]
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

# Show device info
nfc-eink info
```

## Requirements

- Python 3.9+
- USB NFC reader (tested with Sony RC-S380 PaSoRi)
- [nfcpy](https://github.com/nfcpy/nfcpy) for NFC communication
- [lzallright](https://github.com/vlaci/lzallright) for LZO image compression

## Supported Colors

| Index | Color  |
|-------|--------|
| 0     | Black  |
| 1     | White  |
| 2     | Yellow |
| 3     | Red    |

## Advanced Usage

```python
from nfc_eink import EInkCard

# Use raw pixel data (300x400 array of color indices 0-3)
pixels = [[1] * 400 for _ in range(300)]  # all white
with EInkCard() as card:
    card.send_image(pixels)
    card.refresh()
```

## License

MIT
