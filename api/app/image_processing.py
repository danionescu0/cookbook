import io

from PIL import Image, UnidentifiedImageError


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def resize_and_compress(content: bytes, max_dimension: int, max_size_kb: int) -> bytes | None:
    """Downscale and JPEG-compress raw image bytes. Returns None if content isn't a valid image.

    Mirrors worker/app/images.py's _resize_and_compress — same downscale/compress policy is used
    whether an image arrives via worker-side URL download or this admin-side manual upload, so a
    recipe's images all look and behave the same regardless of source.
    """
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except UnidentifiedImageError:
        return None

    image.thumbnail((max_dimension, max_dimension))
    image = _flatten_to_rgb(image)

    max_bytes = max_size_kb * 1024
    quality = 85
    buffer = io.BytesIO()
    while True:
        buffer.seek(0)
        buffer.truncate()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        if buffer.tell() <= max_bytes or quality <= 40:
            break
        quality -= 10

    return buffer.getvalue()
