import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config import settings
from app.rate_limiter import DomainRateLimiter

logger = logging.getLogger(__name__)

_rate_limiter = DomainRateLimiter(settings.default_rate_limit_requests_per_minute)


class ScrapeDisallowedError(Exception):
    pass


def _fetch_robots_txt(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = RobotFileParser()
    try:
        response = httpx.get(
            robots_url,
            headers={"User-Agent": settings.scrape_user_agent},
            timeout=settings.scrape_timeout_seconds,
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


def fetch_page(url: str) -> str:
    domain = urlparse(url).netloc
    robots = _fetch_robots_txt(url)

    if not robots.can_fetch(settings.scrape_user_agent, url):
        raise ScrapeDisallowedError(f"robots.txt on {domain} disallows fetching this page")

    crawl_delay = robots.crawl_delay(settings.scrape_user_agent)
    _rate_limiter.wait(domain, float(crawl_delay) if crawl_delay else None)

    response = httpx.get(
        url,
        headers={"User-Agent": settings.scrape_user_agent},
        timeout=settings.scrape_timeout_seconds,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text[: settings.max_html_chars]
