"""Exception classes for nfc_eink."""


class NfcEinkError(Exception):
    """Base exception for nfc_eink library."""


class CommunicationError(NfcEinkError):
    """NFC communication failure."""


class AuthenticationError(NfcEinkError):
    """Card authentication failed."""


class StatusWordError(NfcEinkError):
    """Unexpected ISO7816 status word received.

    Attributes:
        sw1: Status word byte 1.
        sw2: Status word byte 2.
    """

    def __init__(self, sw1: int, sw2: int) -> None:
        self.sw1 = sw1
        self.sw2 = sw2
        super().__init__(f"Status word error: {sw1:02X}{sw2:02X}")


class ImageSizeError(NfcEinkError):
    """Image dimensions do not match expected screen size."""
