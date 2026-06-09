from __future__ import annotations

import asyncio
import logging
import calendar
from datetime import datetime, timezone
from typing import Iterable, List

import feedparser
import httpx

from app.core.config import FeedConfig
from app.core.models import NewsItem
from app.services.url_utils import canonicalize_url

log = logging.getLogger(__name__)


class RSSService:
    def __init__(self, timeout_seconds: int = 30, user_agent: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or "investment-news-agent/0.1"

    async def fetch_news(self, feeds: Iterable[FeedConfig], max_items: int | None = None) -> List[NewsItem]:
        enabled_feeds = [feed for feed in feeds if feed.enabled]
        if not enabled_feeds:
            return []

        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            tasks = [self._fetch_feed(client, feed) for feed in enabled_feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        items: List[NewsItem] = []
        for feed, result in zip(enabled_feeds, results, strict=False):
            if isinstance(result, Exception):
                log.warning("Failed to fetch feed %s: %s", feed.name, result)
                continue
            items.extend(result)

        fallback_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
        items.sort(key=lambda item: item.published_at or fallback_dt, reverse=True)
        if max_items is not None:
            items = items[:max_items]
        return items

    async def _fetch_feed(self, client: httpx.AsyncClient, feed: FeedConfig) -> List[NewsItem]:
        response = await client.get(str(feed.url), follow_redirects=True)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        items: List[NewsItem] = []

        for entry in parsed.entries:
            url = entry.get("link") or entry.get("id")
            title = entry.get("title")
            if not url or not title:
                continue

            summary = entry.get("summary") or entry.get("description")
            published_at = self._extract_datetime(entry)
            canonical_url = canonicalize_url(url)

            items.append(
                NewsItem(
                    title=title.strip(),
                    url=url,
                    source=feed.name,
                    published_at=published_at,
                    summary=summary.strip() if isinstance(summary, str) else summary,
                    canonical_url=canonical_url,
                    raw=entry,
                )
            )

        return items

    @staticmethod
    def _extract_datetime(entry: dict) -> datetime | None:
        if "published_parsed" in entry and entry["published_parsed"]:
            return datetime.fromtimestamp(
                calendar.timegm(entry["published_parsed"]), tz=timezone.utc
            )
        if published := entry.get("published"):
            try:
                return datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None
