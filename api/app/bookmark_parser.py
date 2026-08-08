from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Browser bookmark exports (Chrome/Firefox/Safari/IE "Export bookmarks/favorites to HTML") all
# produce the same Netscape Bookmark File format: a flat/nested <DL><DT><A HREF="...">Title</A>
# structure. bs4's default parser doesn't need the format to be well-formed XHTML (it isn't —
# Netscape bookmark files are deliberately loose, unclosed <DT>/<p> tags and all), so a plain
# find_all("a") over the whole soup picks up every link regardless of folder nesting depth.
_MAX_LINKS = 1000  # generous headroom over what anyone will select in one go; just a sanity cap


@dataclass(frozen=True)
class BookmarkLink:
    title: str
    url: str


def parse_bookmark_links(html: str) -> list[BookmarkLink]:
    """Extracts candidate recipe links from an uploaded bookmark-export HTML file.

    Only http(s) links are returned — bookmark files also carry browser-internal entries
    (Firefox's `place:` special-folder queries, `javascript:` bookmarklets) that are never
    fetchable pages. Deduplicated by URL, keeping the first title seen for a repeated URL and
    preserving the file's own order (folder order, then link order within a folder).
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[BookmarkLink] = []

    for tag in soup.find_all("a", href=True):
        url = tag["href"].strip()
        if url in seen:
            continue
        if (urlparse(url).scheme or "").lower() not in ("http", "https"):
            continue
        seen.add(url)
        title = tag.get_text(strip=True) or url
        links.append(BookmarkLink(title=title, url=url))
        if len(links) >= _MAX_LINKS:
            break

    return links
