from __future__ import annotations

import logging
from dataclasses import replace
from difflib import SequenceMatcher
from datetime import datetime
from typing import Iterable, List

from app.core.models import NewsItem
from app.services.url_utils import canonicalize_url

log = logging.getLogger(__name__)


class DeduplicationService:
    def __init__(self, title_similarity_threshold: float = 0.88):
        self.title_similarity_threshold = title_similarity_threshold

    def deduplicate(self, items: Iterable[NewsItem]) -> List[NewsItem]:
        by_url: dict[str, NewsItem] = {}
        for item in items:
            canonical_url = canonicalize_url(item.url)
            normalized = replace(item, canonical_url=canonical_url)
            existing = by_url.get(canonical_url)
            if existing is None or self._is_newer(normalized, existing):
                by_url[canonical_url] = normalized

        unique_items = list(by_url.values())
        unique_items.sort(key=self._sort_key, reverse=True)

        deduped: List[NewsItem] = []
        for candidate in unique_items:
            if not self._is_similar_to_any(candidate, deduped):
                deduped.append(candidate)

        deduped.sort(key=self._sort_key, reverse=True)
        return deduped

    @staticmethod
    def _is_newer(candidate: NewsItem, existing: NewsItem) -> bool:
        if candidate.published_at and existing.published_at:
            return candidate.published_at >= existing.published_at
        if candidate.published_at and not existing.published_at:
            return True
        return False

    def _is_similar_to_any(self, candidate: NewsItem, others: Iterable[NewsItem]) -> bool:
        candidate_title = candidate.title.lower()
        for other in others:
            ratio = SequenceMatcher(None, candidate_title, other.title.lower()).ratio()
            if ratio >= self.title_similarity_threshold:
                log.debug(
                    "Dropping '%s' as duplicate of '%s' (%.2f)",
                    candidate.title,
                    other.title,
                    ratio,
                )
                return True
        return False

    @staticmethod
    def _sort_key(item: NewsItem) -> float:
        if isinstance(item.published_at, datetime):
            return item.published_at.timestamp()
        return 0.0
