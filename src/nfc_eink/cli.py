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

    @cli.command()
    @_click.argument("scenario", default="S1")
    def diag(scenario: str) -> None:
        """Diagnose image transfer. Scenarios: S1, S2, S5, S6."""
        from nfc_eink.card import EInkCard
        from nfc_eink.image import compress_block

        scenario = scenario.upper()

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            di = card.device_info
            _click.echo(
                f"Card: {card.serial_number} "
                f"({di.width}x{di.height}, {di.num_colors} colors)"
            )

            white = compress_block(b"\xff" * di.block_size)

            def send_d(p1: int, block_no: int) -> str:
                """Send F0D3 with given P1 and blockNo. Returns 'OK' or SW."""
                data = bytes([block_no, 0]) + white
                try:
                    card._send_apdu(0xF0, 0xD3, p1, 0x01, data)
                    return "OK"
                except Exception as e:
                    return str(e)

            if scenario == "S1":
                _click.echo("\n--- S1: blockNo=2 alone (no prior blocks) ---")
                _click.echo(f"  D(P1=0,blk=2): {send_d(0, 2)}")

            elif scenario == "S2":
                _click.echo("\n--- S2: P1 page switch (blockNo reset) ---")
                _click.echo("  D(P1=0,blk=0) D(P1=0,blk=1) D(P1=1,blk=0) D(P1=1,blk=1)")
                for p1, blk in [(0, 0), (0, 1), (1, 0), (1, 1)]:
                    result = send_d(p1, blk)
                    _click.echo(f"  D(P1={p1},blk={blk}): {result}")
                    if result != "OK":
                        break

            elif scenario == "S5":
                _click.echo("\n--- S5: Refresh Case3 (current: data=0x00) ---")
                _click.echo("  Sending 4 blocks first (S2 pattern)...")
                for p1, blk in [(0, 0), (0, 1), (1, 0), (1, 1)]:
                    result = send_d(p1, blk)
                    _click.echo(f"  D(P1={p1},blk={blk}): {result}")
                    if result != "OK":
                        _click.echo("  Image transfer failed, skipping refresh.")
                        return
                _click.echo("  Refresh (Case3: data=0x00)...")
                try:
                    card._send_apdu(0xF0, 0xD4, 0x85, 0x80, b"\x00")
                    _click.echo("  Refresh: OK")
                except Exception as e:
                    _click.echo(f"  Refresh: {e}")

            elif scenario == "S6":
                _click.echo("\n--- S6: Refresh Case2 (data=None, Le=256) ---")
                _click.echo("  Sending 4 blocks first (S2 pattern)...")
                for p1, blk in [(0, 0), (0, 1), (1, 0), (1, 1)]:
                    result = send_d(p1, blk)
                    _click.echo(f"  D(P1={p1},blk={blk}): {result}")
                    if result != "OK":
                        _click.echo("  Image transfer failed, skipping refresh.")
                        return
                _click.echo("  Refresh (Case2: Le=0x00)...")
                try:
                    card._send_apdu(0xF0, 0xD4, 0x85, 0x80, None, mrl=256)
                    _click.echo("  Refresh: OK")
                except Exception as e:
                    _click.echo(f"  Refresh: {e}")

            else:
                _click.echo(f"Unknown scenario: {scenario}")
                _click.echo("Available: S1, S2, S5, S6")

    return cli


if __name__ == "__main__":
    main()
