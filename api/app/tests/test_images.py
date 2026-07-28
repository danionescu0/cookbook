import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.routers import images as images_router


@pytest.fixture(autouse=True)
def _images_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(images_router.settings, "images_dir", str(tmp_path))
    return tmp_path


def _png_bytes(size: tuple[int, int] = (200, 200)) -> bytes:
    image = Image.new("RGB", size, (200, 50, 50))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_image_stores_and_returns_url(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/images", files={"file": ("photo.png", _png_bytes(), "image/png")}
    )

    assert response.status_code == 201
    url = response.json()["url"]
    assert url.startswith("/images/")
    assert url.endswith(".jpg")

    saved_path = tmp_path / url.removeprefix("/images/")
    assert saved_path.exists()
    with Image.open(saved_path) as saved:
        assert saved.format == "JPEG"


def test_upload_image_rejects_non_image_content(client: TestClient) -> None:
    response = client.post(
        "/images", files={"file": ("notanimage.txt", b"just some text", "text/plain")}
    )

    assert response.status_code == 400


def test_upload_image_requires_auth(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/images", files={"file": ("photo.png", _png_bytes(), "image/png")}
    )

    assert response.status_code == 401
