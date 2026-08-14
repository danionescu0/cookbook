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
    # url defaults to "" (not a real URL, but empty netloc never matches the Google
    # redirect-notice check) — only tests exercising that specific behavior need to set a real one.
    def __init__(self, status_code: int = 200, text: str = "", url: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.url = url

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

    # lxml (unlike the stdlib html.parser) always builds a real <body> around bare content, per
    # the HTML5 spec — see _clean_html's own comment for why lxml is used at all.
    _, html = scraping.fetch_page("https://example.com/recipe", _snapshot())
    assert html == "<body>hello</body>"


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

    _, html = scraping.fetch_page("https://example.com/recipe", _snapshot())
    assert html == "<body>ok</body>"


def test_fetch_page_allows_when_robots_txt_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            raise httpx.ConnectError("boom")
        return FakeResponse(200, "<html>ok</html>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, html = scraping.fetch_page("https://example.com/recipe", _snapshot())
    assert html == "<body>ok</body>"


def test_fetch_page_truncates_html_to_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "<p>" + "x" * 100 + "</p>")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot(max_html_chars=10))
    assert len(result) == 10
    assert result == "<body><p>x"


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

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

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


def test_fetch_page_promotes_data_src_for_lazy_loaded_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real-world regression: simplyrecipes.com (and many other recipe sites, via lazysizes.js-style
    # lazy loading) ship <img> tags with no real `src` at all — just a data-src/data-srcset
    # carrying the actual URL, filled in by JS after load. Blanket-stripping data-* attributes
    # (needed to cut tracking-attribute noise) was silently deleting every such image, including
    # the recipe's hero photo, with no error — the import just quietly produced an incomplete
    # `images` list.
    page_html = (
        "<html><body>"
        "<img data-src='https://example.com/hero.jpg' data-srcset='https://example.com/hero2x.jpg 2x'>"
        "<img src='data:image/gif;base64,R0lGODlh' data-src='https://example.com/step1.jpg'>"
        "<img data-srcset='https://example.com/step2.jpg 1x, https://example.com/step2-2x.jpg 2x'>"
        "<img data-original='https://example.com/step3.jpg'>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert 'src="https://example.com/hero.jpg"' in result
    assert 'src="https://example.com/step1.jpg"' in result
    assert 'src="https://example.com/step2.jpg"' in result
    assert 'src="https://example.com/step3.jpg"' in result
    # the placeholder data: URI is replaced, not left alongside the real one
    assert "base64,R0lGODlh" not in result
    # the lazy-load attributes themselves are still stripped once promoted into src
    assert "data-src" not in result
    assert "data-srcset" not in result
    assert "data-original" not in result


def test_fetch_page_widens_a_templated_lazy_src_using_data_widths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real-world regression: mancaregatita.ro's theme puts a *template* URL in data-src, pre-filled
    # with a tiny placeholder (width=1) rather than the real photo — promoting it as-is "succeeds"
    # (a valid download) while actually fetching a 1x1 pixel. The real width to use is listed in
    # the sibling data-widths attribute, the same source the page's own JS reads from.
    page_html = (
        "<html><body>"
        "<img class='lazyloadt4s' data-src='https://example.com/hero.webp?v=1&width=1' "
        "data-widths='[100,200,600,1600]'>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "width=1600" in result
    assert "width=1&" not in result and not result.rstrip('"/>').endswith("width=1")


def test_fetch_page_leaves_a_normal_lazy_src_alone_without_data_widths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The width-templating fix must not misfire on the common case (no data-widths at all) — a
    # plain data-src is still promoted verbatim, unchanged.
    page_html = (
        "<html><body>"
        "<img data-src='https://example.com/hero.jpg?width=1'>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "hero.jpg?width=1" in result


def test_fetch_page_does_not_promote_a_real_src_onto_a_noise_data_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An <img> that already has a real src must not be overwritten by an unrelated data-src
    # (e.g. a higher-res variant meant for a different breakpoint) — only fill the gap, don't
    # clobber a src that already works.
    page_html = (
        "<img src='https://example.com/already-real.jpg' "
        "data-src='https://example.com/should-not-be-used.jpg'>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert 'src="https://example.com/already-real.jpg"' in result
    assert "should-not-be-used.jpg" not in result


def test_fetch_page_keeps_noscript_image_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Some sites put the only <img src="..."> with a real URL inside a <noscript> fallback for a
    # lazy-loaded image, instead of (or alongside) a data-src attribute — noscript used to be
    # blanket-stripped as page chrome, silently losing that image too.
    page_html = (
        "<html><body>"
        "<img data-src='https://example.com/js-version.jpg'>"
        "<noscript><img src='https://example.com/noscript-version.jpg'></noscript>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "noscript-version.jpg" in result


def test_fetch_page_truncates_after_cleaning_not_before(monkeypatch: pytest.MonkeyPatch) -> None:
    # A big <script> block shouldn't eat into the max_html_chars budget that's meant for
    # actual recipe content — cleaning must happen before truncation, not after.
    page_html = "<script>" + ("x" * 500) + "</script><p>short recipe text</p>"

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot(max_html_chars=100))

    assert "short recipe text" in result


def test_fetch_page_recovers_article_body_from_json_ld_on_a_js_rendered_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real-world regression: mancaregatita.ro (a JS-rendered Shopify blog theme) renders the
    # actual recipe text into <main> via JavaScript after load — a plain httpx fetch sees an
    # empty shell there, even though a browser shows the recipe fine. The site's own SEO plugin
    # had already embedded the full text in a JSON-LD Article's articleBody, meant for search
    # engines, which this recovers instead of losing the recipe entirely.
    page_html = (
        "<html><body>"
        "<main></main>"
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org/", "@type": "Article", '
        '"articleBody": "Tomato Soup\\n\\nIngredients\\n2 tomatoes\\n\\nSteps\\nBoil the tomatoes."}'
        "</script>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "Ingredients" in result
    assert "2 tomatoes" in result
    assert "Boil the tomatoes" in result


def test_fetch_page_prefers_the_longest_article_body_when_json_ld_has_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Some SEO plugins emit more than one near-duplicate Article block (a plainer summary
    # alongside the full text) — the shorter one shouldn't win and truncate the real recipe.
    page_html = (
        "<html><body>"
        '<script type="application/ld+json">'
        '{"@type": "Article", "articleBody": "Short summary only."}'
        "</script>"
        '<script type="application/ld+json">'
        '{"@type": "BlogPosting", "articleBody": "Full recipe: ingredients and every step."}'
        "</script>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "Full recipe: ingredients and every step." in result


def test_fetch_page_ignores_non_article_json_ld(monkeypatch: pytest.MonkeyPatch) -> None:
    # A BreadcrumbList (or any other schema.org type without articleBody) must not be treated as
    # recovered page text — only Article/BlogPosting/NewsArticle blocks with real body text count.
    page_html = (
        "<html><body>"
        '<script type="application/ld+json">'
        '{"@type": "BreadcrumbList", "itemListElement": []}'
        "</script>"
        "<p>real page text</p>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "real page text" in result
    assert "BreadcrumbList" not in result


def test_fetch_page_tolerates_malformed_json_ld(monkeypatch: pytest.MonkeyPatch) -> None:
    page_html = (
        "<html><body>"
        '<script type="application/ld+json">{not valid json</script>'
        "<p>real page text</p>"
        "</body></html>"
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, page_html)

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    _, result = scraping.fetch_page("https://example.com/recipe", _snapshot())

    assert "real page text" in result


def test_fetch_page_resolves_a_google_amp_link_through_the_redirect_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real-world regression: a Google AMP-viewer link (google.com/amp/s/<url>) whose target no
    # longer has a live AMP page doesn't 3xx-redirect all the way to the real article — the
    # request lands on a Google-served "click through to continue" notice page instead (a genuine
    # 200 OK, google.com/url?q=<real-url>), which fetch_page used to hand to Claude as-is instead
    # of the actual recipe. No robots.txt fetch for google.com itself (see
    # _is_google_redirect_url) — only for the real target's domain once resolved, exercised here
    # by *not* stubbing a google.com/robots.txt response at all: an unexpected fetch there would
    # hit the catch-all below and fail the test.
    real_page_html = "<html><body><h1>Tocănița de vinete</h1></body></html>"

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url == "https://www.gustos.ro/robots.txt":
            return FakeResponse(404, "")
        if "google.com/amp/s/" in url:
            # The notice page's own URL (what response.url reports) carries the real target in q=.
            return FakeResponse(
                200,
                "<html>Notă de redirecționare</html>",
                url="https://www.google.com/url?q=https://www.gustos.ro/tocanita-de-vinete.html",
            )
        if url == "https://www.gustos.ro/tocanita-de-vinete.html":
            return FakeResponse(200, real_page_html, url=url)
        raise AssertionError(f"unexpected URL fetched: {url}")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    final_url, html = scraping.fetch_page(
        "https://www.google.com/amp/s/www.gustos.ro/amp/tocanita-de-vinete.html", _snapshot()
    )

    assert final_url == "https://www.gustos.ro/tocanita-de-vinete.html"
    assert "Tocănița de vinete" in html


def test_fetch_page_resolves_a_plain_google_url_redirect_link(monkeypatch: pytest.MonkeyPatch) -> None:
    # The same notice page shape shows up from a plain copy-pasted Google Search result link
    # (google.com/url?q=...), not just the AMP case — same fix, same code path.
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        if "google.com/url" in url:
            return FakeResponse(200, "<html>notice</html>", url=url)
        if url == "https://example.com/real-recipe":
            return FakeResponse(200, "<html>the real recipe</html>", url=url)
        raise AssertionError(f"unexpected URL fetched: {url}")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    final_url, html = scraping.fetch_page(
        "https://www.google.com/url?q=https://example.com/real-recipe&sa=T", _snapshot()
    )

    assert final_url == "https://example.com/real-recipe"
    assert "the real recipe" in html


def test_fetch_page_does_not_treat_an_ordinary_page_as_a_google_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A page that just happens to live at a path called /url on a non-Google domain must not be
    # mistaken for the notice page — the host check matters, not just the path.
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(200, "<p>a real recipe page</p>", url="https://example.com/url?q=1")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    final_url, html = scraping.fetch_page("https://example.com/url?q=1", _snapshot())

    assert final_url == "https://example.com/url?q=1"
    assert "a real recipe page" in html


def test_fetch_page_raises_on_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/robots.txt"):
            return FakeResponse(404, "")
        return FakeResponse(500, "")

    monkeypatch.setattr(scraping.httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        scraping.fetch_page("https://example.com/recipe", _snapshot())
