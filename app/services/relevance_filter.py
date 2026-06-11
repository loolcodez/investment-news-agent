from __future__ import annotations

import logging
from typing import Iterable, List, Sequence

from app.core.models import FilteredNews, NewsItem

log = logging.getLogger(__name__)


class RelevanceFilterService:
    def __init__(
        self,
        watchlist: Sequence[str],
        themes: Sequence[str],
        min_keyword_hits: int = 1,
        fallback_keep: int = 5,
    ):
        self.watch_keywords = {symbol: {symbol.lower()} for symbol in watchlist}
        self.theme_keywords = {theme: {theme.lower()} for theme in themes}
        self.min_keyword_hits = min_keyword_hits
        self.fallback_keep = fallback_keep

    def filter_items(self, items: Iterable[NewsItem], max_items: int | None = None) -> List[FilteredNews]:
        scored: List[tuple[int, float, NewsItem, List[str], List[str]]] = []
        for item in items:
            text = self._build_text(item)
            symbol_hits = self._match_keywords(text, self.watch_keywords)
            theme_hits = self._match_keywords(text, self.theme_keywords)
            total_hits = len(symbol_hits) + len(theme_hits)

            if total_hits >= self.min_keyword_hits or len(scored) < self.fallback_keep:
                recency_weight = item.published_at.timestamp() if item.published_at else 0.0
                scored.append((total_hits, recency_weight, item, symbol_hits, theme_hits))
            else:
                log.debug("Skipping news '%s' as low relevance", item.title)

        scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)

        if max_items is not None:
            scored = scored[:max_items]

        return [
            FilteredNews(
                item=entry[2],
                symbols=entry[3],
                themes=entry[4],
                fingerprint=getattr(entry[2], "fingerprint", None),
                reanalyze=getattr(entry[2], "reanalyze", False),
            )
            for entry in scored
        ]

    @staticmethod
    def _build_text(item: NewsItem) -> str:
        summary = item.summary or ""
        return f"{item.title}\n{summary}".lower()

    @staticmethod
    def _match_keywords(text: str, keyword_map: dict[str, set[str]]) -> List[str]:
        hits: List[str] = []
        for label, keywords in keyword_map.items():
            if any(keyword in text for keyword in keywords):
                hits.append(label)
        return hits
