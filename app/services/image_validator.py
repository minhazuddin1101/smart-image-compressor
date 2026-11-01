from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError

from app.core.config import settings


FORMAT_BY_EXTENSION = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".webp": ("WEBP", "image/webp"),
}
FORMAT_NAMES = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}


class ImageValidationError(ValueError):
    pass


def validate_image(data: bytes, filename: str, content_type: str | None = None) -> tuple[str, int, int]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    expected = FORMAT_BY_EXTENSION.get(f".{extension}")
    if expected is None:
        raise ImageValidationError("Unsupported file type. Use JPEG, PNG, or WebP.")
    if not data:
        raise ImageValidationError("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise ImageValidationError("The image exceeds the 10 MB upload limit.")
    if content_type and content_type not in (expected[1], "application/octet-stream"):
        raise ImageValidationError("The file type does not match its extension.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                detected_format = image.format
                width, height = image.size
                if detected_format != expected[0]:
                    raise ImageValidationError("The image content does not match its extension.")
                if width <= 0 or height <= 0:
                    raise ImageValidationError("The image has invalid dimensions.")
                if width > settings.max_image_dimension or height > settings.max_image_dimension:
                    raise ImageValidationError("The image dimensions exceed the configured limit.")
                if width * height > settings.max_image_pixels:
                    raise ImageValidationError("The image contains too many pixels to process safely.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ImageValidationError("Animated images are not supported.")
                image.verify()
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ImageValidationError("The uploaded file is not a valid, readable image.") from exc

    return FORMAT_NAMES[detected_format], width, height
