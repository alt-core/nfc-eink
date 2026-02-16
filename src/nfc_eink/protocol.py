"""APDU command construction and response parsing for NFC e-ink cards.

This module handles the ISO7816 APDU protocol without any NFC I/O.
All functions return tuples of (cla, ins, p1, p2, data) suitable for
passing to nfcpy's tag.send_apdu().
"""

from __future__ import annotations

# Screen constants
SCREEN_WIDTH: int = 400
SCREEN_HEIGHT: int = 300
BLOCK_ROWS: int = 20
NUM_BLOCKS: int = SCREEN_HEIGHT // BLOCK_ROWS  # 15
BYTES_PER_ROW: int = SCREEN_WIDTH // 4  # 100
BLOCK_SIZE: int = BYTES_PER_ROW * BLOCK_ROWS  # 2000
MAX_FRAGMENT_DATA: int = 250  # 0xFC - 2 (blockNo + fragNo)

# APDU type alias
Apdu = tuple[int, int, int, int, bytes]


def build_auth_apdu() -> Apdu:
    """Build the authentication APDU.

    Returns:
        (cla=0x00, ins=0x20, p1=0x00, p2=0x01, data=b'\\x20\\x09\\x12\\x10')
    """
    return (0x00, 0x20, 0x00, 0x01, b"\x20\x09\x12\x10")


def build_image_apdu(
    block_no: int, frag_no: int, fragment: bytes, is_final: bool,
    page: int = 0,
) -> Apdu:
    """Build an image data transfer APDU (F0D3).

    Args:
        block_no: Block number within the page (0-based).
        frag_no: Fragment number within the block (0..).
        fragment: Compressed image fragment (max 250 bytes).
        is_final: True if this is the last fragment of the block.
        page: Page selector (P1). 0 for single-page devices or upper half,
              1 for lower half on 2-page devices.

    Returns:
        APDU tuple for image transfer.
    """
    p2 = 0x01 if is_final else 0x00
    data = bytes([block_no, frag_no]) + fragment
    return (0xF0, 0xD3, page, p2, data)


def build_refresh_apdu() -> tuple[int, int, int, int, None]:
    """Build the screen refresh start APDU (F0D4).

    This is a Case 2 APDU (no command data, expects response).

    Returns:
        APDU tuple for starting screen refresh (data=None).
    """
    return (0xF0, 0xD4, 0x85, 0x80, None)


def build_poll_apdu() -> tuple[int, int, int, int, None]:
    """Build the refresh polling APDU (F0DE).

    This is a Case 2 APDU (no command data, expects 1-byte response).

    Returns:
        APDU tuple for polling refresh status (data=None).
    """
    return (0xF0, 0xDE, 0x00, 0x00, None)


def build_device_info_apdu() -> tuple[int, int, int, int, None]:
    """Build the device info APDU (00D1).

    Returns:
        APDU tuple for querying device info.
    """
    return (0x00, 0xD1, 0x00, 0x00, None)


def build_panel_type_apdu() -> Apdu:
    """Build the panel type query APDU (F0D8).

    Returns:
        APDU tuple for querying panel type.
    """
    return (0xF0, 0xD8, 0x00, 0x00, b"\x05\x00\x00\x00\x00\x0E")


def is_refresh_complete(response: bytes) -> bool:
    """Parse a poll response to check if screen refresh is complete.

    Args:
        response: Response data from poll APDU (1 byte, excluding status word).

    Returns:
        True if refresh is complete (0x00), False if still refreshing (0x01).
    """
    return response[0] == 0x00
