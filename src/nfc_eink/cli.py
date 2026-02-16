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
            di = card.device_info
            _click.echo(
                f"Card: {card.serial_number} "
                f"({di.width}x{di.height}, {di.num_colors} colors)"
            )

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
            di = card.device_info
            _click.echo(f"Serial:         {card.serial_number}")
            _click.echo(f"Screen:         {di.width}x{di.height}")
            _click.echo(f"Colors:         {di.num_colors}")
            _click.echo(f"Bits/pixel:     {di.bits_per_pixel}")
            _click.echo(f"Rows/block:     {di.rows_per_block}")
            _click.echo(f"Block size:     {di.block_size} bytes")
            _click.echo(f"Total blocks:   {di.num_blocks}")

    return cli


if __name__ == "__main__":
    main()
