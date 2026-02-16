"""Tests for image encoding module."""

from lzallright import LZOCompressor

from nfc_eink.image import (
    compress_block,
    encode_image,
    make_fragments,
    pack_pixels,
    pack_row,
    split_blocks,
)
from nfc_eink.protocol import BLOCK_SIZE, BYTES_PER_ROW, MAX_FRAGMENT_DATA, NUM_BLOCKS


class TestPackRow:
    def test_all_black(self):
        """All pixels = 0 (black) → all bytes = 0x00."""
        pixels = [0] * 400
        result = pack_row(pixels)
        assert len(result) == BYTES_PER_ROW
        assert result == b"\x00" * 100

    def test_all_white(self):
        """All pixels = 1 (white) → each byte = 0b01010101 = 0x55."""
        pixels = [1] * 400
        result = pack_row(pixels)
        assert len(result) == BYTES_PER_ROW
        assert all(b == 0x55 for b in result)

    def test_all_red(self):
        """All pixels = 3 (red) → each byte = 0b11111111 = 0xFF."""
        pixels = [3] * 400
        result = pack_row(pixels)
        assert result == b"\xFF" * 100

    def test_packing_formula(self):
        """Verify byte = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)."""
        # Rightmost 4 pixels (indices 396..399) → byte 0
        pixels = [0] * 400
        pixels[396] = 0  # p0
        pixels[397] = 1  # p1
        pixels[398] = 2  # p2
        pixels[399] = 3  # p3
        result = pack_row(pixels)
        expected = 0 | (1 << 2) | (2 << 4) | (3 << 6)  # 0b11100100 = 0xE4
        assert result[0] == expected

    def test_right_to_left_byte_order(self):
        """Byte 0 = rightmost pixels, byte 99 = leftmost pixels."""
        pixels = [0] * 400
        # Set leftmost 4 pixels (indices 0..3) to red (3)
        pixels[0] = 3
        pixels[1] = 3
        pixels[2] = 3
        pixels[3] = 3
        result = pack_row(pixels)
        # Should be in byte 99 (last byte, rightmost in packed data = leftmost pixels)
        assert result[99] == 0xFF
        # All other bytes should be 0
        assert all(b == 0 for b in result[:99])

    def test_output_length(self):
        pixels = [1] * 400
        assert len(pack_row(pixels)) == 100


class TestPackPixels:
    def test_output_size(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = pack_pixels(pixels)
        assert len(result) == 30000

    def test_white_screen(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = pack_pixels(pixels)
        assert all(b == 0x55 for b in result)


class TestSplitBlocks:
    def test_correct_split(self):
        packed = b"\x00" * 30000
        blocks = split_blocks(packed)
        assert len(blocks) == NUM_BLOCKS
        assert all(len(b) == BLOCK_SIZE for b in blocks)

    def test_preserves_data(self):
        packed = bytes(range(256)) * (30000 // 256) + bytes(range(30000 % 256))
        blocks = split_blocks(packed)
        reassembled = b"".join(blocks)
        assert reassembled == packed


class TestCompressBlock:
    def test_compress_decompress_roundtrip(self):
        block = bytes(range(256)) * (BLOCK_SIZE // 256) + bytes(
            range(BLOCK_SIZE % 256)
        )
        compressed = compress_block(block)
        decompressed = LZOCompressor.decompress(compressed, output_size_hint=BLOCK_SIZE)
        assert decompressed == block

    def test_uniform_block_compresses_small(self):
        block = b"\x55" * BLOCK_SIZE
        compressed = compress_block(block)
        assert len(compressed) < BLOCK_SIZE


class TestMakeFragments:
    def test_small_data_single_fragment(self):
        data = b"\x00" * 100
        fragments = make_fragments(data)
        assert len(fragments) == 1
        assert fragments[0] == data

    def test_max_fragment_size(self):
        data = b"\x00" * 600
        fragments = make_fragments(data)
        assert all(len(f) <= MAX_FRAGMENT_DATA for f in fragments)

    def test_concatenation_equals_original(self):
        data = b"\xAB" * 700
        fragments = make_fragments(data)
        assert b"".join(fragments) == data

    def test_exact_boundary(self):
        data = b"\x00" * MAX_FRAGMENT_DATA
        fragments = make_fragments(data)
        assert len(fragments) == 1
        assert len(fragments[0]) == MAX_FRAGMENT_DATA

    def test_one_over_boundary(self):
        data = b"\x00" * (MAX_FRAGMENT_DATA + 1)
        fragments = make_fragments(data)
        assert len(fragments) == 2
        assert len(fragments[0]) == MAX_FRAGMENT_DATA
        assert len(fragments[1]) == 1


class TestEncodeImage:
    def test_returns_15_blocks(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels)
        assert len(result) == NUM_BLOCKS

    def test_each_block_has_at_least_one_apdu(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels)
        for block_apdus in result:
            assert len(block_apdus) >= 1

    def test_last_fragment_is_final(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels)
        for block_apdus in result:
            # Last APDU: P2 should be 0x01 (final)
            *_, last = block_apdus
            assert last[3] == 0x01  # p2 = final
            # All others: P2 should be 0x00 (intermediate)
            for apdu in block_apdus[:-1]:
                assert apdu[3] == 0x00

    def test_apdu_data_size_within_limit(self):
        pixels = [[0] * 400 for _ in range(300)]
        result = encode_image(pixels)
        for block_apdus in result:
            for cla, ins, p1, p2, data in block_apdus:
                # data = blockNo(1) + fragNo(1) + fragment(<=250)
                assert len(data) <= MAX_FRAGMENT_DATA + 2

    def test_block_numbers_sequential(self):
        pixels = [[0] * 400 for _ in range(300)]
        result = encode_image(pixels)
        for block_no, block_apdus in enumerate(result):
            for apdu in block_apdus:
                assert apdu[4][0] == block_no  # data[0] = blockNo
