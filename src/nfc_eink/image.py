"""Image encoding for NFC e-ink cards.

Handles pixel packing, block splitting, LZO compression, and fragmentation.
This module works with raw color index arrays (0=Black, 1=White, 2=Yellow, 3=Red)
and does not depend on Pillow.
"""

from __future__ import annotations

from lzallright import LZOCompressor

from nfc_eink.protocol import (
    BLOCK_ROWS,
    BLOCK_SIZE,
    BYTES_PER_ROW,
    MAX_FRAGMENT_DATA,
    NUM_BLOCKS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    Apdu,
    build_image_apdu,
)


def pack_row(pixels: list[int]) -> bytes:
    """Pack a single row of color index pixels into bytes.

    Packs 4 pixels per byte using: byte = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)
    Byte order within a row is right-to-left (last 4 pixels become first byte).

    Args:
        pixels: List of 400 color index values (0..3).

    Returns:
        100 bytes of packed pixel data.
    """
    row_bytes = bytearray(BYTES_PER_ROW)
    for byte_idx in range(BYTES_PER_ROW):
        # Right-to-left: byte 0 = rightmost 4 pixels, byte 99 = leftmost 4 pixels
        pixel_offset = (BYTES_PER_ROW - 1 - byte_idx) * 4
        p0 = pixels[pixel_offset]
        p1 = pixels[pixel_offset + 1]
        p2 = pixels[pixel_offset + 2]
        p3 = pixels[pixel_offset + 3]
        row_bytes[byte_idx] = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)
    return bytes(row_bytes)


def pack_pixels(pixels: list[list[int]]) -> bytes:
    """Pack a full screen of pixels into bytes.

    Args:
        pixels: 2D list of color indices, shape (300, 400).

    Returns:
        30000 bytes of packed pixel data.
    """
    return b"".join(pack_row(row) for row in pixels)


def split_blocks(packed: bytes) -> list[bytes]:
    """Split packed pixel data into 15 blocks of 2000 bytes each.

    Args:
        packed: 30000 bytes of packed pixel data.

    Returns:
        List of 15 blocks, each 2000 bytes.
    """
    return [
        packed[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE] for i in range(NUM_BLOCKS)
    ]


def compress_block(block: bytes) -> bytes:
    """Compress a 2000-byte block using LZO1X-1.

    Args:
        block: 2000 bytes of uncompressed block data.

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


def encode_image(pixels: list[list[int]]) -> list[list[Apdu]]:
    """Encode a full image into APDU commands ready for transmission.

    Args:
        pixels: 2D list of color indices, shape (300, 400).
            Values: 0=Black, 1=White, 2=Yellow, 3=Red.

    Returns:
        List of 15 blocks, each containing a list of APDU tuples.
        Each APDU is (cla, ins, p1, p2, data).
    """
    packed = pack_pixels(pixels)
    blocks = split_blocks(packed)
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
