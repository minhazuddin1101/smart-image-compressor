from io import BytesIO

from PIL import Image


def image_bytes(image_format="PNG", size=(80, 40), color=(30, 120, 80, 100)):
    image = Image.new("RGBA", size, color)
    if image_format.upper() == "JPEG":
        image = image.convert("RGB")
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()
