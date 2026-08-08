from app.bookmark_parser import BookmarkLink, parse_bookmark_links
from app import bookmark_parser

# A realistic (trimmed) Netscape bookmark export, the format Chrome/Firefox/Safari/IE all
# produce — unclosed <DT>/<p> tags and all, since that's how real exports look.
_SAMPLE_HTML = """
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3>Recipes</H3>
    <DL><p>
        <DT><A HREF="https://example.com/cake" ADD_DATE="1700000000">Chocolate Cake</A>
        <DT><A HREF="https://example.com/soup" ADD_DATE="1700000001">Soup</A>
    </DL><p>
    <DT><A HREF="javascript:void(0)">A bookmarklet</A>
    <DT><A HREF="place:sort=1&type=6">Recently Bookmarked</A>
    <DT><A HREF="https://example.com/cake" ADD_DATE="1700000002">Chocolate Cake (duplicate)</A>
    <DT><A HREF="  https://example.com/pasta  ">   </A>
</DL><p>
"""


def test_parse_bookmark_links_extracts_http_links_only() -> None:
    links = parse_bookmark_links(_SAMPLE_HTML)

    urls = [link.url for link in links]
    assert "https://example.com/cake" in urls
    assert "https://example.com/soup" in urls
    assert not any(url.startswith("javascript:") for url in urls)
    assert not any(url.startswith("place:") for url in urls)


def test_parse_bookmark_links_dedupes_by_url_keeping_first_title() -> None:
    links = parse_bookmark_links(_SAMPLE_HTML)

    cake_links = [link for link in links if link.url == "https://example.com/cake"]
    assert cake_links == [BookmarkLink(title="Chocolate Cake", url="https://example.com/cake")]


def test_parse_bookmark_links_falls_back_to_url_when_link_text_is_blank() -> None:
    links = parse_bookmark_links(_SAMPLE_HTML)

    pasta = next(link for link in links if link.url == "https://example.com/pasta")
    assert pasta.title == "https://example.com/pasta"


def test_parse_bookmark_links_preserves_file_order() -> None:
    links = parse_bookmark_links(_SAMPLE_HTML)

    urls = [link.url for link in links]
    assert urls == [
        "https://example.com/cake",
        "https://example.com/soup",
        "https://example.com/pasta",
    ]


def test_parse_bookmark_links_returns_empty_list_for_no_links() -> None:
    assert parse_bookmark_links("<html><body>no links here</body></html>") == []


def test_parse_bookmark_links_caps_at_1000_links() -> None:
    html = "".join(f'<DT><A HREF="https://example.com/{i}">Recipe {i}</A>\n' for i in range(1200))

    links = parse_bookmark_links(html)

    assert len(links) == 1000
    assert bookmark_parser._MAX_LINKS == 1000
