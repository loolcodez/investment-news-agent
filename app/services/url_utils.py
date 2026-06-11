from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse

from app.core.models import NewsItem


def canonicalize_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


_WHITESPACE_RE = re.compile(r"\s+")
_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    lowered = title.lower().strip()
    lowered = _WHITESPACE_RE.sub(" ", lowered)
    lowered = _ALNUM_RE.sub("", lowered)
    return lowered.strip()


def make_fingerprint(item: NewsItem) -> str:
    base = item.canonical_url or item.url
    if base:
        key = canonicalize_url(base)
    else:
        normalized = normalize_title(item.title)
        key = f"{normalized}|{item.source.lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
