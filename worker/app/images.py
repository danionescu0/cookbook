import io
import logging
import uuid
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.settings_service import SettingsSnapshot

logger = logging.getLogger(__name__)


def _download(url: str, timeout_seconds: float) -> bytes | None:
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": settings.scrape_user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as exc:
        logger.warning("failed to download image %s: %s", url, exc)
        return None


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def _resize_and_compress(content: bytes, max_dimension: int, max_size_kb: int) -> bytes | None:
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


def process_images(image_urls: list[str], app_settings: SettingsSnapshot) -> list[str]:
    """Download, downscale, and compress each URL to a local JPEG.

    Individual failures (unreachable URL, non-image content) are skipped rather than
    failing the whole import — a recipe with fewer images beats no recipe at all.
    """
    images_dir = Path(settings.images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    served_urls: list[str] = []
    for url in image_urls:
        content = _download(url, app_settings.scrape_timeout_seconds)
        if content is None:
            continue

        processed = _resize_and_compress(
            content, app_settings.image_max_dimension, app_settings.image_max_size_kb
        )
        if processed is None:
            logger.warning("skipping non-image content at %s", url)
            continue

        filename = f"{uuid.uuid4().hex}.jpg"
        (images_dir / filename).write_bytes(processed)
        served_urls.append(f"/images/{filename}")

    return served_urls
