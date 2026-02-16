"""Device information parsing for NFC e-ink cards."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """Parsed device information from 00D1 response.

    Attributes:
        width: Screen width in pixels (e.g. 400, 296).
        height: Screen height in pixels (e.g. 300, 128).
        bits_per_pixel: Color depth (1 = 2-color, 2 = 4-color).
        rows_per_block: Number of pixel rows per transfer block.
        serial_number: Device serial string (e.g. "SEAA000282").
        raw: Original response bytes.
    """

    width: int
    height: int
    bits_per_pixel: int
    rows_per_block: int
    serial_number: str
    raw: bytes = b""

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
    def block_size(self) -> int:
        """Uncompressed bytes per block."""
        return self.bytes_per_row * self.rows_per_block

    @property
    def num_blocks(self) -> int:
        """Total number of blocks for the full screen."""
        return self.height // self.rows_per_block

    @property
    def blocks_per_page(self) -> int:
        """Number of blocks per F0D3 page (P1 address space).

        For 2-color devices, empirically 2 blocks per page.
        For 4-color devices, all blocks fit in a single page.
        """
        if self.bits_per_pixel == 1:
            return 2
        return self.num_blocks

    @property
    def num_pages(self) -> int:
        """Number of F0D3 pages needed for full screen."""
        return self.num_blocks // self.blocks_per_page


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


def parse_device_info(data: bytes) -> DeviceInfo:
    """Parse 00D1 device info response into DeviceInfo.

    TLV structure (observed):
        A0: [flags, color_planes, rows_per_block, height_hi, height_lo, width_hi, width_lo]
        C0: serial number (ASCII)

    Args:
        data: Raw response bytes from 00D1 command.

    Returns:
        Parsed DeviceInfo.

    Raises:
        ValueError: If required TLV tags are missing.
    """
    tlv = parse_tlv(data)

    if 0xA0 not in tlv or len(tlv[0xA0]) < 7:
        raise ValueError(f"Missing or invalid A0 tag in device info: {data.hex()}")

    a0 = tlv[0xA0]
    bits_per_pixel = a0[1]
    rows_per_block = a0[2]
    height = (a0[3] << 8) | a0[4]
    width = (a0[5] << 8) | a0[6]

    serial_number = ""
    if 0xC0 in tlv:
        serial_number = tlv[0xC0].decode("ascii", errors="replace")

    return DeviceInfo(
        width=width,
        height=height,
        bits_per_pixel=bits_per_pixel,
        rows_per_block=rows_per_block,
        serial_number=serial_number,
        raw=data,
    )
