from urllib.parse import urlparse, urlunparse

# Instagram appends a per-share tracking token (?igsi=...) to every link generated from its share
# sheet — the same reel/post gets a different query string every time it's re-shared or
# re-copied. The duplicate-import check (routers/imports.py) is an exact string match, so without
# normalizing this first, re-sharing a link you already imported reads as a brand-new URL: a real
# prod case imported the same reel three times this way (see README Design Decisions, "Instagram
# URL normalization"). Query string and fragment carry no content-identifying information for
# Instagram (the id in the path is what's fetched), so they're dropped entirely rather than
# selectively stripping known tracking params — simpler, and robust to Instagram adding new ones.
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}


def normalize_source_url(url: str) -> str:
    """Canonicalizes a submitted recipe source URL before it's compared against or stored as
    ImportJob.source / Recipe.source_url, so re-sharing/re-copying a link to the same content is
    recognized as the same URL. A no-op for any host other than Instagram — see the module
    docstring above for why Instagram specifically needed this, and INSTAGRAM_HOSTS's comment for
    what "revisit if too naive" (routers/imports.py's original duplicate-check comment) turned out
    to mean in practice.
    """
    stripped = url.strip()
    parsed = urlparse(stripped)
    host = (parsed.hostname or "").lower()
    if host not in INSTAGRAM_HOSTS:
        return stripped

    path = parsed.path if parsed.path.endswith("/") else f"{parsed.path}/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
