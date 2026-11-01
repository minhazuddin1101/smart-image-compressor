from io import BytesIO

from PIL import Image

from app.services.image_processor import compress_image
from tests.helpers import image_bytes


def open_output(data):
    image = Image.open(BytesIO(data))
    image.load()
    return image


def test_compresses_to_supported_formats():
    source = image_bytes()
    for output_format, pillow_format in (("jpeg", "JPEG"), ("png", "PNG"), ("webp", "WEBP")):
        output, width, height = compress_image(source, output_format, 80)
        assert open_output(output).format == pillow_format
        assert (width, height) == (80, 40)


def test_png_preserves_alpha():
    output, _, _ = compress_image(image_bytes(), "png", 40)
    result = open_output(output)
    assert result.mode in ("RGBA", "LA", "P")
    assert result.getpixel((0, 0))[3] == 100


def test_webp_preserves_palette_png_transparency():
    source = Image.new("P", (2, 2), 0)
    source.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    source.info["transparency"] = 0
    encoded = BytesIO()
    source.save(encoded, format="PNG", transparency=0)

    output, _, _ = compress_image(encoded.getvalue(), "webp", 80)
    result = open_output(output).convert("RGBA")
    assert result.getpixel((0, 0))[3] == 0


def test_jpeg_output_composites_transparency():
    output, _, _ = compress_image(image_bytes(), "jpeg", 80)
    result = open_output(output)
    assert result.format == "JPEG"
    assert result.mode in ("RGB", "L")


def test_resize_preserves_aspect_ratio_and_does_not_enlarge_by_default():
    output, width, height = compress_image(
        image_bytes(size=(800, 400)), "png", 80, "custom", 400, 400
    )
    assert (width, height) == (400, 200)
    assert open_output(output).size == (400, 200)

    _, width, height = compress_image(image_bytes(size=(80, 40)), "png", 80, "max", 400, 400)
    assert (width, height) == (80, 40)


def test_explicit_enlargement_is_supported():
    _, width, height = compress_image(
        image_bytes(size=(80, 40)), "png", 80, "custom", 400, 400, allow_enlarge=True
    )
    assert (width, height) == (400, 200)
