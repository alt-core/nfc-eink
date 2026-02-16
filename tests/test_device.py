"""Tests for device info parsing."""

from nfc_eink.device import DeviceInfo, parse_device_info, parse_tlv

# Actual response from 296x128 2-color device (SEAA000282)
SAMPLE_RESPONSE = bytes.fromhex(
    "a007f0012000800128"
    "a10700120030ffffffb1012eb20114b30100"
    "c00a53454141303030323832"
    "c10422ab5052"
    "d10701200000000000"
)


class TestParseTlv:
    def test_parses_all_tags(self):
        tlv = parse_tlv(SAMPLE_RESPONSE)
        assert 0xA0 in tlv
        assert 0xA1 in tlv
        assert 0xB1 in tlv
        assert 0xB2 in tlv
        assert 0xB3 in tlv
        assert 0xC0 in tlv
        assert 0xC1 in tlv
        assert 0xD1 in tlv

    def test_tag_lengths(self):
        tlv = parse_tlv(SAMPLE_RESPONSE)
        assert len(tlv[0xA0]) == 7
        assert len(tlv[0xC0]) == 10

    def test_empty_data(self):
        assert parse_tlv(b"") == {}

    def test_truncated_data(self):
        # Tag + length but value truncated
        tlv = parse_tlv(b"\xA0\x07\x01\x02")
        assert 0xA0 not in tlv


class TestParseDeviceInfo:
    def test_dimensions(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.width == 296
        assert info.height == 128

    def test_color_depth(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.bits_per_pixel == 1
        assert info.num_colors == 2

    def test_block_structure(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.rows_per_block == 32
        # Framebuffer: 128-wide x 296-tall (rotated), 3 blocks
        assert info.num_blocks == 3
        assert info.block_sizes == [2000, 2000, 736]

    def test_serial_number(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.serial_number == "SEAA000282"

    def test_pixels_per_byte(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.pixels_per_byte == 8  # 1bpp

    def test_bytes_per_row(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.bytes_per_row == 37  # 296 / 8

    def test_raw_preserved(self):
        info = parse_device_info(SAMPLE_RESPONSE)
        assert info.raw == SAMPLE_RESPONSE

    def test_missing_a0_tag(self):
        import pytest

        with pytest.raises(ValueError):
            parse_device_info(b"\xC0\x04TEST")


class TestDeviceInfoProperties:
    def test_4color_device(self):
        """Verify properties for a hypothetical 400x300 4-color device."""
        info = DeviceInfo(
            width=400, height=300, bits_per_pixel=2,
            rows_per_block=20, serial_number="TEST001",
        )
        assert info.num_colors == 4
        assert info.pixels_per_byte == 4
        assert info.bytes_per_row == 100
        assert info.rotated is False
        assert info.fb_width == 400
        assert info.fb_height == 300
        assert info.fb_bytes_per_row == 100
        assert info.fb_total_bytes == 30000
        assert info.block_sizes == [2000] * 15
        assert info.num_blocks == 15

    def test_2color_device(self):
        """Verify properties for a 296x128 2-color device."""
        info = DeviceInfo(
            width=296, height=128, bits_per_pixel=1,
            rows_per_block=32, serial_number="TEST002",
        )
        assert info.num_colors == 2
        assert info.pixels_per_byte == 8
        assert info.bytes_per_row == 37
        assert info.rotated is True
        assert info.fb_width == 128
        assert info.fb_height == 296
        assert info.fb_bytes_per_row == 16
        assert info.fb_total_bytes == 4736
        assert info.block_sizes == [2000, 2000, 736]
        assert info.num_blocks == 3
