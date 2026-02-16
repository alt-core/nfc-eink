"""Main API class for NFC e-ink card communication."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

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
    build_panel_type_apdu,
    build_poll_apdu,
    build_refresh_apdu,
    is_refresh_complete,
)

if TYPE_CHECKING:
    from PIL import Image


class EInkCard:
    """NFC e-ink card communication manager.

    Usage::

        # Auto-detect reader and wait for card
        with EInkCard() as card:
            card.send_image(Image.open("photo.png"))
            card.refresh()

        # Use an existing nfcpy tag
        card = EInkCard(tag=my_tag)
        card.authenticate()
        card.send_image(pixels_2d_array)
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

    def connect(self, reader: str = "usb") -> None:
        """Connect to an NFC reader and wait for a card.

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

        tag = self._clf.connect(rdwr={"on-connect": lambda tag: tag})
        if tag is None or tag is False:
            raise CommunicationError("No card detected")
        self._tag = tag

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
        """Send an APDU command via nfcpy.

        Args:
            cla: Class byte.
            ins: Instruction byte.
            p1: Parameter 1.
            p2: Parameter 2.
            data: Command data (optional).
            mrl: Maximum response length.
            check_status: If True, raise on non-9000 status.

        Returns:
            Response data bytes (excluding status word).

        Raises:
            CommunicationError: If no tag is connected.
            StatusWordError: If check_status is True and status != 9000.
        """
        if self._tag is None:
            raise CommunicationError("Not connected to a card")

        try:
            response = self._tag.send_apdu(
                cla, ins, p1, p2, data, mrl, check_status
            )
            return bytes(response) if response else b""
        except Exception as e:
            if "Type4TagCommandError" in type(e).__name__:
                raise StatusWordError(
                    getattr(e, "errno", 0x6F) >> 8,
                    getattr(e, "errno", 0x00) & 0xFF,
                ) from e
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

    def send_image(self, image: Any) -> None:
        """Send an image to the card.

        Accepts either a PIL Image (requires Pillow) or a 2D list of
        color indices (300 rows x 400 columns, values 0-3).

        Args:
            image: PIL Image or 2D list of color indices.

        Raises:
            CommunicationError: If sending fails.
            NfcEinkError: If image format is invalid.
        """
        # Check if it's a PIL Image
        try:
            from PIL import Image as PILImage

            if isinstance(image, PILImage.Image):
                from nfc_eink.convert import convert_image

                pixels = convert_image(image)
            else:
                pixels = image
        except ImportError:
            pixels = image

        apdus = encode_image(pixels)

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
        # Start refresh
        cla, ins, p1, p2, data = build_refresh_apdu()
        self._send_apdu(cla, ins, p1, p2, data)

        # Poll until complete
        cla, ins, p1, p2, data = build_poll_apdu()
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            response = self._send_apdu(cla, ins, p1, p2, data, mrl=1, check_status=False)
            if is_refresh_complete(response):
                return
            time.sleep(poll_interval)

        raise NfcEinkError(f"Screen refresh timed out after {timeout}s")

    def get_device_info(self) -> bytes:
        """Query device info.

        Returns:
            Raw device info bytes.
        """
        cla, ins, p1, p2, data = build_device_info_apdu()
        return self._send_apdu(cla, ins, p1, p2, data, mrl=256)

    def get_panel_type(self) -> str:
        """Query panel type.

        Returns:
            Panel type string (e.g. "4_color Screen").
        """
        cla, ins, p1, p2, data = build_panel_type_apdu()
        response = self._send_apdu(cla, ins, p1, p2, data, mrl=256)
        return response.decode("ascii", errors="replace")
