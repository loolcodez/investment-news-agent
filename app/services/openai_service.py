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
        self.theme_instructions = {
            "Interest rates": (
                "Only classify this theme when the article covers central bank policy, inflation data, bond yields, "
                "monetary policy decisions, or market interest-rate expectations. If the article is about retail "
                "savings products, deposit promotions, or consumer banking tips, you must set relevance to 0 and "
                "state that it is not a market-moving interest-rate signal."
            ),
        }
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
        target_symbol_set = {symbol for symbol in symbols}
        target_theme_set = {theme for theme in themes}
        target_union = target_symbol_set | target_theme_set

        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an investment research assistant. Output only valid JSON for the requested schema.",
                        },
                        {"role": "user", "content": instructions},
                    ],
                )
                data = self._extract_json(response)
                analyses = []
                for entry in data.get("analyses", []):
                    target = entry.get("symbol")
                    if target not in target_union:
                        continue
                    target_type = "symbol" if target in target_symbol_set else "theme"
                    analyses.append(
                        NewsAnalysis(
                            news_url=filtered.item.url,
                            symbol=target,
                            target_type=target_type,
                            relevance=int(entry["relevance"]),
                            impact=entry["impact"],
                            time_horizon=entry["time_horizon"],
                            confidence=float(entry["confidence"]),
                            reason=entry["reason"],
                        )
                    )
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
        for theme in themes:
            extra = self.theme_instructions.get(theme)
            if extra:
                target_lines.append(f"- Theme: {theme} ({extra})")
            else:
                target_lines.append(f"- Theme: {theme}")
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
        choices = getattr(response, "choices", [])
        if not choices:
            raise json.JSONDecodeError("No choices returned", doc="", pos=0)
        message = getattr(choices[0], "message", None)
        if message is None:
            raise json.JSONDecodeError("No message content", doc="", pos=0)
        content = getattr(message, "content", "")
        if isinstance(content, list):  # some SDKs return content arrays
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not isinstance(content, str):
            raise json.JSONDecodeError("Unsupported content type", doc="", pos=0)
        return OpenAIAnalysisService._parse_json_content(content)

    @staticmethod
    def _parse_json_content(text: str) -> dict:
        text = text.strip()
        if not text:
            raise json.JSONDecodeError("Empty response", doc="", pos=0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = text[start : end + 1]
                return json.loads(snippet)
            raise
