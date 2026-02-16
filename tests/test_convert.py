"""Tests for image conversion module."""

from PIL import Image

from nfc_eink.convert import EINK_PALETTE, convert_image


class TestConvertImage:
    def test_output_dimensions(self):
        img = Image.new("RGB", (800, 600), (255, 255, 255))
        result = convert_image(img)
        assert len(result) == 300
        assert all(len(row) == 400 for row in result)

    def test_white_image(self):
        img = Image.new("RGB", (400, 300), (255, 255, 255))
        result = convert_image(img)
        # All pixels should be white (index 1)
        assert all(pixel == 1 for row in result for pixel in row)

    def test_black_image(self):
        img = Image.new("RGB", (400, 300), (0, 0, 0))
        result = convert_image(img)
        # All pixels should be black (index 0)
        assert all(pixel == 0 for row in result for pixel in row)

    def test_red_image(self):
        img = Image.new("RGB", (400, 300), (255, 0, 0))
        result = convert_image(img)
        # All pixels should be red (index 3)
        assert all(pixel == 3 for row in result for pixel in row)

    def test_yellow_image(self):
        img = Image.new("RGB", (400, 300), (255, 255, 0))
        result = convert_image(img)
        # All pixels should be yellow (index 2)
        assert all(pixel == 2 for row in result for pixel in row)

    def test_values_in_range(self):
        """All output values should be valid color indices 0..3."""
        img = Image.new("RGB", (100, 100), (128, 64, 32))
        result = convert_image(img)
        assert all(0 <= pixel <= 3 for row in result for pixel in row)

    def test_non_square_image_preserves_aspect(self):
        """A wide image should be letterboxed with white."""
        img = Image.new("RGB", (400, 100), (0, 0, 0))
        result = convert_image(img)
        # Top and bottom rows should be mostly white (letterboxing)
        top_row = result[0]
        assert all(pixel == 1 for pixel in top_row)

    def test_rgba_input(self):
        """Should handle RGBA input images."""
        img = Image.new("RGBA", (400, 300), (255, 0, 0, 255))
        result = convert_image(img)
        assert len(result) == 300
        assert all(pixel == 3 for row in result for pixel in row)

    def test_grayscale_input(self):
        """Should handle grayscale input images."""
        img = Image.new("L", (400, 300), 0)
        result = convert_image(img)
        assert len(result) == 300
        # Black pixels
        assert all(pixel == 0 for row in result for pixel in row)

    def test_palette_values(self):
        assert len(EINK_PALETTE) == 4
        assert EINK_PALETTE[0] == (0, 0, 0)        # Black
        assert EINK_PALETTE[1] == (255, 255, 255)  # White
        assert EINK_PALETTE[2] == (255, 255, 0)    # Yellow
        assert EINK_PALETTE[3] == (255, 0, 0)      # Red
