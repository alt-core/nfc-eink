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
    def clear() -> None:
        """Clear the display to white."""
        from nfc_eink.card import EInkCard

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            di = card.device_info
            _click.echo(
                f"Card: {card.serial_number} "
                f"({di.width}x{di.height}, {di.num_colors} colors)"
            )

            # All-white pixel array (color index 1 = white)
            pixels = [[1] * di.width for _ in range(di.height)]
            _click.echo("Sending white image...")
            card.send_image(pixels)

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
            _click.echo(f"Rotated FB:     {di.rotated}")
            _click.echo(f"Framebuffer:    {di.fb_width}x{di.fb_height}")
            _click.echo(f"Blocks:         {di.num_blocks} ({'+'.join(str(s) for s in di.block_sizes)} bytes)")

    @cli.command()
    @_click.argument("scenario", default="black")
    def diag(scenario: str) -> None:
        """Basic device diagnostics.

        \b
        Scenarios:
          black   - Fill screen with BLACK (raw block transfer test)
          stripe  - Alternating B/W stripes per block (block mapping test)
        """
        from nfc_eink.card import EInkCard
        from nfc_eink.image import compress_block, make_fragments

        scenario = scenario.lower()

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            di = card.device_info
            _click.echo(
                f"Card: {card.serial_number} "
                f"({di.width}x{di.height}, {di.num_colors} colors)"
            )
            _click.echo(
                f"Blocks: {di.num_blocks} "
                f"({'+'.join(str(s) for s in di.block_sizes)} bytes)"
            )

            def send_block(block_no: int, raw_data: bytes) -> None:
                comp = compress_block(raw_data)
                frags = make_fragments(comp)
                for frag_no, frag in enumerate(frags):
                    is_final = frag_no == len(frags) - 1
                    p2 = 0x01 if is_final else 0x00
                    data = bytes([block_no, frag_no]) + frag
                    card._send_apdu(0xF0, 0xD3, 0, p2, data)

            if scenario == "black":
                _click.echo("\n--- Fill all blocks with BLACK ---")
                for blk_no, size in enumerate(di.block_sizes):
                    send_block(blk_no, b"\x00" * size)
                    _click.echo(f"  blk={blk_no} ({size}B): OK")

            elif scenario == "stripe":
                _click.echo("\n--- Alternating B/W stripes ---")
                for blk_no, size in enumerate(di.block_sizes):
                    fill = 0x00 if blk_no % 2 == 0 else 0xFF
                    label = "BLACK" if fill == 0x00 else "WHITE"
                    send_block(blk_no, bytes([fill]) * size)
                    _click.echo(f"  blk={blk_no} ({size}B) = {label}: OK")

            else:
                _click.echo(f"Unknown scenario: {scenario}")
                _click.echo("Available: black, stripe")
                return

            _click.echo("Refreshing...")
            card.refresh()
            _click.echo("Done!")

    return cli


if __name__ == "__main__":
    main()
