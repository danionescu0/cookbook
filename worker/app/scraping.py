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
_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
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


class ScrapeDisallowedError(Exception):
    pass


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

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
