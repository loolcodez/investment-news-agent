from __future__ import annotations

import json
import logging
from typing import Iterable, List, Sequence

from openai import AsyncOpenAI
from openai import OpenAIError

from app.core.config import OpenAISettings
from app.core.models import FilteredNews, NewsAnalysis, NewsInsights

log = logging.getLogger(__name__)


class OpenAIAnalysisService:
    def __init__(self, settings: OpenAISettings, client: AsyncOpenAI | None = None):
        self.settings = settings
        self.client = client or AsyncOpenAI()
        self.response_schema = {
            "name": "news_analysis_batch",
            "schema": {
                "type": "object",
                "properties": {
                    "analyses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "relevance": {"type": "integer", "minimum": 0, "maximum": 10},
                                "impact": {
                                    "type": "string",
                                    "enum": ["positive", "negative", "neutral"],
                                },
                                "time_horizon": {
                                    "type": "string",
                                    "enum": ["short", "medium", "long"],
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "reason": {"type": "string"},
                            },
                            "required": [
                                "symbol",
                                "relevance",
                                "impact",
                                "time_horizon",
                                "confidence",
                                "reason",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["analyses"],
                "additionalProperties": False,
            },
        }

    async def analyze_batch(
        self,
        filtered_items: Sequence[FilteredNews],
        default_symbols: Iterable[str],
        default_themes: Iterable[str],
    ) -> List[NewsInsights]:
        insights: List[NewsInsights] = []
        for filtered in filtered_items:
            targets_symbols = filtered.symbols or list(default_symbols)
            targets_themes = filtered.themes or list(default_themes)
            insight = await self._analyze_single(filtered, targets_symbols, targets_themes)
            insights.append(insight)
        return insights

    async def _analyze_single(
        self,
        filtered: FilteredNews,
        symbols: Sequence[str],
        themes: Sequence[str],
    ) -> NewsInsights:
        instructions = self._build_prompt(filtered, symbols, themes)
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await self.client.responses.create(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    response_format={"type": "json_schema", "json_schema": self.response_schema},
                    input=[
                        {
                            "role": "system",
                            "content": "You are an investment research assistant. Always reply with strict JSON.",
                        },
                        {"role": "user", "content": instructions},
                    ],
                )
                data = self._extract_json(response)
                analyses = [
                    NewsAnalysis(
                        news_url=filtered.item.url,
                        symbol=entry["symbol"],
                        relevance=int(entry["relevance"]),
                        impact=entry["impact"],
                        time_horizon=entry["time_horizon"],
                        confidence=float(entry["confidence"]),
                        reason=entry["reason"],
                    )
                    for entry in data.get("analyses", [])
                    if entry.get("symbol") in {*symbols, *themes}
                ]
                return NewsInsights(item=filtered.item, analyses=analyses)
            except (OpenAIError, json.JSONDecodeError, KeyError) as exc:
                log.warning(
                    "OpenAI request failed (attempt %s/%s): %s",
                    attempt + 1,
                    self.settings.max_retries + 1,
                    exc,
                )
                if attempt >= self.settings.max_retries:
                    raise
        raise RuntimeError("Unable to obtain OpenAI analysis")

    def _build_prompt(
        self,
        filtered: FilteredNews,
        symbols: Sequence[str],
        themes: Sequence[str],
    ) -> str:
        target_lines = [f"- Stock: {symbol}" for symbol in symbols]
        target_lines += [f"- Theme: {theme}" for theme in themes]
        targets_text = "\n".join(target_lines) if target_lines else "- (none provided)"

        summary = filtered.item.summary or "(No summary provided)"
        published = (
            filtered.item.published_at.isoformat()
            if filtered.item.published_at
            else "Unknown"
        )
        return (
            "Analyze the following news article and assess its impact on the listed targets.\n"
            "Output JSON with key 'analyses' containing an array of objects with fields: "
            "symbol, relevance (0-10), impact (positive/negative/neutral), time_horizon (short/medium/long), "
            "confidence (0-1), reason (one sentence). Only include the provided targets. If a target is irrelevant, "
            "set relevance to 0 and explain briefly.\n\n"
            f"Title: {filtered.item.title}\n"
            f"Source: {filtered.item.source}\n"
            f"Published: {published}\n"
            f"URL: {filtered.item.url}\n"
            f"Summary: {summary}\n\n"
            f"Targets:\n{targets_text}"
        )

    @staticmethod
    def _extract_json(response) -> dict:
        for output in getattr(response, "output", []) or []:
            for content in getattr(output, "content", []) or []:
                content_type = getattr(content, "type", None)
                text = getattr(content, "text", None)
                if content_type == "output_text" and text:
                    return json.loads(text)
        output_text = getattr(response, "output_text", None)
        if output_text:
            text = output_text[0] if isinstance(output_text, list) else output_text
            return json.loads(text)
        raise json.JSONDecodeError("No JSON content", doc="", pos=0)
