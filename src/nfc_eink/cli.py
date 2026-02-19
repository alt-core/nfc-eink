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
    @_click.option(
        "--photo",
        is_flag=True,
        default=False,
        help="Photo preset: --dither atkinson --resize cover --palette tuned --tone-map.",
    )
    @_click.option(
        "--dither", "-d",
        type=_click.Choice(
            ["atkinson", "floyd-steinberg", "jarvis", "stucki", "none", "pillow"],
            case_sensitive=False,
        ),
        default="pillow",
        help="Dithering algorithm (default: pillow).",
    )
    @_click.option(
        "--resize", "-r",
        type=_click.Choice(["fit", "cover"], case_sensitive=False),
        default="fit",
        help="Resize mode: fit (white margins) or cover (crop excess). Default: fit.",
    )
    @_click.option(
        "--palette", "-p",
        type=_click.Choice(["pure", "tuned"], case_sensitive=False),
        default="pure",
        help="Palette mode: pure (ideal RGB) or tuned (adjusted for actual panel). Default: pure.",
    )
    @_click.option(
        "--tone-map/--no-tone-map",
        default=None,
        help="Enable/disable luminance tone mapping. Default: auto (on for tuned palette).",
    )
    @_click.pass_context
    def send(ctx: _click.Context, image_path: str, photo: bool, dither: str, resize: str, palette: str, tone_map: bool | None) -> None:
        """Send an image to the e-ink card and refresh the display."""
        from PIL import Image

        from nfc_eink.card import EInkCard

        # --photo sets defaults; explicitly specified options take priority
        if photo:
            src = ctx.get_parameter_source
            if src("dither") != _click.core.ParameterSource.COMMANDLINE:
                dither = "atkinson"
            if src("resize") != _click.core.ParameterSource.COMMANDLINE:
                resize = "cover"
            if src("palette") != _click.core.ParameterSource.COMMANDLINE:
                palette = "tuned"
            if src("tone_map") != _click.core.ParameterSource.COMMANDLINE:
                tone_map = True

        _click.echo(f"Loading image: {image_path}")
        image = Image.open(image_path)

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            di = card.device_info
            _click.echo(
                f"Card: {card.serial_number} "
                f"({di.width}x{di.height}, {di.num_colors} colors)"
            )

            _click.echo(f"Sending image (dither={dither}, resize={resize}, palette={palette})...")
            card.send_image(image, dither=dither, resize=resize, palette=palette, tone_map=tone_map)

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
        from nfc_eink.device import parse_tlv

        _click.echo("Waiting for NFC card...")
        with EInkCard() as card:
            di = card.device_info
            _click.echo(f"C0 (device ID): {card.serial_number}")
            _click.echo(f"C1 (unknown):   {di.c1.hex() if di.c1 else '(not present)'}")
            _click.echo(f"Screen:         {di.width}x{di.height}")
            _click.echo(f"Colors:         {di.num_colors}")
            _click.echo(f"Bits/pixel:     {di.bits_per_pixel}")
            _click.echo(f"Rotated FB:     {di.rotated}")
            _click.echo(f"Framebuffer:    {di.fb_width}x{di.fb_height}")
            _click.echo(f"Blocks:         {di.num_blocks} ({'+'.join(str(s) for s in di.block_sizes)} bytes)")

            # Raw hex dump for debugging
            if di.raw:
                tlv = parse_tlv(di.raw)
                if 0xA0 in tlv:
                    a0_hex = " ".join(f"{b:02x}" for b in tlv[0xA0])
                    _click.echo(f"Raw A0:         [{a0_hex}]")
                _click.echo(f"Raw response:   {di.raw.hex()}")

    @cli.command()
    @_click.argument("scenario", default="black")
    def diag(scenario: str) -> None:
        """Basic device diagnostics.

        \b
        Scenarios:
          black   - Fill screen with black
          white   - Fill screen with white
          yellow  - Fill screen with yellow (4-color devices only)
          red     - Fill screen with red (4-color devices only)
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

            def fill_byte(color_index: int) -> int:
                """Compute byte value for solid fill of a color index."""
                ppb = di.pixels_per_byte
                bpp = di.bits_per_pixel
                val = 0
                for i in range(ppb):
                    val |= color_index << (i * bpp)
                return val

            # Solid fill scenarios: name -> (color_index, label, min_colors)
            solid_fills = {
                "black":  (0, "BLACK",  2),
                "white":  (1, "WHITE",  2),
                "yellow": (2, "YELLOW", 4),
                "red":    (3, "RED",    4),
            }

            if scenario in solid_fills:
                color_index, label, min_colors = solid_fills[scenario]
                if di.num_colors < min_colors:
                    _click.echo(
                        f"Error: '{scenario}' requires {min_colors}-color device "
                        f"(this device has {di.num_colors} colors)"
                    )
                    return
                fill = fill_byte(color_index)
                _click.echo(f"\n--- Fill all blocks with {label} (0x{fill:02x}) ---")
                for blk_no, size in enumerate(di.block_sizes):
                    send_block(blk_no, bytes([fill]) * size)
                    _click.echo(f"  blk={blk_no} ({size}B): OK")

            elif scenario == "stripe":
                _click.echo("\n--- Alternating B/W stripes ---")
                fill_black = fill_byte(0)
                fill_white = fill_byte(1)
                for blk_no, size in enumerate(di.block_sizes):
                    fill = fill_black if blk_no % 2 == 0 else fill_white
                    label = "BLACK" if fill == fill_black else "WHITE"
                    send_block(blk_no, bytes([fill]) * size)
                    _click.echo(f"  blk={blk_no} ({size}B) = {label}: OK")

            else:
                _click.echo(f"Unknown scenario: {scenario}")
                _click.echo("Available: black, white, yellow, red, stripe")
                return

            _click.echo("Refreshing...")
            card.refresh()
            _click.echo("Done!")

    return cli


if __name__ == "__main__":
    main()
