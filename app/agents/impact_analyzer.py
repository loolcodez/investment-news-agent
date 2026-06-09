from __future__ import annotations

import logging
from typing import Iterable, List

from app.agents.base import BaseAgent
from app.core.config import AppConfig
from app.core.models import FilteredNews, NewsInsights
from app.services.openai_service import OpenAIAnalysisService

log = logging.getLogger(__name__)


class ImpactAnalyzerAgent(BaseAgent):
    def __init__(self, analysis_service: OpenAIAnalysisService) -> None:
        super().__init__(name="impact_analyzer")
        self.analysis_service = analysis_service

    async def run(self, data: tuple[list[FilteredNews], AppConfig]) -> List[NewsInsights]:
        filtered_news, config = data
        if not filtered_news:
            log.info("No news to analyze")
            return []

        insights = await self.analysis_service.analyze_batch(
            filtered_news,
            default_symbols=config.watchlist,
            default_themes=config.themes,
        )
        log.info("Generated %s analyses", len(insights))
        return insights
