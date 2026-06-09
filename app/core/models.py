from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Sequence


@dataclass(slots=True)
class WatchTarget:
    symbol: str
    keywords: Sequence[str] = field(default_factory=list)

    def keyword_set(self) -> set[str]:
        return {self.symbol.lower(), *{kw.lower() for kw in self.keywords}}


@dataclass(slots=True)
class Theme:
    name: str
    keywords: Sequence[str] = field(default_factory=list)

    def keyword_set(self) -> set[str]:
        base = {self.name.lower()}
        return base | {kw.lower() for kw in self.keywords}


@dataclass(slots=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
    canonical_url: str
    raw: Dict | None = None


@dataclass(slots=True)
class FilteredNews:
    item: NewsItem
    symbols: List[str]
    themes: List[str]


@dataclass(slots=True)
class NewsAnalysis:
    news_url: str
    symbol: str
    relevance: int
    impact: str          # positive / negative / neutral
    time_horizon: str    # short / medium / long
    confidence: float
    reason: str


@dataclass(slots=True)
class NewsInsights:
    item: NewsItem
    analyses: List[NewsAnalysis]
