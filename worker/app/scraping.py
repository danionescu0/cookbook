import json
import logging
import re
from urllib.parse import parse_qs, urlparse
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


# Real-world regression: some JS-rendered storefronts (Shopify blog themes especially) leave
# the actual article/recipe text out of the raw HTML entirely — it's injected into the DOM by
# JavaScript after load, so a visitor's browser shows it fine but a plain httpx fetch sees an
# empty <main>. The same page's SEO plugin (e.g. "AVADA SEO Suite") often already embeds the full
# article text in a JSON-LD Article/BlogPosting/NewsArticle block's `articleBody`, meant for
# search engines rather than a browser DOM — that text is recovered below before <script> tags
# are stripped as noise. See README Design Decisions, "Recovering recipe text from JSON-LD on
# JS-rendered pages".
_ARTICLE_JSON_LD_TYPES = frozenset({"Article", "BlogPosting", "NewsArticle"})


def _extract_json_ld_article_bodies(soup: BeautifulSoup) -> list[str]:
    bodies = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            item_types = item.get("@type")
            item_types = item_types if isinstance(item_types, list) else [item_types]
            if not any(t in _ARTICLE_JSON_LD_TYPES for t in item_types):
                continue
            body = item.get("articleBody")
            if isinstance(body, str) and body.strip():
                bodies.append(body.strip())
    return bodies


_WIDTH_QUERY_PARAM_RE = re.compile(r"([?&]width=)\d+")


def _widen_templated_lazy_url(url: str, img) -> str:
    # Real-world regression: some lazy-load libraries (seen on a Shopify theme) don't put the
    # final image URL in data-src at all — they put a *template* there, pre-filled with a tiny
    # placeholder width (width=1, a "load almost nothing yet" trick), and a sibling data-widths
    # attribute lists the real candidate widths the page's own JS picks from once it decides what
    # to render. Promoting data-src as-is "succeeds" (a valid, real image download) while actually
    # producing a 1x1 placeholder pixel — no error anywhere, just a uselessly tiny photo. Detected
    # here by the presence of both a `width=` query param and a `data-widths` list, and resolved
    # by substituting in the largest available width, the same value the real page would settle on
    # for a full-size display.
    widths_json = img.get("data-widths")
    if not widths_json or not _WIDTH_QUERY_PARAM_RE.search(url):
        return url
    try:
        widths = json.loads(widths_json)
        largest = max(int(w) for w in widths)
    except (TypeError, ValueError):
        return url
    return _WIDTH_QUERY_PARAM_RE.sub(rf"\g<1>{largest}", url)


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
                img["src"] = _widen_templated_lazy_url(first_url, img)
                break


class ScrapeDisallowedError(Exception):
    pass


_GOOGLE_HOST_RE = re.compile(r"^(www\.)?google\.[a-z.]{2,24}$", re.IGNORECASE)


def _resolve_google_redirect_notice(response: httpx.Response) -> str | None:
    # Real-world regression: a Google AMP-viewer link (google.com/amp/s/<url>) whose target no
    # longer has a live AMP page doesn't 3xx-redirect all the way to the real article — httpx (like
    # any HTTP client, this isn't fixable with follow_redirects) follows the real redirect chain
    # down to a Google-served interstitial "click through to continue" page instead
    # (google.com/url?q=<real-url>&...), a genuine 200 OK with real (if useless) HTML, so there's
    # no further redirect to follow automatically — fetch_page was handing Claude that notice page
    # instead of the actual recipe. The real destination is the q= query param on that landing
    # page's own URL, read directly rather than parsed out of the interstitial's HTML text (which
    # is locale-dependent — "Notă de redirecționare" in Romanian, "Redirect Notice" in English,
    # etc. — the URL shape is the one part of this that's stable across locales). Also fires for a
    # plain google.com/url?q=... link pasted directly, a common copy-paste artifact from a Google
    # Search results page — not just the AMP case.
    parsed = urlparse(str(response.url))
    if not _GOOGLE_HOST_RE.match(parsed.netloc) or parsed.path != "/url":
        return None
    target = parse_qs(parsed.query).get("q", [None])[0]
    return target or None


def _is_google_redirect_url(url: str) -> bool:
    # Real-world regression, found *after* _resolve_google_redirect_notice above: Google's own
    # robots.txt makes Python's stdlib urllib.robotparser mis-parse entirely for this domain —
    # confirmed live, it disallows even a path Google's own file explicitly `Allow`s (e.g.
    # /search/about). That's a genuine parser limitation (it doesn't correctly group multiple
    # `User-agent:` lines sharing one rule block, which Google's robots.txt relies on), not
    # something specific to this feature, and not worth risking a robots.txt parser swap for every
    # other site over. Sidestepped narrowly here instead: an AMP-viewer or /url redirect link isn't
    # a page to scrape in the first place — it's a redirect mechanism, the same as an ordinary HTTP
    # 3xx, which this codebase already doesn't apply a fresh robots.txt check to per hop. The real
    # destination's own domain still gets a full, fresh robots.txt + rate-limit check via the
    # recursive fetch_page call once resolved — nothing about real content-scraping ethics is
    # bypassed, only the mechanical hop through Google's own redirect page.
    parsed = urlparse(url)
    if not _GOOGLE_HOST_RE.match(parsed.netloc):
        return False
    return parsed.path == "/url" or parsed.path.startswith("/amp/")


def _clean_html(html: str) -> str:
    # lxml, not the stdlib html.parser: a real page (mancaregatita.ro) had a malformed <link> tag
    # deep in its <head> that desynced html.parser's open-tag stack, silently nesting the entire
    # real article body (text *and* the hero <img>) inside spurious tags that got decompose()'d as
    # noise below — the recipe wasn't JS-rendered after all, html.parser just corrupted the tree
    # trying to parse it. lxml (libxml2-backed, spec-compliant on void elements like <link>) parses
    # the same document correctly. See README Design Decisions, "Recovering recipe text from
    # JSON-LD on JS-rendered pages" for the fuller story — that JSON-LD fallback stays in place
    # too, for pages that really are JS-only.
    soup = BeautifulSoup(html, "lxml")

    article_bodies = _extract_json_ld_article_bodies(soup)

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
    if article_bodies:
        # Longest wins when a page embeds more than one near-duplicate Article block (seen in
        # practice: one plainer summary variant alongside the full one) — cheap dedup without
        # needing exact-match comparison.
        recovered = soup.new_tag("div")
        recovered.string = max(article_bodies, key=len)
        root.append(recovered)

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


def fetch_page(url: str, app_settings: SettingsSnapshot, _redirect_depth: int = 0) -> tuple[str, str]:
    """Returns (final_url, cleaned_html). final_url is the page actually fetched — usually just
    `url` back again, but can differ after a real HTTP redirect chain or a resolved Google
    redirect-notice page (see _resolve_google_redirect_notice) — callers that resolve relative
    URLs found on the page (images, etc.) should join against final_url, not the original url."""
    domain = urlparse(url).netloc

    if _is_google_redirect_url(url):
        # No robots.txt permission check for this one hop — see _is_google_redirect_url for why.
        # Still rate-limited, same as any other domain.
        _rate_limiter.wait(domain, None, app_settings.default_rate_limit_requests_per_minute)
    else:
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

    real_target = _resolve_google_redirect_notice(response)
    if real_target is not None and _redirect_depth < 3:
        # A fresh robots.txt check + rate limit for whatever domain this turns out to be, same as
        # any other fetch — recursing into fetch_page rather than special-casing gets that for
        # free. Depth-capped defensively; a chain of Google notices pointing at each other isn't a
        # real scenario, but nothing should ever recurse unbounded on attacker-controlled input.
        return fetch_page(real_target, app_settings, _redirect_depth=_redirect_depth + 1)

    return str(response.url), _clean_html(response.text)[: app_settings.max_html_chars]
