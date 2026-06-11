from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.agents.base import BaseAgent
from app.repositories.news_repository import NewsRepository
from app.services.daily_summary_builder import DailySummaryBuilder, SummaryParams


@dataclass
class DailySummaryParams:
    since: datetime
    until: datetime
    min_relevance: int
    output_path: Path


class DailySummaryAgent(BaseAgent):
    def __init__(self, repository: NewsRepository) -> None:
        super().__init__(name="daily_summary")
        self.repository = repository

    async def run(self, params: DailySummaryParams) -> dict:
        records, total, ignored = self.repository.get_analyses_since(params.since, params.min_relevance)
        summary_params = SummaryParams(
            since=params.since,
            until=params.until,
            min_relevance=params.min_relevance,
            ignored_count=ignored,
        )
        builder = DailySummaryBuilder(records, summary_params)
        sections = builder.build()
        markdown = self._render_markdown(params, sections)
        params.output_path.parent.mkdir(parents=True, exist_ok=True)
        params.output_path.write_text(markdown, encoding="utf-8")
        return {
            "output": params.output_path,
            "records_used": sections.stats["records_used"],
            "total_considered": total,
        }

    def _render_markdown(self, params: DailySummaryParams, sections) -> str:
        lines = []
        lines.append(f"# Daily Investment News Summary - {params.until.isoformat()}")
        lines.append("")

        lines.append("## Executive Summary")
        if sections.executive_summary:
            lines.extend(sections.executive_summary)
        else:
            lines.append("No high-relevance news available for this window.")
        lines.append("")

        lines.append("## Top Themes")
        lines.extend(sections.top_themes or ["- None"])
        lines.append("")

        lines.append("## Watchlist Highlights")
        lines.extend(sections.watchlist or ["- None"])
        lines.append("")

        lines.append("## Risks / Negative Signals")
        lines.extend(sections.risks or ["- None"])
        lines.append("")

        lines.append("## Notable News")
        lines.extend(sections.notable_news or ["- None"])
        lines.append("")

        lines.append("## Run Statistics")
        lines.append(
            f"- Analyses used: {sections.stats['records_used']} (ignored {sections.stats['ignored']})"
        )
        lines.append(
            f"- Time window: last {sections.stats['window_hours']} hours ending {params.until.isoformat()}"
        )
        lines.append(f"- Minimum relevance: {sections.stats['min_relevance']}")
        return "\n".join(lines)
