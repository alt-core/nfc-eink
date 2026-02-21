"""Device information parsing for NFC e-ink cards."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Panel resolutions known to use a 90deg CW rotated framebuffer layout.
_ROTATED_PANELS: set[tuple[int, int]] = {
    (296, 128),
}



@dataclass
class DeviceInfo:
    """Parsed device information from 00D1 response.

    Attributes:
        width: Screen width in pixels (e.g. 400, 296).
        height: Screen height in pixels (e.g. 300, 128).
        bits_per_pixel: Color depth (1 = 2-color, 2 = 4-color).
        rows_per_block: Number of pixel rows per transfer block.
        serial_number: Per-device ASCII string from C0 tag
            (e.g. "SEAA000282"). Likely a serial number based on
            the format, but not confirmed by specification.
        c1: Per-device binary value from C1 tag (4 bytes observed).
            Purpose unknown; differs between individual devices.
        raw: Original response bytes.
    """

    width: int
    height: int
    bits_per_pixel: int
    rows_per_block: int
    serial_number: str
    c1: bytes = b""
    raw: bytes = b""
    hflip: bool = False

    @property
    def num_colors(self) -> int:
        """Number of colors (2 or 4)."""
        return 1 << self.bits_per_pixel

    @property
    def pixels_per_byte(self) -> int:
        """Pixels packed into one byte (8 or 4)."""
        return 8 // self.bits_per_pixel

    @property
    def bytes_per_row(self) -> int:
        """Packed bytes per pixel row."""
        return self.width // self.pixels_per_byte

    @property
    def rotated(self) -> bool:
        """Whether framebuffer is rotated 90deg CW relative to physical display.

        Some e-ink panels store pixels in a rotated layout where the
        physical width becomes the framebuffer height and vice versa.
        This is a hardware property of specific panel resolutions.
        """
        return (self.width, self.height) in _ROTATED_PANELS

    @property
    def fb_width(self) -> int:
        """Framebuffer width in pixels (after rotation if applicable)."""
        return self.height if self.rotated else self.width

    @property
    def fb_height(self) -> int:
        """Framebuffer height in pixels (after rotation if applicable)."""
        return self.width if self.rotated else self.height

    @property
    def fb_bytes_per_row(self) -> int:
        """Packed bytes per framebuffer row."""
        return self.fb_width // self.pixels_per_byte

    @property
    def fb_total_bytes(self) -> int:
        """Total framebuffer size in bytes."""
        return self.fb_bytes_per_row * self.fb_height

    @property
    def block_sizes(self) -> list[int]:
        """List of block sizes for full-screen transfer.

        Each block is at most 2000 bytes. The last block may be smaller.
        """
        max_bs = 2000
        total = self.fb_total_bytes
        sizes: list[int] = []
        while total > 0:
            s = min(total, max_bs)
            sizes.append(s)
            total -= s
        return sizes

    @property
    def num_blocks(self) -> int:
        """Total number of blocks for the full screen."""
        return len(self.block_sizes)


def parse_tlv(data: bytes) -> dict[int, bytes]:
    """Parse TLV (Tag-Length-Value) records from device info response.

    Args:
        data: Raw response bytes from 00D1 command.

    Returns:
        Dict mapping tag number to value bytes.
    """
    result: dict[int, bytes] = {}
    offset = 0
    while offset + 2 <= len(data):
        tag = data[offset]
        length = data[offset + 1]
        offset += 2
        if offset + length > len(data):
            break
        result[tag] = data[offset : offset + length]
        offset += length
    return result


# Map A0 color mode byte to bits_per_pixel.
# a0[1] is NOT bpp directly; it's a color mode code.
# The "height" field in A0 stores physical_height * bpp.
_COLOR_MODE_TO_BPP: dict[int, int] = {
    0x01: 1,  # 2-color (black/white) — 296x128
    0x07: 2,  # 4-color (black/white/yellow/red) — 400x300
    0x47: 1,  # 2-color (black/white) — 400x300
}


def parse_device_info(data: bytes) -> DeviceInfo:
    """Parse 00D1 device info response into DeviceInfo.

    TLV structure (observed):
        A0: [flags, color_mode, rows_per_block, height_raw_hi, height_raw_lo, width_hi, width_lo]
        C0: per-device ASCII string (10 bytes observed, e.g. "SEAA000282")
        C1: per-device binary value (4 bytes observed, purpose unknown)

    The height_raw field stores physical_height * bits_per_pixel.
    color_mode is mapped to bpp via _COLOR_MODE_TO_BPP (0x01→1bpp, 0x07→2bpp).

    Args:
        data: Raw response bytes from 00D1 command.

    Returns:
        Parsed DeviceInfo.

    Raises:
        ValueError: If required TLV tags are missing or color mode is unknown.
    """
    tlv = parse_tlv(data)

    if 0xA0 not in tlv or len(tlv[0xA0]) < 7:
        raise ValueError(f"Missing or invalid A0 tag in device info: {data.hex()}")

    a0 = tlv[0xA0]
    color_mode = a0[1]
    rows_per_block = a0[2]
    height_raw = (a0[3] << 8) | a0[4]
    width = (a0[5] << 8) | a0[6]

    if color_mode not in _COLOR_MODE_TO_BPP:
        a0_hex = " ".join(f"{b:02x}" for b in a0)
        raise ValueError(
            f"Unknown color mode 0x{color_mode:02x} in A0 tag. "
            f"Known modes: {', '.join(f'0x{k:02x}' for k in _COLOR_MODE_TO_BPP)}. "
            f"A0 raw: [{a0_hex}]. Full response: {data.hex()}"
        )

    bits_per_pixel = _COLOR_MODE_TO_BPP[color_mode]
    height = height_raw // bits_per_pixel

    # Some panels report portrait dimensions (width < height) for a
    # physically landscape display. Swap to present as landscape.
    swapped = width < height
    if swapped:
        width, height = height, width

    serial_number = ""
    if 0xC0 in tlv:
        serial_number = tlv[0xC0].decode("ascii", errors="replace")

    c1 = b""
    if 0xC1 in tlv:
        c1 = tlv[0xC1]

    # For swapped panels: if _ROTATED_PANELS handles the axis transform
    # via CW90 rotation, hflip is not needed. Otherwise hflip compensates.
    rotated = (width, height) in _ROTATED_PANELS
    hflip = swapped and not rotated

    return DeviceInfo(
        width=width,
        height=height,
        bits_per_pixel=bits_per_pixel,
        rows_per_block=rows_per_block,
        serial_number=serial_number,
        c1=c1,
        raw=data,
        hflip=hflip,
    )
