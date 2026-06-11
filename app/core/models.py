from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
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
    fingerprint: str | None = None
    seen_before: bool = False
    reanalyze: bool = False


@dataclass(slots=True)
class FilteredNews:
    item: NewsItem
    symbols: List[str]
    themes: List[str]
    fingerprint: str | None = None
    reanalyze: bool = False


@dataclass(slots=True)
class NewsAnalysis:
    news_url: str
    symbol: str
    relevance: int
    impact: str          # positive / negative / neutral
    time_horizon: str    # short / medium / long
    confidence: float
    reason: str
    target_type: str = "symbol"


@dataclass(slots=True)
class NewsInsights:
    item: NewsItem
    analyses: List[NewsAnalysis]


@dataclass(slots=True)
class AnalysisRecord:
    news_title: str
    news_url: str
    source: str
    published_at: datetime | None
    fingerprint: str
    analyzed_at: datetime
    target: str
    target_type: str
    relevance: int
    impact: str
    time_horizon: str
    confidence: float
    reason: str | None


@dataclass(slots=True)
class NewsRecord:
    fingerprint: str
    was_new: bool
    analyzed_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int

    def needs_analysis(self, now: datetime, reanalyze_after_hours: int) -> bool:
        if self.analyzed_at is None:
            return True
        return now - self.analyzed_at >= timedelta(hours=reanalyze_after_hours)


@dataclass(slots=True)
class CollectorStats:
    fetched_count: int = 0
    deduped_count: int = 0
    already_seen_count: int = 0
    new_items_count: int = 0
    reanalyze_count: int = 0
    analyze_candidate_count: int = 0
    analyzed_count: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "fetched": self.fetched_count,
            "deduped": self.deduped_count,
            "already_seen": self.already_seen_count,
            "new_items": self.new_items_count,
            "reanalyze_items": self.reanalyze_count,
            "analyze_candidates": self.analyze_candidate_count,
            "analyzed": self.analyzed_count,
        }


@dataclass(slots=True)
class CollectorResult:
    filtered_news: List[FilteredNews]
    stats: CollectorStats


@dataclass(slots=True)
class ReportResult:
    paths: Dict[str, Path]
    payload: Dict
