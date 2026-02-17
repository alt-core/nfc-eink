"""Tests for image conversion module."""

import numpy as np
import pytest
from PIL import Image

from nfc_eink.convert import (
    DITHER_MATRICES,
    EINK_PALETTE,
    PALETTES,
    _dither,
    convert_image,
    rgb_to_lab,
)


class TestRgbToLab:
    """Tests for RGB → CIELAB conversion."""

    def test_black(self):
        rgb = np.array([0, 0, 0], dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert abs(lab[0]) < 0.5  # L* ≈ 0
        assert abs(lab[1]) < 0.5  # a* ≈ 0
        assert abs(lab[2]) < 0.5  # b* ≈ 0

    def test_white(self):
        rgb = np.array([255, 255, 255], dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert abs(lab[0] - 100.0) < 0.1  # L* ≈ 100
        assert abs(lab[1]) < 0.5  # a* ≈ 0
        assert abs(lab[2]) < 0.5  # b* ≈ 0

    def test_red(self):
        rgb = np.array([255, 0, 0], dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert 50 < lab[0] < 55  # L* ≈ 53.2
        assert lab[1] > 70  # a* > 0 (red axis)
        assert lab[2] > 50  # b* > 0 (yellow axis)

    def test_yellow(self):
        rgb = np.array([255, 255, 0], dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert lab[0] > 90  # L* is high (bright)
        assert lab[2] > 80  # b* > 0 (yellow axis)

    def test_batch_shape(self):
        """rgb_to_lab should work on (H, W, 3) arrays."""
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert lab.shape == (10, 20, 3)

    def test_single_pixel_shape(self):
        rgb = np.array([128, 64, 32], dtype=np.uint8)
        lab = rgb_to_lab(rgb)
        assert lab.shape == (3,)


class TestDither:
    """Tests for the _dither function."""

    def test_solid_black(self):
        """Solid black image should map entirely to index 0."""
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert result.shape == (10, 10)
        assert np.all(result == 0)

    def test_solid_white(self):
        """Solid white image should map entirely to index 1."""
        image = np.full((10, 10, 3), 255, dtype=np.uint8)
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert np.all(result == 1)

    def test_solid_red(self):
        """Solid red image should map entirely to index 3."""
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[..., 0] = 255  # R=255
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert np.all(result == 3)

    def test_solid_yellow(self):
        """Solid yellow image should map entirely to index 2."""
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[..., 0] = 255  # R=255
        image[..., 1] = 255  # G=255
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert np.all(result == 2)

    def test_values_in_range(self):
        """All output values should be valid palette indices."""
        rng = np.random.RandomState(42)
        image = rng.randint(0, 256, (20, 20, 3), dtype=np.uint8)
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert np.all((result >= 0) & (result < 4))

    def test_no_dither(self):
        """method='none' should produce nearest-color mapping without error diffusion."""
        image = np.full((5, 5, 3), 128, dtype=np.uint8)
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method="none")
        assert result.shape == (5, 5)
        assert np.all((result >= 0) & (result < 4))
        # All pixels are the same input, so all should map to the same index
        assert np.all(result == result[0, 0])

    @pytest.mark.parametrize("method", list(DITHER_MATRICES.keys()))
    def test_all_methods_accepted(self, method):
        """All named dithering methods should run without error."""
        image = np.full((5, 5, 3), 128, dtype=np.uint8)
        palette = np.array(PALETTES[4], dtype=np.uint8)
        result = _dither(image, palette, method=method)
        assert result.shape == (5, 5)

    def test_2color_palette(self):
        """Dithering should work with 2-color palette."""
        image = np.full((10, 10, 3), 128, dtype=np.uint8)
        palette = np.array(PALETTES[2], dtype=np.uint8)
        result = _dither(image, palette, method="atkinson")
        assert np.all((result >= 0) & (result < 2))


class TestConvertImage4Color:
    def test_output_dimensions(self):
        img = Image.new("RGB", (800, 600), (255, 255, 255))
        result = convert_image(img)
        assert len(result) == 300
        assert all(len(row) == 400 for row in result)

    def test_white_image(self):
        img = Image.new("RGB", (400, 300), (255, 255, 255))
        result = convert_image(img)
        assert all(pixel == 1 for row in result for pixel in row)

    def test_black_image(self):
        img = Image.new("RGB", (400, 300), (0, 0, 0))
        result = convert_image(img)
        assert all(pixel == 0 for row in result for pixel in row)

    def test_red_image(self):
        img = Image.new("RGB", (400, 300), (255, 0, 0))
        result = convert_image(img)
        assert all(pixel == 3 for row in result for pixel in row)

    def test_yellow_image(self):
        img = Image.new("RGB", (400, 300), (255, 255, 0))
        result = convert_image(img)
        assert all(pixel == 2 for row in result for pixel in row)

    def test_values_in_range(self):
        img = Image.new("RGB", (100, 100), (128, 64, 32))
        result = convert_image(img)
        assert all(0 <= pixel <= 3 for row in result for pixel in row)

    def test_non_square_image_preserves_aspect(self):
        img = Image.new("RGB", (400, 100), (0, 0, 0))
        result = convert_image(img)
        top_row = result[0]
        assert all(pixel == 1 for pixel in top_row)

    def test_rgba_input(self):
        img = Image.new("RGBA", (400, 300), (255, 0, 0, 255))
        result = convert_image(img)
        assert all(pixel == 3 for row in result for pixel in row)

    def test_grayscale_input(self):
        img = Image.new("L", (400, 300), 0)
        result = convert_image(img)
        assert all(pixel == 0 for row in result for pixel in row)


class TestConvertImage2Color:
    def test_output_dimensions(self):
        img = Image.new("RGB", (600, 300), (255, 255, 255))
        result = convert_image(img, width=296, height=128, num_colors=2)
        assert len(result) == 128
        assert all(len(row) == 296 for row in result)

    def test_white_image(self):
        img = Image.new("RGB", (296, 128), (255, 255, 255))
        result = convert_image(img, width=296, height=128, num_colors=2)
        assert all(pixel == 1 for row in result for pixel in row)

    def test_black_image(self):
        img = Image.new("RGB", (296, 128), (0, 0, 0))
        result = convert_image(img, width=296, height=128, num_colors=2)
        assert all(pixel == 0 for row in result for pixel in row)

    def test_values_in_range(self):
        img = Image.new("RGB", (296, 128), (128, 64, 32))
        result = convert_image(img, width=296, height=128, num_colors=2)
        assert all(0 <= pixel <= 1 for row in result for pixel in row)

    def test_red_becomes_black_or_white(self):
        """Red should be dithered to black/white in 2-color mode."""
        img = Image.new("RGB", (296, 128), (255, 0, 0))
        result = convert_image(img, width=296, height=128, num_colors=2)
        assert all(pixel in (0, 1) for row in result for pixel in row)


class TestDitherMethods:
    """Test different dithering methods through convert_image."""

    def test_none_dither(self):
        img = Image.new("RGB", (20, 20), (255, 255, 255))
        result = convert_image(img, width=20, height=20, dither="none")
        assert all(pixel == 1 for row in result for pixel in row)

    def test_floyd_steinberg(self):
        img = Image.new("RGB", (20, 20), (0, 0, 0))
        result = convert_image(img, width=20, height=20, dither="floyd-steinberg")
        assert all(pixel == 0 for row in result for pixel in row)

    def test_jarvis(self):
        img = Image.new("RGB", (20, 20), (255, 0, 0))
        result = convert_image(img, width=20, height=20, dither="jarvis")
        assert all(pixel == 3 for row in result for pixel in row)

    def test_stucki(self):
        img = Image.new("RGB", (20, 20), (255, 255, 0))
        result = convert_image(img, width=20, height=20, dither="stucki")
        assert all(pixel == 2 for row in result for pixel in row)

    def test_pillow_fallback_white(self):
        img = Image.new("RGB", (20, 20), (255, 255, 255))
        result = convert_image(img, width=20, height=20, dither="pillow")
        assert all(pixel == 1 for row in result for pixel in row)

    def test_pillow_fallback_black(self):
        img = Image.new("RGB", (20, 20), (0, 0, 0))
        result = convert_image(img, width=20, height=20, dither="pillow")
        assert all(pixel == 0 for row in result for pixel in row)

    def test_pillow_fallback_red(self):
        img = Image.new("RGB", (20, 20), (255, 0, 0))
        result = convert_image(img, width=20, height=20, dither="pillow")
        assert all(pixel == 3 for row in result for pixel in row)

    def test_pillow_fallback_values_in_range(self):
        img = Image.new("RGB", (20, 20), (128, 64, 32))
        result = convert_image(img, width=20, height=20, dither="pillow")
        assert all(0 <= pixel <= 3 for row in result for pixel in row)

    def test_pillow_fallback_2color(self):
        img = Image.new("RGB", (20, 20), (0, 0, 0))
        result = convert_image(img, width=20, height=20, num_colors=2, dither="pillow")
        assert all(pixel == 0 for row in result for pixel in row)

    def test_invalid_method_raises(self):
        img = Image.new("RGB", (20, 20), (0, 0, 0))
        with pytest.raises(ValueError, match="Unknown dither method"):
            convert_image(img, width=20, height=20, dither="invalid")


class TestPalettes:
    def test_4color_palette(self):
        assert len(PALETTES[4]) == 4
        assert PALETTES[4][0] == (0, 0, 0)
        assert PALETTES[4][1] == (255, 255, 255)

    def test_2color_palette(self):
        assert len(PALETTES[2]) == 2
        assert PALETTES[2][0] == (0, 0, 0)
        assert PALETTES[2][1] == (255, 255, 255)

    def test_backward_compat(self):
        assert EINK_PALETTE == PALETTES[4]


class TestUnsupportedNumColors:
    def test_convert_image_rejects_unsupported_num_colors(self):
        import pytest

        img = Image.new("RGB", (20, 20), (255, 255, 255))
        with pytest.raises(ValueError, match="Unsupported num_colors=128"):
            convert_image(img, width=20, height=20, num_colors=128)

    def test_error_message_suggests_info_command(self):
        import pytest

        img = Image.new("RGB", (20, 20), (255, 255, 255))
        with pytest.raises(ValueError, match="nfc-eink info"):
            convert_image(img, width=20, height=20, num_colors=128)
