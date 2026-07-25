import httpx
import pytest

from app import scraping


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Rate limiting itself is covered by test_rate_limiter.py; skip real sleeping here so
    # these tests stay fast and focused on robots.txt handling.
    monkeypatch.setattr(scraping._rate_limiter, "wait", lambda *args, **kwargs: None)


def test_fetch_page_returns_html_when_robots_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /\n")
        return FakeResponse(200, "<html>hello</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe") == "<html>hello</html>"


def test_fetch_page_raises_when_robots_disallows(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /\n")
        raise AssertionError("page should not be fetched when robots.txt disallows it")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    with pytest.raises(scraping.ScrapeDisallowedError):
        scraping.fetch_page("https://example.com/recipe")


def test_fetch_page_allows_when_robots_txt_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe") == "<html>ok</html>"


def test_fetch_page_allows_when_robots_txt_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            raise httpx.ConnectError("boom")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe") == "<html>ok</html>"


def test_fetch_page_truncates_html_to_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraping.settings, "max_html_chars", 10)

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "x" * 100)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe") == "x" * 10


def test_fetch_page_raises_on_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(500, "")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        scraping.fetch_page("https://example.com/recipe")
