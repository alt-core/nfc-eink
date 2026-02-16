"""Tests for image encoding module."""

from lzallright import LZOCompressor

from nfc_eink.device import DeviceInfo
from nfc_eink.image import (
    compress_block,
    encode_image,
    make_fragments,
    pack_pixels,
    pack_row,
    rotate_cw90,
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
        pixels = [0] * 128
        result = pack_row(pixels, bits_per_pixel=1)
        assert len(result) == 16
        assert result == b"\x00" * 16

    def test_all_white(self):
        pixels = [1] * 128
        result = pack_row(pixels, bits_per_pixel=1)
        assert all(b == 0xFF for b in result)

    def test_packing_formula(self):
        """byte = p0 | (p1 << 1) | ... | (p7 << 7)"""
        pixels = [0] * 128
        # Rightmost 8 pixels (indices 120..127) -> byte 0
        pixels[120] = 1  # bit 0
        pixels[121] = 0  # bit 1
        pixels[122] = 1  # bit 2
        pixels[123] = 0  # bit 3
        pixels[124] = 0  # bit 4
        pixels[125] = 0  # bit 5
        pixels[126] = 0  # bit 6
        pixels[127] = 0  # bit 7
        result = pack_row(pixels, bits_per_pixel=1)
        expected = 1 | (0 << 1) | (1 << 2)  # 0b00000101 = 0x05
        assert result[0] == expected

    def test_right_to_left_byte_order(self):
        pixels = [0] * 128
        # Leftmost 8 pixels -> last byte
        for i in range(8):
            pixels[i] = 1
        result = pack_row(pixels, bits_per_pixel=1)
        assert result[15] == 0xFF
        assert all(b == 0 for b in result[:15])


class TestRotateCw90:
    def test_dimensions(self):
        pixels = [[0] * 296 for _ in range(128)]
        rotated = rotate_cw90(pixels)
        assert len(rotated) == 296
        assert len(rotated[0]) == 128

    def test_pixel_mapping(self):
        """CW 90: rotated[y'][x'] = pixels[H-1-x'][y']"""
        pixels = [[0] * 4 for _ in range(3)]
        # Place a marker at physical top-left (0, 0)
        pixels[0][0] = 1
        rotated = rotate_cw90(pixels)
        # After CW 90, top-left of physical -> top-right of internal
        assert rotated[0][2] == 1

    def test_simple_rotation(self):
        # Input 2x3:
        # [[1, 2, 3],
        #  [4, 5, 6]]
        pixels = [[1, 2, 3], [4, 5, 6]]
        rotated = rotate_cw90(pixels)
        # CW 90 should give 3x2:
        # [[4, 1],
        #  [5, 2],
        #  [6, 3]]
        assert rotated == [[4, 1], [5, 2], [6, 3]]


class TestPackPixels:
    def test_4color_output_size(self):
        pixels = [[1] * 400 for _ in range(300)]
        result = pack_pixels(pixels, bits_per_pixel=2)
        assert len(result) == 30000

    def test_2color_output_size(self):
        """After rotation, rows are 128 wide -> 16 bytes each, 296 rows."""
        pixels = [[1] * 128 for _ in range(296)]
        result = pack_pixels(pixels, bits_per_pixel=1)
        assert len(result) == 16 * 296  # 4736


class TestSplitBlocks:
    def test_4color_split(self):
        packed = b"\x00" * 30000
        blocks = split_blocks(packed, block_size=2000)
        assert len(blocks) == 15
        assert all(len(b) == 2000 for b in blocks)

    def test_2color_split(self):
        packed = b"\x00" * 4736
        blocks = split_blocks(packed, block_size=[2000, 2000, 736])
        assert len(blocks) == 3
        assert len(blocks[0]) == 2000
        assert len(blocks[1]) == 2000
        assert len(blocks[2]) == 736

    def test_preserves_data(self):
        packed = bytes(range(256)) * (30000 // 256) + bytes(range(30000 % 256))
        blocks = split_blocks(packed, block_size=2000)
        assert b"".join(blocks) == packed

    def test_list_preserves_data(self):
        packed = b"\xAA" * 2000 + b"\xBB" * 2000 + b"\xCC" * 736
        blocks = split_blocks(packed, block_size=[2000, 2000, 736])
        assert b"".join(blocks) == packed


class TestCompressBlock:
    def test_roundtrip(self):
        block = bytes(range(256)) * 8  # 2048 -> trim to 2000
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

    def test_2color_returns_3_blocks(self):
        pixels = [[1] * 296 for _ in range(128)]
        result = encode_image(pixels, DEVICE_2COLOR)
        assert len(result) == 3

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

    def test_4color_all_page0(self):
        """4-color device: all blocks use P1=0."""
        pixels = [[1] * 400 for _ in range(300)]
        result = encode_image(pixels, DEVICE_4COLOR)
        for block_apdus in result:
            for cla, ins, p1, p2, data in block_apdus:
                assert p1 == 0

    def test_2color_all_page0(self):
        """2-color device: all blocks use P1=0, blockNo=0,1,2."""
        pixels = [[1] * 296 for _ in range(128)]
        result = encode_image(pixels, DEVICE_2COLOR)
        assert len(result) == 3
        for block_apdus in result:
            for cla, ins, p1, p2, data in block_apdus:
                assert p1 == 0
        # blockNo = 0, 1, 2
        assert result[0][0][4][0] == 0
        assert result[1][0][4][0] == 1
        assert result[2][0][4][0] == 2

    def test_apdu_data_size_within_limit(self):
        pixels = [[0] * 296 for _ in range(128)]
        result = encode_image(pixels, DEVICE_2COLOR)
        for block_apdus in result:
            for cla, ins, p1, p2, data in block_apdus:
                assert len(data) <= MAX_FRAGMENT_DATA + 2
