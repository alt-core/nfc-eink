"""CLI for NFC e-ink card."""

from __future__ import annotations

import sys


def main() -> None:
    """Entry point for the nfc-eink CLI."""
    try:
        import click
    except ImportError:
        print("CLI requires click: pip install nfc-eink[cli]", file=sys.stderr)
        sys.exit(1)

    _build_cli(click).standalone_mode = True
    _build_cli(click)()


def _build_cli(click: object) -> object:
    """Build the Click CLI group (deferred to avoid import-time dependency)."""
    import click as _click

    @_click.group()
    def cli() -> None:
        """NFC e-ink card tool."""

    @cli.command()
    @_click.argument("image_path", type=_click.Path(exists=True))
    def send(image_path: str) -> None:
        """Send an image to the e-ink card and refresh the display."""
        from PIL import Image

        from nfc_eink.card import EInkCard

        _click.echo(f"Loading image: {image_path}")
        image = Image.open(image_path)

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            _click.echo("Card detected. Authenticating...")
            card.authenticate()

            _click.echo("Sending image...")
            card.send_image(image)

            _click.echo("Refreshing display...")
            card.refresh()

            _click.echo("Done!")

    @cli.command()
    def info() -> None:
        """Show device information."""
        from nfc_eink.card import EInkCard

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            card.authenticate()

            panel = card.get_panel_type()
            _click.echo(f"Panel type: {panel}")

            device_info = card.get_device_info()
            _click.echo(f"Device info: {device_info.hex()}")

    return cli


if __name__ == "__main__":
    main()
