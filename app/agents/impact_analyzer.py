from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List

from app.agents.base import BaseAgent
from app.core.config import AppConfig
from app.core.models import FilteredNews, NewsInsights
from app.repositories.news_repository import NewsRepository
from app.services.openai_service import OpenAIAnalysisService

log = logging.getLogger(__name__)


class ImpactAnalyzerAgent(BaseAgent):
    def __init__(self, analysis_service: OpenAIAnalysisService, repository: NewsRepository) -> None:
        super().__init__(name="impact_analyzer")
        self.analysis_service = analysis_service
        self.repository = repository

    async def run(self, data: tuple[list[FilteredNews], AppConfig, int | None]) -> List[NewsInsights]:
        filtered_news, config, run_id = data
        if not filtered_news:
            log.info("No news to analyze")
            return []

        insights = await self.analysis_service.analyze_batch(
            filtered_news,
            default_symbols=config.watchlist,
            default_themes=config.themes,
        )
        log.info("Generated %s analyses", len(insights))
        now = datetime.now(timezone.utc)
        for insight in insights:
            fingerprint = insight.item.fingerprint
            if fingerprint:
                self.repository.save_analyses(fingerprint, insight.analyses, now, run_id)
                self.repository.mark_analyzed(fingerprint, now)
        return insights
