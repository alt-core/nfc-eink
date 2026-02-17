#!/usr/bin/env python3
"""L-system tree growth demo for NFC e-ink cards.

Each NFC e-ink card touched to the reader grows a unique tree.
The tree's shape is deterministically derived from the device's serial number,
and each subsequent touch advances the growth by one step.

Usage:
    # Normal mode: wait for NFC cards in a loop
    python examples/tree_demo.py

    # Preview mode: generate step 0-6 images for all device profiles
    python examples/tree_demo.py --preview [SERIAL]

Requires: nfc-eink[cli] (pip install "nfc-eink[cli] @ git+...")
"""

from __future__ import annotations

import argparse
import hashlib
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Palette colors (must match nfc_eink.convert.PALETTES)
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)

# ---------------------------------------------------------------------------
# Tree parameters
# ---------------------------------------------------------------------------
MAX_DEPTH = 6
LEAF_STAGE = 4   # step at which leaves appear
FLOWER_STAGE = 5  # step at which flowers appear
GROUND_MARGIN = 20  # pixels from bottom edge to ground line


@dataclass
class TreeParams:
    """Per-device tree shape parameters, deterministically derived from serial."""

    branch_angle: float       # base branching angle (radians)
    length_ratio: float       # length reduction per depth level
    side_ratio: float         # side branch length relative to main
    thickness_ratio: float    # thickness reduction per level
    initial_length: float     # trunk segment length (px)
    initial_thickness: float  # trunk line width (px)
    lean: float               # overall lean offset (radians)
    angle_jitter: float       # gaussian stdev for angle randomness
    extra_branch_prob: float  # probability of a third branch at each node
    leaf_size: float          # leaf radius (px)
    flower_size: float        # flower radius (px)
    leaf_density: float       # probability of drawing a leaf
    flower_density: float     # probability of drawing a flower


def make_tree_params(serial_number: str, tree_index: int = 0) -> TreeParams:
    """Derive deterministic tree parameters from a device serial number."""
    seed_bytes = hashlib.sha256(
        f"{serial_number}:tree:{tree_index}".encode()
    ).digest()
    seed = int.from_bytes(seed_bytes[:8], "big")
    rng = random.Random(seed)

    # Target tree height at MAX_DEPTH determines initial_length.
    # Available: ~276px (296 - ground margin). Range gives good variation.
    target_height = rng.uniform(130, 270)
    length_ratio = rng.uniform(0.65, 0.82)
    series_sum = (1 - length_ratio ** MAX_DEPTH) / (1 - length_ratio)
    initial_length = target_height / series_sum

    return TreeParams(
        branch_angle=math.radians(rng.uniform(22, 42)),
        length_ratio=length_ratio,
        side_ratio=rng.uniform(0.6, 0.85),
        thickness_ratio=rng.uniform(0.60, 0.72),
        initial_length=initial_length,
        initial_thickness=rng.uniform(6, 10),
        lean=rng.uniform(-0.12, 0.12),
        angle_jitter=rng.uniform(0.05, 0.18),
        extra_branch_prob=rng.uniform(0.0, 0.35),
        leaf_size=rng.uniform(3, 6),
        flower_size=rng.uniform(2, 4),
        leaf_density=rng.uniform(0.5, 1.0),
        flower_density=rng.uniform(0.2, 0.5),
    )


# ---------------------------------------------------------------------------
# Drawing functions
# ---------------------------------------------------------------------------

def draw_branch(
    draw: ImageDraw.ImageDraw,
    x: float, y: float,
    angle: float,
    length: float,
    thickness: float,
    depth: int,
    max_depth: int,
    params: TreeParams,
    rng: random.Random,
    num_colors: int,
) -> None:
    """Recursively draw a tree branch.

    Critical design: random numbers are consumed in a fixed pattern at every
    node regardless of depth, so that step N's tree is a strict visual subset
    of step N+1's tree.
    """
    # Always consume random numbers in the same order
    jitter = rng.gauss(0, params.angle_jitter)
    left_angle_offset = params.branch_angle + rng.gauss(0, params.angle_jitter)
    right_angle_offset = params.branch_angle + rng.gauss(0, params.angle_jitter)
    has_extra = rng.random() < params.extra_branch_prob
    extra_angle = rng.uniform(
        -params.branch_angle * 0.5, params.branch_angle * 0.5
    )
    leaf_rand = rng.random()
    flower_rand = rng.random()

    if depth <= 0 or length < 2:
        return

    # Compute endpoint
    end_x = x + length * math.cos(angle + jitter)
    end_y = y - length * math.sin(angle + jitter)

    # Draw branch segment
    w = max(1, round(thickness))
    draw.line([(x, y), (end_x, end_y)], fill=BLACK, width=w)

    # Decorations at branch tips
    if depth <= 2 and max_depth >= LEAF_STAGE:
        if leaf_rand < params.leaf_density:
            _draw_leaf(draw, end_x, end_y, params.leaf_size, num_colors)
    if depth == 1 and max_depth >= FLOWER_STAGE:
        if flower_rand < params.flower_density:
            _draw_flower(draw, end_x, end_y, params.flower_size, num_colors)

    # Recurse: main continuation
    new_len = length * params.length_ratio
    new_thick = thickness * params.thickness_ratio
    draw_branch(
        draw, end_x, end_y, angle + jitter,
        new_len, new_thick,
        depth - 1, max_depth, params, rng, num_colors,
    )

    # Left branch
    draw_branch(
        draw, end_x, end_y, angle + left_angle_offset,
        new_len * params.side_ratio, new_thick * 0.8,
        depth - 1, max_depth, params, rng, num_colors,
    )

    # Right branch
    draw_branch(
        draw, end_x, end_y, angle - right_angle_offset,
        new_len * params.side_ratio, new_thick * 0.8,
        depth - 1, max_depth, params, rng, num_colors,
    )

    # Optional extra branch
    if has_extra:
        draw_branch(
            draw, end_x, end_y, angle + extra_angle,
            new_len * 0.7, new_thick * 0.6,
            depth - 2, max_depth, params, rng, num_colors,
        )


def _draw_leaf(
    draw: ImageDraw.ImageDraw,
    x: float, y: float,
    size: float,
    num_colors: int,
) -> None:
    """Draw a leaf at the given position."""
    if num_colors >= 4:
        r = size
        draw.ellipse([x - r, y - r, x + r, y + r], fill=YELLOW)
    else:
        # 2-color: tiny dot (smaller to avoid dense canopy)
        r = max(1, size * 0.4)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)


def _draw_flower(
    draw: ImageDraw.ImageDraw,
    x: float, y: float,
    size: float,
    num_colors: int,
) -> None:
    """Draw a flower at the given position."""
    if num_colors >= 4:
        r = size
        draw.ellipse([x - r, y - r, x + r, y + r], fill=RED)
    else:
        # 2-color: small ring outline to distinguish from leaf dots
        r = max(2, size * 0.5)
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            outline=BLACK, width=1,
        )


def draw_seed(
    draw: ImageDraw.ImageDraw,
    cx: float, ground_y: float,
) -> None:
    """Draw a seed/sprout at ground level (step 0)."""
    # Seed body
    r = 4
    draw.ellipse(
        [cx - r, ground_y - r * 2, cx + r, ground_y],
        fill=BLACK,
    )
    # Tiny sprout
    draw.line(
        [(cx, ground_y - r * 2), (cx, ground_y - r * 2 - 10)],
        fill=BLACK, width=2,
    )


def draw_header(
    img: Image.Image,
    serial: str,
    step: int,
) -> None:
    """Draw serial number and step at the top of the canvas (binary, no AA)."""
    canvas_w = img.width
    text = f"{serial}  step {step}"
    # Pick the largest font size that fits within the canvas width
    for size in (14, 12, 11, 10, 9, 8):
        font = ImageFont.load_default(size=size)
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        if tw + 6 <= canvas_w:
            break
    th = bbox[3] - bbox[1]
    # Render text on a 1-bit image to avoid antialiasing
    txt_img = Image.new("1", (tw + 4, th + 4), 1)  # white
    ImageDraw.Draw(txt_img).text((2, 2 - bbox[1]), text, fill=0, font=font)
    # Paste onto the main RGB canvas
    img.paste(txt_img.convert("RGB"), (2, 1))


def draw_ground(
    draw: ImageDraw.ImageDraw,
    width: int, ground_y: float,
) -> None:
    """Draw a ground line."""
    draw.line([(0, ground_y), (width, ground_y)], fill=BLACK, width=1)


def draw_single_tree(
    draw: ImageDraw.ImageDraw,
    serial: str,
    tree_index: int,
    step: int,
    trunk_x: float,
    ground_y: float,
    num_colors: int,
    size_scale: float = 1.0,
) -> None:
    """Draw one tree at the specified position."""
    params = make_tree_params(serial, tree_index)

    # Deterministic RNG seeded by serial + tree_index only (not step!)
    seed_bytes = hashlib.sha256(
        f"{serial}:rng:{tree_index}".encode()
    ).digest()
    seed = int.from_bytes(seed_bytes[:8], "big")
    rng = random.Random(seed)

    if step == 0:
        draw_seed(draw, trunk_x, ground_y)
        return

    effective_depth = min(step, MAX_DEPTH)
    # Beyond MAX_DEPTH, scale up the trunk instead
    extra_scale = 1.0 + max(0, step - MAX_DEPTH) * 0.1
    trunk_length = params.initial_length * size_scale * extra_scale
    trunk_thickness = params.initial_thickness * size_scale * extra_scale

    draw_branch(
        draw,
        trunk_x, ground_y,
        angle=math.pi / 2 + params.lean,
        length=trunk_length,
        thickness=trunk_thickness,
        depth=effective_depth,
        max_depth=step,
        params=params,
        rng=rng,
        num_colors=num_colors,
    )


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_tree_image_landscape(
    serial: str,
    step: int,
    width: int = 400,
    height: int = 300,
    num_colors: int = 4,
) -> Image.Image:
    """Generate tree image for landscape devices (e.g. 400x300). 4 trees."""
    img = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(img)

    ground_y = height - GROUND_MARGIN
    draw_ground(draw, width, ground_y)
    draw_header(img, serial, step)

    # Layout: derive per-device positions from serial
    layout_seed = hashlib.sha256(f"{serial}:layout".encode()).digest()
    layout_rng = random.Random(int.from_bytes(layout_seed[:8], "big"))

    num_trees = 4
    zone_width = width // num_trees

    trees: list[tuple[float, float, int, int]] = []  # (x, scale, tree_step, idx)
    for i in range(num_trees):
        zone_center = zone_width * i + zone_width // 2
        x_offset = layout_rng.randint(-15, 15)
        trunk_x = zone_center + x_offset

        size_scale = layout_rng.uniform(0.6, 1.0)
        step_lag = layout_rng.choice([0, 0, 0, -1, -1, -2])
        tree_step = max(0, step + step_lag)

        trees.append((trunk_x, size_scale, tree_step, i))

    # Draw smaller trees first (further away)
    trees.sort(key=lambda t: t[1])
    for trunk_x, size_scale, tree_step, idx in trees:
        draw_single_tree(
            draw, serial, idx, tree_step,
            trunk_x, ground_y, num_colors, size_scale,
        )

    return img


def generate_tree_image_portrait(
    serial: str,
    step: int,
    width: int = 296,
    height: int = 128,
    num_colors: int = 2,
) -> Image.Image:
    """Generate tree image for portrait devices (e.g. 296x128 held vertically).

    Draws on a visual portrait canvas (height×width) then rotates to match
    the device's landscape coordinate system.
    """
    # Visual canvas: use device height as portrait width, device width as height
    vis_w = height  # 128
    vis_h = width   # 296

    img = Image.new("RGB", (vis_w, vis_h), WHITE)
    draw = ImageDraw.Draw(img)

    ground_y = vis_h - GROUND_MARGIN
    trunk_x = vis_w // 2

    draw_ground(draw, vis_w, ground_y)
    draw_header(img, serial, step)
    # Slightly scale down to reduce horizontal overflow on narrow canvas
    draw_single_tree(
        draw, serial, 0, step,
        trunk_x, ground_y, num_colors,
        size_scale=0.85,
    )

    # Rotate to match device landscape coordinates.
    # When user holds card with left edge up (90° CCW from landscape),
    # the portrait bottom becomes the landscape right side.
    # PIL rotate(90) = CCW rotation.
    return img.transpose(Image.Transpose.ROTATE_270)


def generate_tree_image(
    serial: str,
    step: int,
    width: int,
    height: int,
    num_colors: int,
) -> Image.Image:
    """Generate tree image appropriate for the given device profile."""
    if width < height:
        # Already portrait dimensions — shouldn't happen with current devices
        return generate_tree_image_portrait(
            serial, step, width, height, num_colors,
        )
    if height <= 128:
        # Small device (296x128) → portrait with 1 tree
        return generate_tree_image_portrait(
            serial, step, width, height, num_colors,
        )
    # Large device (400x300) → landscape with 4 trees
    return generate_tree_image_landscape(
        serial, step, width, height, num_colors,
    )


# ---------------------------------------------------------------------------
# Preview mode
# ---------------------------------------------------------------------------

DEVICE_PROFILES = [
    ("296x128_2c", 296, 128, 2),
    ("296x128_4c", 296, 128, 4),
    ("400x300_2c", 400, 300, 2),
    ("400x300_4c", 400, 300, 4),
]


def preview_mode(serial: str, output_dir: Path, max_step: int = 7) -> None:
    """Generate preview images for all device profiles and steps."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating previews for serial={serial}")
    print(f"Output directory: {output_dir}")

    for profile_name, w, h, nc in DEVICE_PROFILES:
        profile_dir = output_dir / profile_name
        profile_dir.mkdir(exist_ok=True)

        for step in range(max_step + 1):
            img = generate_tree_image(serial, step, w, h, nc)
            path = profile_dir / f"step{step}.png"
            img.save(path)
            print(f"  {profile_name}/step{step}.png ({img.size[0]}x{img.size[1]})")

    print(f"\nDone! {(max_step + 1) * len(DEVICE_PROFILES)} images generated.")


# ---------------------------------------------------------------------------
# NFC main loop
# ---------------------------------------------------------------------------

def _wait_for_removal(card: object, poll_interval: float = 0.5) -> None:
    """Poll the card until it is removed from the reader."""
    while True:
        try:
            # Any APDU that gets a response means the card is still present.
            # Use the poll command (F0DE) as a lightweight presence check.
            card._send_apdu(0xF0, 0xDE, 0, 0, None, mrl=1, check_status=False)
            time.sleep(poll_interval)
        except Exception:
            return  # Card removed (communication error)


DEBOUNCE_SECONDS = 1.5  # ignore re-detection shortly after removal


def nfc_loop(wait_for_removal: bool = True) -> None:
    """Main NFC loop: wait for cards and grow trees."""
    try:
        from nfc_eink import CommunicationError, EInkCard, NfcEinkError
    except ImportError:
        print(
            "nfc-eink is not installed. Install with:\n"
            '  pip install "nfc-eink[cli] @ git+https://github.com/alt-core/nfc-eink.git"',
            file=sys.stderr,
        )
        sys.exit(1)

    device_states: dict[str, int] = {}

    print("=== L-system Tree Demo ===")
    print("Touch an NFC e-ink card to grow a tree.")
    print("Press Ctrl+C to exit.\n")

    while True:
        print("Waiting for card...")
        try:
            with EInkCard() as card:
                serial = card.serial_number
                di = card.device_info

                if serial not in device_states:
                    device_states[serial] = 0
                    print(f"  [{serial}] New device! Generating tree...")
                else:
                    print(f"  [{serial}] Welcome back!")

                step = device_states[serial]
                print(
                    f"  Device: {di.width}x{di.height}, "
                    f"{di.num_colors} colors, step={step}"
                )

                print(f"  Generating image (step {step})...")
                img = generate_tree_image(
                    serial, step, di.width, di.height, di.num_colors,
                )

                print("  Sending image...")
                card.send_image(img, dither="none")

                print("  Refreshing display...")
                card.refresh()

                device_states[serial] = step + 1
                print(f"  Done! Step {step} -> {step + 1}")

                # Show state summary
                if len(device_states) > 1:
                    print("  --- Device states ---")
                    for s, st in sorted(device_states.items()):
                        marker = " <--" if s == serial else ""
                        print(f"    {s}: step {st}{marker}")

                # Wait for the card to be removed before accepting next touch
                if wait_for_removal:
                    print("  Remove the card from the reader...")
                    _wait_for_removal(card)
                    print("  Card removed.")

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except NfcEinkError as e:
            print(f"  NFC error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"  Unexpected error: {type(e).__name__}: {e}")
            time.sleep(1)

        # Debounce: brief pause to avoid re-detecting a card that is
        # still being lifted, or to space out back-to-back touches.
        time.sleep(DEBOUNCE_SECONDS if wait_for_removal else 2)
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="L-system tree growth demo for NFC e-ink cards.",
    )
    parser.add_argument(
        "--preview",
        metavar="SERIAL",
        nargs="?",
        const="DEMO001",
        help=(
            "Preview mode: generate step images as PNG files "
            "(default serial: DEMO001)."
        ),
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("preview"),
        help="Output directory for preview images (default: preview/).",
    )
    parser.add_argument(
        "--max-step",
        type=int,
        default=7,
        help="Maximum growth step for preview mode (default: 7).",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for card removal between touches.",
    )
    args = parser.parse_args()

    if args.preview is not None:
        preview_mode(args.preview, args.output_dir, args.max_step)
    else:
        nfc_loop(wait_for_removal=not args.no_wait)


if __name__ == "__main__":
    main()
