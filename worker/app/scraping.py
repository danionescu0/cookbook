import logging
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Comment

from app.config import settings
from app.rate_limiter import DomainRateLimiter
from app.settings_service import SettingsSnapshot

logger = logging.getLogger(__name__)

# Constructor value is only ever a fallback (see DomainRateLimiter.wait) — every real call from
# fetch_page passes the current DB-backed rate explicitly, so this never actually applies.
_rate_limiter = DomainRateLimiter(6)

# Tags that never carry recipe content, just page chrome/boilerplate — stripping them
# (scripts and styles especially) is what keeps a raw page dump from burning most of the
# max_html_chars budget, and therefore most of the Claude input-token cost, on noise.
# NOT noscript: some sites (e.g. simplyrecipes.com) put the only real <img src="..."> for a
# lazy-loaded photo inside a <noscript> fallback — see _promote_lazy_image_sources below for the
# more common case (a real URL in a data-* attribute instead), but this is the other shape of the
# same "the real image URL isn't in a plain src" problem, so it's not safe to blanket-strip.
_NOISE_TAGS = (
    "script",
    "style",
    "svg",
    "iframe",
    "link",
    "meta",
    "form",
    "button",
    "template",
    "nav",
    "footer",
    "header",
    "aside",
)
_NOISE_ATTRS = frozenset({"class", "style", "role"})
_NOISE_ATTR_PREFIXES = ("data-", "on", "aria-")
# Common lazy-load attribute names (lazysizes.js and similar libraries) that carry an image's
# real URL while `src` holds a tiny placeholder (or is absent) until JS runs. Checked in order;
# the first one present wins. Promoted into `src` *before* the generic `data-*` stripping above
# would otherwise delete them — without this, every lazy-loaded photo (the hero image, most step
# photos on many recipe blogs) silently vanishes from what Claude sees.
_LAZY_IMAGE_SRC_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-srcset")


def _promote_lazy_image_sources(soup: BeautifulSoup) -> None:
    for img in soup.find_all("img"):
        current_src = img.get("src", "")
        if current_src and not current_src.startswith("data:"):
            continue  # already has a real (non-placeholder) src
        for attr in _LAZY_IMAGE_SRC_ATTRS:
            value = img.get(attr)
            if not value:
                continue
            # A srcset-shaped value is "url descriptor, url descriptor, ..." — take the first URL.
            first_url = value.split(",")[0].strip().split(" ")[0]
            if first_url:
                img["src"] = first_url
                break


class ScrapeDisallowedError(Exception):
    pass


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    _promote_lazy_image_sources(soup)

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr in _NOISE_ATTRS or attr.startswith(_NOISE_ATTR_PREFIXES):
                del tag.attrs[attr]

    root = soup.body or soup
    return re.sub(r"\n{2,}", "\n", str(root)).strip()


def _fetch_robots_txt(url: str, timeout_seconds: float) -> RobotFileParser:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = RobotFileParser()
    try:
        response = httpx.get(
            robots_url,
            headers={"User-Agent": settings.scrape_user_agent},
            timeout=timeout_seconds,
        )
    except httpx.HTTPError:
        # Unreachable robots.txt (DNS/connect/timeout/etc): treat as if none was published.
        parser.allow_all = True
        return parser

    if response.status_code >= 400:
        # No robots.txt published (404) or otherwise inaccessible: allow, fall back to the
        # default rate limit.
        parser.allow_all = True
    else:
        parser.parse(response.text.splitlines())
    return parser


def fetch_page(url: str, app_settings: SettingsSnapshot) -> str:
    domain = urlparse(url).netloc
    robots = _fetch_robots_txt(url, app_settings.scrape_timeout_seconds)

    if not robots.can_fetch(settings.scrape_user_agent, url):
        raise ScrapeDisallowedError(f"robots.txt on {domain} disallows fetching this page")

    crawl_delay = robots.crawl_delay(settings.scrape_user_agent)
    _rate_limiter.wait(
        domain,
        float(crawl_delay) if crawl_delay else None,
        app_settings.default_rate_limit_requests_per_minute,
    )

    response = httpx.get(
        url,
        headers={"User-Agent": settings.scrape_user_agent},
        timeout=app_settings.scrape_timeout_seconds,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _clean_html(response.text)[: app_settings.max_html_chars]
