import pytest
from playwright.sync_api import Error as PlaywrightError

from app import instagram_client
from app.instagram_client import InstagramFetchError, fetch_instagram_post


class FakeLocator:
    def __init__(self, count: int = 0, attribute: str | None = None) -> None:
        self._count = count
        self._attribute = attribute

    def count(self) -> int:
        return self._count

    def get_attribute(self, name: str) -> str | None:
        return self._attribute


class FakePage:
    def __init__(self, body_text: str, og_image: str | None, has_password_field: bool) -> None:
        self._body_text = body_text
        self._og_image = og_image
        self._has_password_field = has_password_field
        self.goto_calls: list[str] = []

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_calls.append(url)

    def wait_for_timeout(self, ms: int) -> None:
        pass

    def locator(self, selector: str) -> FakeLocator:
        if "password" in selector:
            return FakeLocator(count=1 if self._has_password_field else 0)
        if "og:image" in selector:
            return FakeLocator(attribute=self._og_image)
        raise AssertionError(f"unexpected selector: {selector!r}")

    def evaluate(self, script: str) -> str:
        return self._body_text


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self._page = page

    def new_page(self) -> FakePage:
        return self._page


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.closed = False

    def new_context(self, **kwargs: object) -> FakeContext:
        return FakeContext(self._page)

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self._browser = browser

    def launch(self, headless: bool) -> FakeBrowser:
        return self._browser


class FakePlaywright:
    def __init__(self, page: FakePage) -> None:
        self.chromium = FakeChromium(FakeBrowser(page))


class FakeSyncPlaywright:
    def __init__(self, page: FakePage) -> None:
        self._page = page

    def __enter__(self) -> FakePlaywright:
        return FakePlaywright(self._page)

    def __exit__(self, *args: object) -> None:
        pass


_REAL_POST_TEXT = "Log In\nSign Up\n" + ("Batoane sanatoase cu mere. Reteta: mere, fulgi de ovaz. " * 5)


def test_fetch_instagram_post_returns_text_and_image(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage(
        body_text=_REAL_POST_TEXT,
        og_image="https://scontent.cdninstagram.com/photo.jpg",
        has_password_field=False,
    )
    monkeypatch.setattr(
        instagram_client, "sync_playwright", lambda: FakeSyncPlaywright(page)
    )

    result = fetch_instagram_post("https://www.instagram.com/p/abc123/", timeout_seconds=15)

    assert result.text == _REAL_POST_TEXT
    assert result.image_url == "https://scontent.cdninstagram.com/photo.jpg"
    assert page.goto_calls == ["https://www.instagram.com/p/abc123/"]


def test_fetch_instagram_post_raises_when_login_wall_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage(body_text=_REAL_POST_TEXT, og_image=None, has_password_field=True)
    monkeypatch.setattr(
        instagram_client, "sync_playwright", lambda: FakeSyncPlaywright(page)
    )

    with pytest.raises(InstagramFetchError, match="asked for a login"):
        fetch_instagram_post("https://www.instagram.com/p/private/", timeout_seconds=15)


def test_fetch_instagram_post_raises_when_body_text_too_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # e.g. a blocked/deleted post renders almost no real content, unlike a genuine post's
    # caption + comments — see the length threshold's rationale in instagram_client.py.
    page = FakePage(body_text="Sorry, this page isn't available.", og_image=None, has_password_field=False)
    monkeypatch.setattr(
        instagram_client, "sync_playwright", lambda: FakeSyncPlaywright(page)
    )

    with pytest.raises(InstagramFetchError, match="Couldn't read this Instagram post"):
        fetch_instagram_post("https://www.instagram.com/p/gone/", timeout_seconds=15)


def test_fetch_instagram_post_wraps_playwright_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class RaisingSyncPlaywright:
        def __enter__(self) -> "RaisingSyncPlaywright":
            raise PlaywrightError("navigation timeout")

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(instagram_client, "sync_playwright", lambda: RaisingSyncPlaywright())

    with pytest.raises(InstagramFetchError, match="failed to load Instagram post"):
        fetch_instagram_post("https://www.instagram.com/p/timeout/", timeout_seconds=15)
