"""Main API class for NFC e-ink card communication."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from nfc_eink.device import DeviceInfo, parse_device_info
from nfc_eink.exceptions import (
    AuthenticationError,
    CommunicationError,
    NfcEinkError,
    StatusWordError,
)
from nfc_eink.image import encode_image
from nfc_eink.protocol import (
    build_auth_apdu,
    build_device_info_apdu,
    build_poll_apdu,
    build_refresh_apdu,
    is_refresh_complete,
)

if TYPE_CHECKING:
    from PIL import Image


class EInkCard:
    """NFC e-ink card communication manager.

    On connect, the card is automatically authenticated and device info
    is read, making serial_number and device_info immediately available.

    Usage::

        with EInkCard() as card:
            print(card.serial_number)
            card.send_image(Image.open("photo.png"))
            card.refresh()
    """

    def __init__(self, tag: Any = None) -> None:
        """Initialize EInkCard.

        Args:
            tag: An nfcpy Type4Tag object. If None, call connect() to
                auto-detect a reader and wait for a card.
        """
        self._tag = tag
        self._clf: Any = None
        self._device_info: DeviceInfo | None = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Detected device information, available after connect."""
        return self._device_info

    @property
    def serial_number(self) -> str:
        """Per-device identifier string from C0 tag, available after connect."""
        if self._device_info is None:
            return ""
        return self._device_info.serial_number

    def connect(self, reader: str = "usb") -> None:
        """Connect to an NFC reader, wait for a card, authenticate, and read device info.

        Blocks until a card is detected on the reader.

        Args:
            reader: nfcpy device path (default: 'usb' for USB readers).

        Raises:
            CommunicationError: If no reader is found or connection fails.
        """
        try:
            import nfc
        except ImportError as e:
            raise CommunicationError(
                "nfcpy is required: pip install nfcpy"
            ) from e

        try:
            self._clf = nfc.ContactlessFrontend(reader)
        except IOError as e:
            raise CommunicationError(f"Cannot open NFC reader '{reader}': {e}") from e

        def on_connect(tag: Any) -> bool:
            self._tag = tag
            return False  # Return False so connect() returns immediately with the tag

        tag = self._clf.connect(rdwr={"on-connect": on_connect})
        if tag is None or self._tag is None:
            raise CommunicationError("No card detected")

        self.authenticate()
        self._read_device_info()

    def _read_device_info(self) -> None:
        """Read and parse device info from the card."""
        cla, ins, p1, p2, data = build_device_info_apdu()
        raw = self._send_apdu(cla, ins, p1, p2, data, mrl=256)
        self._device_info = parse_device_info(raw)

    def close(self) -> None:
        """Close the NFC connection."""
        if self._clf is not None:
            self._clf.close()
            self._clf = None
        self._tag = None

    def __enter__(self) -> EInkCard:
        if self._tag is None:
            self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    def _send_apdu(
        self,
        cla: int,
        ins: int,
        p1: int,
        p2: int,
        data: bytes | None = None,
        mrl: int = 0,
        check_status: bool = True,
    ) -> bytes:
        """Send an APDU command via nfcpy."""
        if self._tag is None:
            raise CommunicationError("Not connected to a card")

        try:
            response = self._tag.send_apdu(
                cla, ins, p1, p2, data, mrl, check_status
            )
            return bytes(response) if response else b""
        except Exception as e:
            err_name = type(e).__name__
            if "TimeoutError" in err_name or "timeout" in str(e).lower():
                raise CommunicationError(
                    "Card communication timed out (card may have been removed)"
                ) from e
            if "Type4TagCommandError" in err_name:
                errno = getattr(e, "errno", 0)
                if errno == 0:
                    raise CommunicationError(
                        "Card communication lost"
                    ) from e
                raise StatusWordError(errno >> 8, errno & 0xFF) from e
            raise CommunicationError(f"APDU command failed: {e}") from e

    def authenticate(self) -> None:
        """Authenticate with the card.

        Raises:
            AuthenticationError: If authentication fails.
        """
        cla, ins, p1, p2, data = build_auth_apdu()
        try:
            self._send_apdu(cla, ins, p1, p2, data)
        except (StatusWordError, CommunicationError) as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e

    def send_image(
        self,
        image: Any,
        dither: str = "pillow",
        resize: str = "fit",
        palette: str = "pure",
    ) -> None:
        """Send an image to the card.

        Accepts either a PIL Image (requires Pillow) or a 2D list of
        color indices matching the device's screen dimensions.
        Image encoding parameters are automatically determined from device info.

        Args:
            image: PIL Image or 2D list of color indices.
            dither: Dithering algorithm for PIL Image conversion.
                One of 'pillow' (default), 'atkinson', 'floyd-steinberg',
                'jarvis', 'stucki', 'none'.
            resize: Resize mode for PIL Image conversion.
                'fit' (default) adds white margins, 'cover' crops excess.
            palette: Palette mode for PIL Image conversion.
                'pure' (default) uses ideal RGB values.
                'measured' uses colors from an actual e-ink panel.

        Raises:
            CommunicationError: If sending fails.
            NfcEinkError: If image format is invalid.
        """
        is_pil = False
        try:
            from PIL import Image as PILImage

            is_pil = isinstance(image, PILImage.Image)
        except ImportError:
            pass

        if is_pil:
            from nfc_eink.convert import convert_image

            di = self._device_info
            if di is not None:
                pixels = convert_image(
                    image, di.width, di.height, di.num_colors,
                    dither=dither, resize=resize, palette=palette,
                )
            else:
                pixels = convert_image(
                    image, dither=dither, resize=resize, palette=palette,
                )
        else:
            pixels = image

        apdus = encode_image(pixels, self._device_info)

        for block_apdus in apdus:
            for cla, ins, p1, p2, data in block_apdus:
                self._send_apdu(cla, ins, p1, p2, data)

    def refresh(self, timeout: float = 30.0, poll_interval: float = 0.5) -> None:
        """Start screen refresh and wait for completion.

        Args:
            timeout: Maximum seconds to wait for refresh (default 30).
            poll_interval: Seconds between poll attempts (default 0.5).

        Raises:
            NfcEinkError: If refresh times out.
            CommunicationError: If communication fails during refresh.
        """
        cla, ins, p1, p2, data = build_refresh_apdu()
        self._send_apdu(cla, ins, p1, p2, data, mrl=256)

        cla, ins, p1, p2, data = build_poll_apdu()
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            response = self._send_apdu(cla, ins, p1, p2, data, mrl=1, check_status=False)
            if is_refresh_complete(response):
                return
            time.sleep(poll_interval)

        raise NfcEinkError(f"Screen refresh timed out after {timeout}s")
