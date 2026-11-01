import pytest

from app.services.image_validator import ImageValidationError, validate_image
from tests.helpers import image_bytes


@pytest.mark.parametrize(
    ("name", "content_type", "image_format"),
    [
        ("photo.jpg", "image/jpeg", "JPEG"),
        ("photo.png", "image/png", "PNG"),
        ("photo.webp", "image/webp", "WEBP"),
    ],
)
def test_accepts_supported_image_formats(name, content_type, image_format):
    actual_format, width, height = validate_image(image_bytes(image_format), name, content_type)
    assert actual_format == {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}[image_format]
    assert (width, height) == (80, 40)


@pytest.mark.parametrize(
    ("data", "name", "content_type"),
    [
        (b"", "empty.png", "image/png"),
        (b"not an image", "broken.png", "image/png"),
        (image_bytes("PNG"), "wrong.jpg", "image/jpeg"),
        (image_bytes("PNG"), "photo.svg", "image/svg+xml"),
        (image_bytes("PNG"), "photo.png", "image/jpeg"),
    ],
)
def test_rejects_invalid_files(data, name, content_type):
    with pytest.raises(ImageValidationError):
        validate_image(data, name, content_type)


def test_rejects_excessive_dimensions():
    with pytest.raises(ImageValidationError, match="dimensions"):
        validate_image(image_bytes("PNG", (12001, 1)), "wide.png", "image/png")
