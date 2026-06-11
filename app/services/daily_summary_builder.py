from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

from app.core.models import AnalysisRecord


@dataclass
class SummaryParams:
    since: datetime
    until: datetime
    min_relevance: int
    ignored_count: int


@dataclass
class SummarySections:
    executive_summary: List[str]
    top_themes: List[str]
    watchlist: List[str]
    risks: List[str]
    notable_news: List[str]
    stats: dict


class DailySummaryBuilder:
    INTEREST_RATE_NOISE = (
        "mortgage",
        "mortgages",
        "refinance",
        "refi",
        "savings",
        "certificate of deposit",
        "cd rate",
        "apy",
        "checking",
        "personal loan",
    )

    def __init__(self, records: Iterable[AnalysisRecord], params: SummaryParams):
        self.original_records = list(records)
        self.params = params
        self.records = [
            r for r in self.original_records if not self._is_interest_rate_noise(r)
        ]
        self.filtered_records = [
            r for r in self.records if r.relevance >= self.params.min_relevance
        ]

    def build(self) -> SummarySections:
        top_themes = self._build_top_themes()
        watchlist = self._build_watchlist()
        risks = self._build_risks()
        notable = self._build_notable_news()
        exec_summary = self._build_executive_summary(top_themes, watchlist, risks)
        stats = {
            "records_used": len(self.filtered_records),
            "total_records": len(self.records),
            "ignored": self.params.ignored_count,
            "window_hours": round((self.params.until - self.params.since).total_seconds() / 3600, 2),
            "min_relevance": self.params.min_relevance,
        }
        return SummarySections(exec_summary, top_themes, watchlist, risks, notable, stats)

    def _build_top_themes(self) -> List[str]:
        buckets = defaultdict(list)
        for record in self.filtered_records:
            if record.target_type != "theme":
                continue
            buckets[record.target].append(record)
        ranked = sorted(
            buckets.items(),
            key=lambda item: (-len(item[1]), -self._avg_relevance(item[1])),
        )
        lines: List[str] = []
        for theme, records in ranked[:5]:
            avg_rel = self._avg_relevance(records)
            pos = sum(1 for r in records if r.impact == "positive")
            neg = sum(1 for r in records if r.impact == "negative")
            lines.append(
                f"- {theme}: {len(records)} mentions, avg relevance {avg_rel:.1f}/10 (pos {pos} / neg {neg})"
            )
        return lines

    def _build_watchlist(self) -> List[str]:
        buckets = defaultdict(list)
        for record in self.filtered_records:
            if record.target_type != "symbol":
                continue
            buckets[record.target].append(record)
        highlights: List[str] = []
        for symbol, records in buckets.items():
            summary = self._watchlist_summary(symbol, records)
            highlights.append(summary)
        highlights.sort()
        return highlights[:8]

    def _build_risks(self) -> List[str]:
        risks = [r for r in self.filtered_records if r.impact == "negative"]
        risks.sort(key=lambda r: r.relevance, reverse=True)
        lines = [
            f"- {r.news_title} → {r.target} (R={r.relevance}/10): {r.reason or 'Negative signal'}"
            for r in risks[:5]
        ]
        return lines

    def _build_notable_news(self) -> List[str]:
        grouped: dict[str, List[AnalysisRecord]] = {}
        for record in self.filtered_records:
            grouped.setdefault(record.fingerprint, []).append(record)

        best_per_news: List[AnalysisRecord] = []
        for records in grouped.values():
            best = max(
                records,
                key=lambda r: (r.target_type == "symbol", r.relevance, r.confidence),
            )
            best_per_news.append(best)

        ranked = sorted(best_per_news, key=lambda r: r.relevance, reverse=True)
        return [
            f"- {record.news_title} → {record.target} ({record.impact}, R={record.relevance}/10)"
            for record in ranked[:10]
        ]

    def _build_executive_summary(
        self,
        top_themes: List[str],
        watchlist: List[str],
        risks: List[str],
    ) -> List[str]:
        bullets: List[str] = []
        hours = round((self.params.until - self.params.since).total_seconds() / 3600)
        bullets.append(
            f"- Processed {len(self.filtered_records)} analyses in the last {hours}h (min relevance {self.params.min_relevance})."
        )
        if top_themes:
            bullets.append(f"- Dominant theme: {top_themes[0][2:]}")
        if watchlist:
            bullets.append(f"- Watchlist highlight: {watchlist[0][2:]}")
        if risks:
            bullets.append(f"- Top risk: {risks[0][2:]}")
        if self.params.ignored_count:
            bullets.append(f"- Ignored {self.params.ignored_count} low-relevance items in this window.")
        return bullets[:5]

    @staticmethod
    def _avg_relevance(records: List[AnalysisRecord]) -> float:
        if not records:
            return 0.0
        return sum(r.relevance for r in records) / len(records)

    @staticmethod
    def _trend(records: List[AnalysisRecord]) -> str:
        positives = sum(1 for r in records if r.impact == "positive")
        negatives = sum(1 for r in records if r.impact == "negative")
        if positives > negatives:
            return "net positive"
        if negatives > positives:
            return "net negative"
        return "mixed"

    def _watchlist_summary(self, symbol: str, records: List[AnalysisRecord]) -> str:
        positives = sum(1 for r in records if r.impact == "positive")
        negatives = sum(1 for r in records if r.impact == "negative")
        if positives > negatives:
            tone = "positive"
        elif negatives > positives:
            tone = "negative"
        else:
            tone = max(records, key=lambda r: r.relevance).impact

        best = max(records, key=lambda r: (r.relevance, r.confidence))
        detail = best.reason or "Key development"
        return (
            f"- {symbol}: {tone} bias (top relevance {best.relevance}/10, {positives}↑/{negatives}↓) – {detail}"  # noqa: E501
        )

    def _is_interest_rate_noise(self, record: AnalysisRecord) -> bool:
        if record.target_type != "theme" or record.target.lower() != "interest rates":
            return False
        title = (record.news_title or "").lower()
        reason = (record.reason or "").lower()
        text = f"{title} {reason}"
        return any(keyword in text for keyword in self.INTEREST_RATE_NOISE)
