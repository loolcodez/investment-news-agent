from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def canonicalize_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))
