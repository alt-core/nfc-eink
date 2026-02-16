"""Tests for image conversion module."""

from PIL import Image

from nfc_eink.convert import EINK_PALETTE, PALETTES, convert_image


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
