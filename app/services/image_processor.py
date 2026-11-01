from io import BytesIO
import math

from PIL import Image, ImageOps

from app.core.config import settings


class ImageProcessingError(ValueError):
    pass


def _target_size(
    original_width: int,
    original_height: int,
    resize_mode: str,
    width: int | None,
    height: int | None,
    allow_enlarge: bool,
) -> tuple[int, int]:
    if resize_mode not in ("original", "custom", "max"):
        raise ImageProcessingError("Choose original size, custom size, or maximum dimensions.")
    for dimension in (width, height):
        if dimension is not None and not 1 <= dimension <= settings.max_image_dimension:
            raise ImageProcessingError(
                f"Resize dimensions must be between 1 and {settings.max_image_dimension:,} pixels."
            )
    if resize_mode == "original":
        return original_width, original_height
    if width is None and height is None:
        raise ImageProcessingError("Enter at least one valid resize dimension.")

    scale = min(
        width / original_width if width is not None else float("inf"),
        height / original_height if height is not None else float("inf"),
    )
    if not allow_enlarge:
        scale = min(scale, 1.0)
    return max(1, math.floor(original_width * scale)), max(1, math.floor(original_height * scale))


def compress_image(
    data: bytes,
    output_format: str,
    quality: int,
    resize_mode: str = "original",
    width: int | None = None,
    height: int | None = None,
    allow_enlarge: bool = False,
    webp_lossless: bool = False,
) -> tuple[bytes, int, int]:
    if output_format not in ("jpeg", "png", "webp"):
        raise ImageProcessingError("Choose JPEG, PNG, or WebP as the output format.")
    if not 10 <= quality <= 100:
        raise ImageProcessingError("Quality must be between 10 and 100.")

    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            original_width, original_height = image.size
            target = _target_size(original_width, original_height, resize_mode, width, height, allow_enlarge)
            if target != image.size:
                image = image.resize(target, Image.Resampling.LANCZOS)

            output = BytesIO()
            if output_format == "jpeg":
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                elif image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
            elif output_format == "png":
                if image.mode not in ("RGB", "RGBA", "L", "LA", "P", "1", "I", "F"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                image.save(output, format="PNG", optimize=True, compress_level=9)
            else:
                if image.mode not in ("RGB", "RGBA"):
                    has_transparency = "A" in image.getbands() or "transparency" in image.info
                    image = image.convert("RGBA" if has_transparency else "RGB")
                image.save(
                    output,
                    format="WEBP",
                    quality=quality,
                    method=5,
                    lossless=webp_lossless,
                )
            return output.getvalue(), target[0], target[1]
    except (OSError, ValueError) as exc:
        if isinstance(exc, ImageProcessingError):
            raise
        raise ImageProcessingError("The image could not be processed with these settings.") from exc
