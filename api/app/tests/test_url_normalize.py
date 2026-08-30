import pytest

from app.url_normalize import normalize_source_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Instagram's share-sheet tracking token (?igsi=...) differs on every re-share/re-copy of
        # the same reel — stripped so re-sharing a link you already imported is recognized as the
        # same URL. See README Design Decisions, "Instagram URL normalization".
        (
            "https://www.instagram.com/reel/DaPg51KNxhk/?igsi=MTRtY2xsZ3RhMTB2NA==",
            "https://www.instagram.com/reel/DaPg51KNxhk/",
        ),
        (
            "https://www.instagram.com/reel/DaPg51KNxhk/?igsi=MTRtY2",
            "https://www.instagram.com/reel/DaPg51KNxhk/",
        ),
        # Already-canonical (no query string) is left alone.
        ("https://www.instagram.com/reel/DaPg51KNxhk/", "https://www.instagram.com/reel/DaPg51KNxhk/"),
        # Missing trailing slash is added.
        ("https://www.instagram.com/p/DPa1bP5DZhP", "https://www.instagram.com/p/DPa1bP5DZhP/"),
        # Bare instagram.com and the instagr.am short host both count.
        ("https://instagram.com/reel/DPa1bP5DZhP/?igsi=abc", "https://instagram.com/reel/DPa1bP5DZhP/"),
        ("https://instagr.am/p/DPa1bP5DZhP/?igsi=abc", "https://instagr.am/p/DPa1bP5DZhP/"),
        # A fragment is dropped too, same as the query string.
        ("https://www.instagram.com/reel/DPa1bP5DZhP/#comments", "https://www.instagram.com/reel/DPa1bP5DZhP/"),
        # Non-Instagram hosts are untouched, even ones with "instagram" in the name/path — query
        # params can be genuinely content-identifying on an arbitrary recipe site.
        ("https://example.com/recipe?utm_source=newsletter", "https://example.com/recipe?utm_source=newsletter"),
        ("https://not-instagram.com/p/DPa1bP5DZhP/?igsi=abc", "https://not-instagram.com/p/DPa1bP5DZhP/?igsi=abc"),
        # Leading/trailing whitespace from a pasted URL is trimmed regardless of host.
        ("  https://example.com/recipe  ", "https://example.com/recipe"),
    ],
)
def test_normalize_source_url(url: str, expected: str) -> None:
    assert normalize_source_url(url) == expected
