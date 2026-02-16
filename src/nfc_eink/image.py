"""Image encoding for NFC e-ink cards.

Handles pixel packing, block splitting, LZO compression, and fragmentation.
This module works with raw color index arrays and does not depend on Pillow.

Supports both 2-color (1bpp) and 4-color (2bpp) devices.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lzallright import LZOCompressor

from nfc_eink.protocol import MAX_FRAGMENT_DATA, Apdu, build_image_apdu

if TYPE_CHECKING:
    from nfc_eink.device import DeviceInfo


def pack_row(pixels: list[int], bits_per_pixel: int = 2) -> bytes:
    """Pack a single row of color index pixels into bytes.

    Byte order within a row is right-to-left.

    For 2bpp (4-color): byte = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)
    For 1bpp (2-color): byte = p0 | (p1 << 1) | ... | (p7 << 7)

    Args:
        pixels: Color index values for one row.
        bits_per_pixel: 1 for 2-color, 2 for 4-color.

    Returns:
        Packed pixel bytes.
    """
    ppb = 8 // bits_per_pixel  # pixels per byte
    width = len(pixels)
    bytes_per_row = width // ppb
    row_bytes = bytearray(bytes_per_row)

    for byte_idx in range(bytes_per_row):
        pixel_offset = (bytes_per_row - 1 - byte_idx) * ppb
        val = 0
        for i in range(ppb):
            val |= pixels[pixel_offset + i] << (i * bits_per_pixel)
        row_bytes[byte_idx] = val

    return bytes(row_bytes)


def pack_pixels(
    pixels: list[list[int]], bits_per_pixel: int = 2
) -> bytes:
    """Pack a full screen of pixels into bytes.

    Args:
        pixels: 2D list of color indices, shape (height, width).
        bits_per_pixel: 1 for 2-color, 2 for 4-color.

    Returns:
        Packed pixel data bytes.
    """
    return b"".join(pack_row(row, bits_per_pixel) for row in pixels)


def split_blocks(packed: bytes, block_size: int) -> list[bytes]:
    """Split packed pixel data into blocks.

    Args:
        packed: Packed pixel data bytes.
        block_size: Bytes per block.

    Returns:
        List of blocks.
    """
    num_blocks = len(packed) // block_size
    return [packed[i * block_size : (i + 1) * block_size] for i in range(num_blocks)]


def compress_block(block: bytes) -> bytes:
    """Compress a block using LZO1X-1.

    Args:
        block: Uncompressed block data.

    Returns:
        LZO-compressed bytes.
    """
    compressor = LZOCompressor()
    return compressor.compress(block)


def make_fragments(compressed: bytes) -> list[bytes]:
    """Split compressed data into fragments of at most 250 bytes.

    Args:
        compressed: LZO-compressed block data.

    Returns:
        List of fragment byte strings.
    """
    fragments = []
    for i in range(0, len(compressed), MAX_FRAGMENT_DATA):
        fragments.append(compressed[i : i + MAX_FRAGMENT_DATA])
    return fragments


def encode_image(
    pixels: list[list[int]],
    device_info: DeviceInfo | None = None,
) -> list[list[Apdu]]:
    """Encode a full image into APDU commands ready for transmission.

    Args:
        pixels: 2D list of color indices, shape (height, width).
        device_info: Device parameters. If None, assumes 400x300 4-color.

    Returns:
        List of blocks, each containing a list of APDU tuples.
    """
    if device_info is not None:
        bpp = device_info.bits_per_pixel
        bs = device_info.block_size
    else:
        bpp = 2
        bs = 2000  # 400x300 4-color default

    packed = pack_pixels(pixels, bpp)
    blocks = split_blocks(packed, bs)
    all_apdus: list[list[Apdu]] = []

    for block_no, block in enumerate(blocks):
        compressed = compress_block(block)
        fragments = make_fragments(compressed)
        block_apdus: list[Apdu] = []

        for frag_no, fragment in enumerate(fragments):
            is_final = frag_no == len(fragments) - 1
            apdu = build_image_apdu(block_no, frag_no, fragment, is_final)
            block_apdus.append(apdu)

        all_apdus.append(block_apdus)

    return all_apdus
