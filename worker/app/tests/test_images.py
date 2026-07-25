import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app import images


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


def _solid_png_bytes(size: tuple[int, int]) -> bytes:
    image = Image.new("RGB", size, (200, 50, 50))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _high_entropy_png_bytes(size: tuple[int, int]) -> bytes:
    # A wrap-around gradient has enough high-frequency detail that JPEG can't compress it
    # trivially, unlike a solid color — needed to exercise the quality-reduction loop.
    image = Image.new("RGB", size)
    image.putdata(
        [(x % 256, y % 256, (x + y) % 256) for y in range(size[1]) for x in range(size[0])]
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _images_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(images.settings, "images_dir", str(tmp_path))
    return tmp_path


def test_process_images_downloads_resizes_and_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(images.settings, "image_max_dimension", 50)
    monkeypatch.setattr(images.settings, "image_max_size_kb", 500)
    content = _solid_png_bytes((200, 200))
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: FakeResponse(content))

    result = images.process_images(["https://example.com/photo.png"])

    assert len(result) == 1
    assert result[0].startswith("/images/")
    assert result[0].endswith(".jpg")

    saved_path = tmp_path / result[0].removeprefix("/images/")
    assert saved_path.exists()
    with Image.open(saved_path) as saved:
        assert saved.format == "JPEG"
        assert max(saved.size) <= 50


def test_process_images_skips_failed_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> FakeResponse:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(images.httpx, "get", fake_get)

    assert images.process_images(["https://example.com/broken.png"]) == []


def test_process_images_skips_non_image_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        images.httpx, "get", lambda *a, **k: FakeResponse(b"<html>not an image</html>")
    )

    assert images.process_images(["https://example.com/notanimage"]) == []


def test_process_images_continues_after_one_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_content = _solid_png_bytes((100, 100))

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if "bad" in url:
            raise httpx.ConnectError("boom")
        return FakeResponse(good_content)

    monkeypatch.setattr(images.httpx, "get", fake_get)

    result = images.process_images(
        ["https://example.com/bad.png", "https://example.com/good.png"]
    )

    assert len(result) == 1


def test_process_images_reduces_quality_to_respect_max_size_kb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Verified empirically: this 400x400 gradient encodes to ~8.5KB at quality 85 but ~5KB by
    # quality 40, so a 5KB budget forces the loop to actually step down instead of a no-op.
    monkeypatch.setattr(images.settings, "image_max_dimension", 800)
    monkeypatch.setattr(images.settings, "image_max_size_kb", 5)
    content = _high_entropy_png_bytes((400, 400))
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: FakeResponse(content))

    result = images.process_images(["https://example.com/detailed.png"])

    saved_path = tmp_path / result[0].removeprefix("/images/")
    assert saved_path.stat().st_size <= 5 * 1024


def test_process_images_stops_at_quality_floor_even_if_still_over_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unreasonably tight budget should still terminate (not loop forever) and save
    # whatever the quality floor produces, rather than raising or hanging.
    monkeypatch.setattr(images.settings, "image_max_dimension", 800)
    monkeypatch.setattr(images.settings, "image_max_size_kb", 1)
    content = _high_entropy_png_bytes((400, 400))
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: FakeResponse(content))

    result = images.process_images(["https://example.com/detailed.png"])

    assert len(result) == 1
    saved_path = tmp_path / result[0].removeprefix("/images/")
    assert saved_path.exists()
    assert saved_path.stat().st_size > 1024  # over budget, but still produced a file
