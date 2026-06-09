from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.agents.base import BaseAgent
from app.core.config import AppConfig
from app.core.models import NewsAnalysis, NewsInsights
from app.repositories.file_repository import ReportRepository


class ReportWriterAgent(BaseAgent):
    def __init__(self, repository: ReportRepository) -> None:
        super().__init__(name="report_writer")
        self.repository = repository

    async def run(self, data: tuple[List[NewsInsights], AppConfig]):
        insights, config = data
        generated_at = datetime.now(timezone.utc)
        payload = self._build_payload(insights, config, generated_at)
        markdown = self._build_markdown(payload)
        return self.repository.write_report(markdown, payload)

    def _build_payload(
        self, insights: List[NewsInsights], config: AppConfig, generated_at: datetime
    ) -> dict:
        items = []
        for insight in insights:
            news = insight.item
            items.append(
                {
                    "news": {
                        "title": news.title,
                        "url": news.url,
                        "source": news.source,
                        "published_at": news.published_at.isoformat() if news.published_at else None,
                        "summary": news.summary,
                    },
                    "analyses": [self._analysis_to_dict(analysis) for analysis in insight.analyses],
                }
            )
        return {
            "generated_at": generated_at.isoformat(),
            "feed_count": len(config.enabled_feeds),
            "watchlist": config.watchlist,
            "themes": config.themes,
            "items": items,
        }

    @staticmethod
    def _analysis_to_dict(analysis: NewsAnalysis) -> dict:
        return {
            "symbol": analysis.symbol,
            "relevance": analysis.relevance,
            "impact": analysis.impact,
            "time_horizon": analysis.time_horizon,
            "confidence": analysis.confidence,
            "reason": analysis.reason,
            "news_url": analysis.news_url,
        }

    def _build_markdown(self, payload: dict) -> str:
        lines: List[str] = []
        generated_at = payload["generated_at"]
        items: List[dict] = payload["items"]

        lines.append(f"# Investment News Report - {generated_at}")
        lines.append("")

        lines.append("## Summary")
        lines.append(f"- Feeds processed: {payload['feed_count']}")
        lines.append(f"- Watchlist size: {len(payload['watchlist'])}")
        lines.append(f"- Themes tracked: {len(payload['themes'])}")
        lines.append(f"- Items analyzed: {len(items)}")
        lines.append("")

        lines.append("## Highlights")
        highlights = self._top_highlights(items)
        if not highlights:
            lines.append("- No news analyzed in this run.")
        else:
            for highlight in highlights:
                lines.append(highlight)
        lines.append("")

        lines.append("## Details")
        for entry in items:
            news = entry["news"]
            lines.append(f"### {news['title']}")
            lines.append(f"Source: {news['source']} | Published: {news['published_at'] or 'Unknown'}")
            if news["summary"]:
                lines.append(news["summary"].strip())
            lines.append("Analyses:")
            if not entry["analyses"]:
                lines.append("- No relevant symbols or themes identified.")
            else:
                for analysis in entry["analyses"]:
                    lines.append(
                        "- {symbol}: relevance {rel}/10, impact {impact}, horizon {horizon}, "
                        "confidence {conf:.2f}. Reason: {reason}".format(
                            symbol=analysis["symbol"],
                            rel=analysis["relevance"],
                            impact=analysis["impact"],
                            horizon=analysis["time_horizon"],
                            conf=analysis["confidence"],
                            reason=analysis["reason"],
                        )
                    )
            lines.append("")

        lines.append("## JSON")
        lines.append("```json")
        lines.append(json.dumps(payload, indent=2))
        lines.append("```")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _top_highlights(items: List[dict], limit: int = 5) -> List[str]:
        scored = []
        for entry in items:
            analyses = entry["analyses"]
            if not analyses:
                continue
            max_analysis = max(analyses, key=lambda a: a["relevance"])
            scored.append((max_analysis["relevance"], entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        highlights = []
        for _, entry in scored[:limit]:
            news = entry["news"]
            analyses = entry["analyses"]
            max_analysis = max(analyses, key=lambda a: a["relevance"])
            highlights.append(
                f"- {news['title']} → {max_analysis['symbol']} ({max_analysis['impact']}, R={max_analysis['relevance']}/10)"
            )
        return highlights
