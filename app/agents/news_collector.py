from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.core.config import AppConfig
from app.core.models import FilteredNews, NewsItem
from app.repositories.memory_repository import InMemoryNewsRepository
from app.services.dedup_service import DeduplicationService
from app.services.relevance_filter import RelevanceFilterService
from app.services.rss_service import RSSService

log = logging.getLogger(__name__)


class NewsCollectorAgent(BaseAgent):
    def __init__(
        self,
        rss_service: RSSService,
        dedup_service: DeduplicationService,
        relevance_filter: RelevanceFilterService,
        repository: InMemoryNewsRepository,
    ) -> None:
        super().__init__(name="news_collector")
        self.rss_service = rss_service
        self.dedup_service = dedup_service
        self.relevance_filter = relevance_filter
        self.repository = repository

    async def run(self, config: AppConfig) -> list[FilteredNews]:
        max_fetch = config.limits.max_items_per_run * 3
        raw_items = await self.rss_service.fetch_news(config.enabled_feeds, max_items=max_fetch)
        log.info("Fetched %s raw news items", len(raw_items))

        deduped_items = self.dedup_service.deduplicate(raw_items)
        log.info("Deduplicated down to %s items", len(deduped_items))
        self.repository.save_news(deduped_items)

        filtered_items = self.relevance_filter.filter_items(
            deduped_items,
            max_items=config.limits.max_items_per_run,
        )
        log.info("Filtered to %s items for OpenAI analysis", len(filtered_items))
        return filtered_items
