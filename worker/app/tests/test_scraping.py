import httpx
import pytest

from app import scraping
from app.settings_service import SettingsSnapshot


def _snapshot(**overrides: object) -> SettingsSnapshot:
    defaults = dict(
        supported_languages="ro,en",
        default_language="ro",
        anthropic_api_key="",
        calorie_ninjas_api_key="",
        default_rate_limit_requests_per_minute=6,
        scrape_timeout_seconds=15.0,
        max_html_chars=200_000,
        image_max_dimension=1600,
        image_max_size_kb=500,
    )
    defaults.update(overrides)
    return SettingsSnapshot(**defaults)  # type: ignore[arg-type]


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

    assert scraping.fetch_page("https://example.com/recipe", _snapshot()) == "<html>hello</html>"


def test_fetch_page_raises_when_robots_disallows(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /\n")
        raise AssertionError("page should not be fetched when robots.txt disallows it")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    with pytest.raises(scraping.ScrapeDisallowedError):
        scraping.fetch_page("https://example.com/recipe", _snapshot())


def test_fetch_page_allows_when_robots_txt_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe", _snapshot()) == "<html>ok</html>"


def test_fetch_page_allows_when_robots_txt_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            raise httpx.ConnectError("boom")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    assert scraping.fetch_page("https://example.com/recipe", _snapshot()) == "<html>ok</html>"


def test_fetch_page_truncates_html_to_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "x" * 100)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    result = scraping.fetch_page("https://example.com/recipe", _snapshot(max_html_chars=10))
    assert result == "x" * 10


def test_fetch_page_passes_current_rate_limit_to_rate_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Confirms a rate-limit change made via the Settings backoffice page reaches the rate
    # limiter on the very next fetch, not just at process startup (see rate_limiter.py).
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    calls = []
    monkeypatch.setattr(
        scraping._rate_limiter, "wait", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    scraping.fetch_page(
        "https://example.com/recipe", _snapshot(default_rate_limit_requests_per_minute=42)
    )

    assert calls == [(("example.com", None, 42), {})]


def test_fetch_page_strips_boilerplate_before_returning(monkeypatch: pytest.MonkeyPatch) -> None:
    page_html = (
        "<html><head><script>track();</script><style>.a{color:red}</style></head>"
        "<body><nav>Menu</nav>"
        "<h1>Grandma's Soup</h1>"
        "<img src='/soup.jpg' class='hero' data-lazy='1' onclick='zoom()'>"
        "<!-- an ad slot goes here -->"
        "<footer>Copyright 2026</footer></body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "track()" not in result
    assert "color:red" not in result
    assert "<nav>" not in result
    assert "<footer>" not in result
    assert "ad slot" not in result
    assert "Grandma's Soup" in result
    # the image src (needed for recipe photo extraction) survives; noisy attributes don't
    assert "/soup.jpg" in result
    assert "class=" not in result
    assert "data-lazy" not in result
    assert "onclick" not in result


def test_fetch_page_truncates_after_cleaning_not_before(monkeypatch: pytest.MonkeyPatch) -> None:
    # A big <script> block shouldn't eat into the max_html_chars budget that's meant for
    # actual recipe content — cleaning must happen before truncation, not after.
    page_html = "<script>" + ("x" * 500) + "</script><p>short recipe text</p>"

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    result = scraping.fetch_page("https://example.com/recipe", _snapshot(max_html_chars=100))

    assert "short recipe text" in result


def test_fetch_page_raises_on_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(500, "")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        scraping.fetch_page("https://example.com/recipe", _snapshot())
