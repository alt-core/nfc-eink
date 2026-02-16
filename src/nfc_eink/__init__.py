"""nfc_eink - Python library for NFC e-ink card displays."""

from nfc_eink.card import EInkCard
from nfc_eink.device import DeviceInfo
from nfc_eink.exceptions import (
    AuthenticationError,
    CommunicationError,
    ImageSizeError,
    NfcEinkError,
    StatusWordError,
)
from nfc_eink.image import encode_image

__all__ = [
    "EInkCard",
    "DeviceInfo",
    "encode_image",
    "NfcEinkError",
    "CommunicationError",
    "AuthenticationError",
    "StatusWordError",
    "ImageSizeError",
]
