"""Tests for protocol module."""

from nfc_eink.protocol import (
    BLOCK_SIZE,
    BYTES_PER_ROW,
    MAX_FRAGMENT_DATA,
    NUM_BLOCKS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    build_auth_apdu,
    build_image_apdu,
    build_panel_type_apdu,
    build_poll_apdu,
    build_refresh_apdu,
    is_refresh_complete,
)


class TestConstants:
    def test_screen_dimensions(self):
        assert SCREEN_WIDTH == 400
        assert SCREEN_HEIGHT == 300

    def test_block_layout(self):
        assert NUM_BLOCKS == 15
        assert BYTES_PER_ROW == 100
        assert BLOCK_SIZE == 2000

    def test_max_fragment(self):
        assert MAX_FRAGMENT_DATA == 250


class TestBuildAuthApdu:
    def test_auth_apdu_values(self):
        cla, ins, p1, p2, data = build_auth_apdu()
        assert cla == 0x00
        assert ins == 0x20
        assert p1 == 0x00
        assert p2 == 0x01
        assert data == b"\x20\x09\x12\x10"

    def test_auth_apdu_matches_spec(self):
        """Verify against spec: 0020 00010420091210."""
        cla, ins, p1, p2, data = build_auth_apdu()
        # Reconstruct raw APDU bytes: CLA INS P1 P2 Lc Data
        raw = bytes([cla, ins, p1, p2, len(data)]) + data
        assert raw == bytes.fromhex("00200001" + "04" + "20091210")


class TestBuildImageApdu:
    def test_final_fragment(self):
        cla, ins, p1, p2, data = build_image_apdu(0, 0, b"\xAA\xBB", is_final=True)
        assert cla == 0xF0
        assert ins == 0xD3
        assert p1 == 0x00
        assert p2 == 0x01  # final
        assert data == b"\x00\x00\xAA\xBB"

    def test_intermediate_fragment(self):
        _, _, _, p2, data = build_image_apdu(2, 0, b"\xFF" * 10, is_final=False)
        assert p2 == 0x00  # intermediate
        assert data[0] == 2  # blockNo
        assert data[1] == 0  # fragNo

    def test_page_parameter(self):
        _, _, p1, _, _ = build_image_apdu(0, 0, b"\x00", is_final=True, page=1)
        assert p1 == 1

    def test_spec_example1(self):
        """Verify against spec Example 1: F0D300011600000255555555552000000000000000B10000110000."""
        spec_hex = "F0D300011600000255555555552000000000000000B10000110000"
        spec_bytes = bytes.fromhex(spec_hex)
        # Parse: CLA=F0, INS=D3, P1=00, P2=01, Lc=16(22), Data=22 bytes
        # Data: blockNo=00, fragNo=00, compressed=20 bytes
        compressed_payload = spec_bytes[7:]  # after CLA INS P1 P2 Lc blockNo fragNo
        assert len(compressed_payload) == 20

        cla, ins, p1, p2, data = build_image_apdu(
            block_no=0, frag_no=0, fragment=compressed_payload, is_final=True
        )
        raw = bytes([cla, ins, p1, p2, len(data)]) + data
        assert raw == spec_bytes

    def test_spec_example2_first_fragment(self):
        """Verify against spec Example 2: F0D30000FC020002..."""
        # P2=00 (intermediate), Lc=FC(252), blockNo=02, fragNo=00
        fragment = b"\x00" * 250  # placeholder 250 bytes
        cla, ins, p1, p2, data = build_image_apdu(
            block_no=2, frag_no=0, fragment=fragment, is_final=False
        )
        assert p2 == 0x00
        assert len(data) == 252  # 2 + 250
        assert data[0] == 2  # blockNo
        assert data[1] == 0  # fragNo
        raw_header = bytes([cla, ins, p1, p2, len(data)])
        assert raw_header == bytes.fromhex("F0D30000FC")


class TestBuildRefreshApdu:
    def test_refresh_apdu(self):
        cla, ins, p1, p2, data = build_refresh_apdu()
        assert (cla, ins, p1, p2) == (0xF0, 0xD4, 0x85, 0x80)
        assert data is None

    def test_refresh_case2(self):
        """Refresh is Case 2 APDU: CLA INS P1 P2 Le=00."""
        cla, ins, p1, p2, data = build_refresh_apdu()
        assert data is None  # No Lc/data; caller passes mrl=256 for Le


class TestBuildPollApdu:
    def test_poll_apdu(self):
        cla, ins, p1, p2, data = build_poll_apdu()
        assert (cla, ins, p1, p2) == (0xF0, 0xDE, 0x00, 0x00)
        assert data is None

    def test_poll_case2(self):
        """Poll is Case 2 APDU: CLA INS P1 P2 Le=01."""
        cla, ins, p1, p2, data = build_poll_apdu()
        assert data is None  # No Lc/data; caller passes mrl=1 for Le


class TestBuildPanelTypeApdu:
    def test_panel_type_apdu(self):
        """Verify against spec: F0D8 000005000000000E."""
        cla, ins, p1, p2, data = build_panel_type_apdu()
        # Reconstruct raw APDU: CLA INS P1 P2 Lc Data
        raw = bytes([cla, ins, p1, p2, len(data)]) + data
        assert raw == bytes.fromhex("F0D8000005000000000E")

    def test_2color_panel_type(self):
        """2-color device: 4 blocks, max blockNo=3."""
        cla, ins, p1, p2, data = build_panel_type_apdu(num_blocks=4)
        assert data == b"\x00\x00\x00\x00\x03"


class TestIsRefreshComplete:
    def test_complete(self):
        assert is_refresh_complete(b"\x00") is True

    def test_still_refreshing(self):
        assert is_refresh_complete(b"\x01") is False
