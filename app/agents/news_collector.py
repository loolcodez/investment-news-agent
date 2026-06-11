from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.core.config import AppConfig
from app.core.models import CollectorResult, CollectorStats, FilteredNews, NewsItem
from app.repositories.news_repository import NewsRepository
from app.services.dedup_service import DeduplicationService
from app.services.relevance_filter import RelevanceFilterService
from app.services.rss_service import RSSService
from app.services.url_utils import make_fingerprint

log = logging.getLogger(__name__)


class NewsCollectorAgent(BaseAgent):
    def __init__(
        self,
        rss_service: RSSService,
        dedup_service: DeduplicationService,
        relevance_filter: RelevanceFilterService,
        news_repository: NewsRepository,
    ) -> None:
        super().__init__(name="news_collector")
        self.rss_service = rss_service
        self.dedup_service = dedup_service
        self.relevance_filter = relevance_filter
        self.repository = news_repository

    async def run(self, config: AppConfig) -> CollectorResult:
        max_fetch = config.limits.max_items_per_run * 3
        raw_items = await self.rss_service.fetch_news(config.enabled_feeds, max_items=max_fetch)
        stats = CollectorStats(fetched_count=len(raw_items))
        log.info("Fetched %s raw news items", stats.fetched_count)

        deduped_items = self.dedup_service.deduplicate(raw_items)
        stats.deduped_count = len(deduped_items)
        log.info("Deduplicated down to %s items", stats.deduped_count)
        now = datetime.now(timezone.utc)
        candidates: list[NewsItem] = []
        for item in deduped_items:
            fingerprint = make_fingerprint(item)
            item.fingerprint = fingerprint
            record = self.repository.upsert_news_item(item, fingerprint, now)
            if record.was_new:
                stats.new_items_count += 1
            else:
                stats.already_seen_count += 1
            if record.needs_analysis(now, config.storage.reanalyze_after_hours):
                if not record.was_new and record.analyzed_at is not None:
                    item.seen_before = True
                    item.reanalyze = True
                    stats.reanalyze_count += 1
                candidates.append(item)

        filtered_items = self.relevance_filter.filter_items(
            candidates,
            max_items=config.limits.max_items_per_run,
        )
        stats.analyze_candidate_count = len(filtered_items)
        log.info("Filtered to %s items for OpenAI analysis", stats.analyze_candidate_count)
        return CollectorResult(filtered_news=filtered_items, stats=stats)
