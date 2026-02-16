"""Tests for image encoding module."""

from lzallright import LZOCompressor

from nfc_eink.device import DeviceInfo
from nfc_eink.image import (
    compress_block,
    encode_image,
    make_fragments,
    pack_pixels,
    pack_row,
    split_blocks,
)
from nfc_eink.protocol import MAX_FRAGMENT_DATA

# Test device profiles
DEVICE_4COLOR = DeviceInfo(
    width=400, height=300, bits_per_pixel=2,
    rows_per_block=20, serial_number="TEST4C",
)
DEVICE_2COLOR = DeviceInfo(
    width=296, height=128, bits_per_pixel=1,
    rows_per_block=32, serial_number="TEST2C",
)


class TestPackRow4Color:
    """Tests for 4-color (2bpp) packing."""

    def test_all_black(self):
        pixels = [0] * 400
        result = pack_row(pixels, bits_per_pixel=2)
        assert len(result) == 100
        assert result == b"\x00" * 100

    def test_all_white(self):
        pixels = [1] * 400
        result = pack_row(pixels, bits_per_pixel=2)
        assert all(b == 0x55 for b in result)

    def test_all_red(self):
        pixels = [3] * 400
        result = pack_row(pixels, bits_per_pixel=2)
        assert result == b"\xFF" * 100

    def test_packing_formula(self):
        """byte = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)"""
        pixels = [0] * 400
        pixels[396] = 0
        pixels[397] = 1
        pixels[398] = 2
        pixels[399] = 3
        result = pack_row(pixels, bits_per_pixel=2)
        expected = 0 | (1 << 2) | (2 << 4) | (3 << 6)
        assert result[0] == expected

    def test_right_to_left_byte_order(self):
        pixels = [0] * 400
        pixels[0] = 3
        pixels[1] = 3
        pixels[2] = 3
        pixels[3] = 3
        result = pack_row(pixels, bits_per_pixel=2)
        assert result[99] == 0xFF
        assert all(b == 0 for b in result[:99])


class TestPackRow2Color:
    """Tests for 2-color (1bpp) packing."""

    def test_all_black(self):
        pixels = [0] * 296
        result = pack_row(pixels, bits_per_pixel=1)
        assert len(result) == 37
        assert result == b"\x00" * 37

    def test_all_white(self):
        pixels = [1] * 296
        result = pack_row(pixels, bits_per_pixel=1)
        assert all(b == 0xFF for b in result)

    def test_packing_formula(self):
        """byte = p0 | (p1 << 1) | ... | (p7 << 7)"""
        pixels = [0] * 296
        # Rightmost 8 pixels (indices 288..295) → byte 0
        pixels[288] = 1  # bit 0
        pixels[289] = 0  # bit 1
        pixels[290] = 1  # bit 2
        pixels[291] = 0  # bit 3
        pixels[292] = 0  # bit 4
        pixels[293] = 0  # bit 5
        pixels[294] = 0  # bit 6
        pixels[295] = 0  # bit 7
        result = pack_row(pixels, bits_per_pixel=1)
        expected = 1 | (0 << 1) | (1 << 2)  # 0b00000101 = 0x05
        assert result[0] == expected

    def test_right_to_left_byte_order(self):
        pixels = [0] * 296
        # Leftmost 8 pixels → last byte
        for i in range(8):
            pixels[i] = 1
        result = pack_row(pixels, bits_per_pixel=1)
        assert result[36] == 0xFF
        assert all(b == 0 for b in result[:36])


class TestPackPixels:
    def test_4color_output_size(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = pack_pixels(pixels, bits_per_pixel=2)
        assert len(result) == 30000

    def test_2color_output_size(self):
        pixels = [[1] * 296 for _ in range(128)]
        result = pack_pixels(pixels, bits_per_pixel=1)
        assert len(result) == 37 * 128  # 4736


class TestSplitBlocks:
    def test_4color_split(self):
        packed = b"\x00" * 30000
        blocks = split_blocks(packed, block_size=2000)
        assert len(blocks) == 15
        assert all(len(b) == 2000 for b in blocks)

    def test_2color_split(self):
        packed = b"\x00" * 4736
        blocks = split_blocks(packed, block_size=1184)
        assert len(blocks) == 4
        assert all(len(b) == 1184 for b in blocks)

    def test_preserves_data(self):
        packed = bytes(range(256)) * (30000 // 256) + bytes(range(30000 % 256))
        blocks = split_blocks(packed, block_size=2000)
        assert b"".join(blocks) == packed


class TestCompressBlock:
    def test_roundtrip(self):
        block = bytes(range(256)) * 8  # 2048 → trim to 2000
        block = block[:2000]
        compressed = compress_block(block)
        decompressed = LZOCompressor.decompress(compressed, output_size_hint=2000)
        assert decompressed == block

    def test_uniform_compresses_small(self):
        block = b"\x55" * 2000
        compressed = compress_block(block)
        assert len(compressed) < 2000


class TestMakeFragments:
    def test_small_data_single_fragment(self):
        data = b"\x00" * 100
        fragments = make_fragments(data)
        assert len(fragments) == 1

    def test_max_fragment_size(self):
        data = b"\x00" * 600
        fragments = make_fragments(data)
        assert all(len(f) <= MAX_FRAGMENT_DATA for f in fragments)

    def test_concatenation_equals_original(self):
        data = b"\xAB" * 700
        fragments = make_fragments(data)
        assert b"".join(fragments) == data


class TestEncodeImage:
    def test_4color_returns_15_blocks(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels, DEVICE_4COLOR)
        assert len(result) == 15

    def test_2color_returns_4_blocks(self):
        pixels = [[1] * 296 for _ in range(128)]
        result = encode_image(pixels, DEVICE_2COLOR)
        assert len(result) == 4

    def test_last_fragment_is_final(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels, DEVICE_4COLOR)
        for block_apdus in result:
            *_, last = block_apdus
            assert last[3] == 0x01  # p2 = final
            for apdu in block_apdus[:-1]:
                assert apdu[3] == 0x00

    def test_default_device_info(self):
        """encode_image with device_info=None uses 400x300 4-color defaults."""
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels)
        assert len(result) == 15

    def test_apdu_data_size_within_limit(self):
        pixels = [[0] * 296 for _ in range(128)]
        result = encode_image(pixels, DEVICE_2COLOR)
        for block_apdus in result:
            for cla, ins, p1, p2, data in block_apdus:
                assert len(data) <= MAX_FRAGMENT_DATA + 2
