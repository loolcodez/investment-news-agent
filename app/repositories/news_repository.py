from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from app.core.models import (
    AnalysisRecord,
    CollectorStats,
    NewsAnalysis,
    NewsItem,
    NewsRecord,
)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class NewsRepository(ABC):
    @abstractmethod
    def upsert_news_item(self, item: NewsItem, fingerprint: str, seen_time: datetime) -> NewsRecord:
        ...

    @abstractmethod
    def save_analyses(
        self,
        fingerprint: str,
        analyses: List[NewsAnalysis],
        analyzed_at: datetime,
        run_id: Optional[int],
    ) -> None:
        ...

    @abstractmethod
    def mark_analyzed(self, fingerprint: str, analyzed_at: datetime) -> None:
        ...

    @abstractmethod
    def start_run(self, started_at: datetime) -> int:
        ...

    @abstractmethod
    def finish_run(self, run_id: int, stats: CollectorStats, finished_at: datetime) -> None:
        ...

    @abstractmethod
    def get_analyses_since(self, since: datetime, min_relevance: int) -> Tuple[List[AnalysisRecord], int, int]:
        ...

    @abstractmethod
    def apply_retention(self, retention) -> Dict[str, int]:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class InMemoryNewsRepository(NewsRepository):
    def __init__(self) -> None:
        self.news: Dict[str, Dict] = {}
        self.analyses: List[Dict] = []
        self.runs: Dict[int, Dict] = {}
        self._run_seq = 0

    def upsert_news_item(self, item: NewsItem, fingerprint: str, seen_time: datetime) -> NewsRecord:
        record = self.news.get(fingerprint)
        was_new = record is None
        published = _to_iso(item.published_at)
        if was_new:
            record = {
                "fingerprint": fingerprint,
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "published_at": published,
                "first_seen_at": _to_iso(seen_time),
                "last_seen_at": _to_iso(seen_time),
                "seen_count": 1,
                "analyzed_at": None,
            }
            self.news[fingerprint] = record
        else:
            record.update(
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "published_at": published,
                    "last_seen_at": _to_iso(seen_time),
                    "seen_count": record["seen_count"] + 1,
                }
            )
        return NewsRecord(
            fingerprint=fingerprint,
            was_new=was_new,
            analyzed_at=_from_iso(record["analyzed_at"]),
            first_seen_at=datetime.fromisoformat(record["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(record["last_seen_at"]),
            seen_count=record["seen_count"],
        )

    def save_analyses(
        self,
        fingerprint: str,
        analyses: List[NewsAnalysis],
        analyzed_at: datetime,
        run_id: Optional[int],
    ) -> None:
        for analysis in analyses:
            self.analyses.append(
                {
                    "news_fingerprint": fingerprint,
                    **asdict(analysis),
                    "run_id": run_id,
                    "analyzed_at": _to_iso(analyzed_at),
                }
            )

    def mark_analyzed(self, fingerprint: str, analyzed_at: datetime) -> None:
        record = self.news.get(fingerprint)
        if record:
            record["analyzed_at"] = _to_iso(analyzed_at)
            record["last_seen_at"] = _to_iso(analyzed_at)

    def start_run(self, started_at: datetime) -> int:
        self._run_seq += 1
        self.runs[self._run_seq] = {
            "started_at": _to_iso(started_at),
            "finished_at": None,
            "stats": {},
        }
        return self._run_seq

    def finish_run(self, run_id: int, stats: CollectorStats, finished_at: datetime) -> None:
        if run_id in self.runs:
            self.runs[run_id]["finished_at"] = _to_iso(finished_at)
            self.runs[run_id]["stats"] = stats.to_dict()

    def get_analyses_since(self, since: datetime, min_relevance: int) -> Tuple[List[AnalysisRecord], int, int]:
        since_iso = _to_iso(since)
        filtered: List[AnalysisRecord] = []
        total = 0
        for record in self.analyses:
            analyzed_at = _from_iso(record.get("analyzed_at"))
            if analyzed_at and analyzed_at >= since:
                total += 1
                if record.get("relevance", 0) >= min_relevance:
                    filtered.append(
                        AnalysisRecord(
                            news_title=record.get("news_title", ""),
                            news_url=record.get("news_url", ""),
                            source=record.get("source", ""),
                            published_at=_from_iso(record.get("published_at")),
                            fingerprint=record.get("news_fingerprint", ""),
                            analyzed_at=analyzed_at,
                            target=record.get("symbol"),
                            target_type=record.get("target_type", "symbol"),
                            relevance=record.get("relevance", 0),
                            impact=record.get("impact", "neutral"),
                            time_horizon=record.get("time_horizon", "short"),
                            confidence=record.get("confidence", 0.0),
                            reason=record.get("reason"),
                        )
                    )
        ignored = total - len(filtered)
        return filtered, total, ignored

    def close(self) -> None:
        pass


class SqliteNewsRepository(NewsRepository):
    def __init__(self, db_path: Path | str) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news_items (
                    fingerprint TEXT PRIMARY KEY,
                    title TEXT,
                    url TEXT,
                    source TEXT,
                    published_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    analyzed_at TEXT
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_fingerprint TEXT NOT NULL,
                    target TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    relevance INTEGER NOT NULL,
                    impact TEXT NOT NULL,
                    time_horizon TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT,
                    analyzed_at TEXT NOT NULL,
                    run_id INTEGER,
                    FOREIGN KEY(news_fingerprint) REFERENCES news_items(fingerprint)
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    fetched_count INTEGER DEFAULT 0,
                    already_seen_count INTEGER DEFAULT 0,
                    new_count INTEGER DEFAULT 0,
                    analyzed_count INTEGER DEFAULT 0
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analyses_news ON analyses(news_fingerprint)"
            )

    def upsert_news_item(self, item: NewsItem, fingerprint: str, seen_time: datetime) -> NewsRecord:
        published = _to_iso(item.published_at)
        seen_iso = _to_iso(seen_time)
        row = self.conn.execute(
            "SELECT fingerprint, first_seen_at, last_seen_at, seen_count, analyzed_at FROM news_items WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        was_new = row is None
        if was_new:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO news_items (
                        fingerprint, title, url, source, published_at,
                        first_seen_at, last_seen_at, seen_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (fingerprint, item.title, item.url, item.source, published, seen_iso, seen_iso),
                )
            first_seen = last_seen = seen_iso
            seen_count = 1
            analyzed_at = None
        else:
            seen_count = row["seen_count"] + 1
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE news_items
                    SET title = ?, url = ?, source = ?, published_at = ?, last_seen_at = ?, seen_count = ?
                    WHERE fingerprint = ?
                    """,
                    (item.title, item.url, item.source, published, seen_iso, seen_count, fingerprint),
                )
            first_seen = row["first_seen_at"]
            last_seen = seen_iso
            analyzed_at = row["analyzed_at"]
        return NewsRecord(
            fingerprint=fingerprint,
            was_new=was_new,
            analyzed_at=_from_iso(analyzed_at),
            first_seen_at=datetime.fromisoformat(first_seen),
            last_seen_at=datetime.fromisoformat(last_seen),
            seen_count=seen_count,
        )

    def save_analyses(
        self,
        fingerprint: str,
        analyses: List[NewsAnalysis],
        analyzed_at: datetime,
        run_id: Optional[int],
    ) -> None:
        if not analyses:
            return
        analyzed_iso = _to_iso(analyzed_at)
        rows = [
            (
                fingerprint,
                analysis.symbol,
                analysis.target_type,
                analysis.relevance,
                analysis.impact,
                analysis.time_horizon,
                analysis.confidence,
                analysis.reason,
                analyzed_iso,
                run_id,
            )
            for analysis in analyses
        ]
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO analyses (
                    news_fingerprint, target, target_type, relevance,
                    impact, time_horizon, confidence, reason,
                    analyzed_at, run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def mark_analyzed(self, fingerprint: str, analyzed_at: datetime) -> None:
        analyzed_iso = _to_iso(analyzed_at)
        with self.conn:
            self.conn.execute(
                "UPDATE news_items SET analyzed_at = ?, last_seen_at = ? WHERE fingerprint = ?",
                (analyzed_iso, analyzed_iso, fingerprint),
            )

    def start_run(self, started_at: datetime) -> int:
        started_iso = _to_iso(started_at)
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO runs (started_at) VALUES (?)",
                (started_iso,),
            )
        return cursor.lastrowid

    def finish_run(self, run_id: int, stats: CollectorStats, finished_at: datetime) -> None:
        finished_iso = _to_iso(finished_at)
        with self.conn:
            self.conn.execute(
                """
                UPDATE runs
                SET finished_at = ?,
                    fetched_count = ?,
                    already_seen_count = ?,
                    new_count = ?,
                    analyzed_count = ?
                WHERE id = ?
                """,
                (
                    finished_iso,
                    stats.fetched_count,
                    stats.already_seen_count,
                    stats.new_items_count,
                    stats.analyzed_count,
                    run_id,
                ),
            )

    def get_analyses_since(self, since: datetime, min_relevance: int) -> Tuple[List[AnalysisRecord], int, int]:
        since_iso = _to_iso(since)
        rows = self.conn.execute(
            """
            SELECT a.news_fingerprint, a.target, a.target_type, a.relevance, a.impact,
                   a.time_horizon, a.confidence, a.reason, a.analyzed_at,
                   n.title, n.url, n.source, n.published_at
            FROM analyses a
            JOIN news_items n ON n.fingerprint = a.news_fingerprint
            WHERE a.analyzed_at >= ? AND a.relevance >= ?
            ORDER BY a.analyzed_at ASC
            """,
            (since_iso, min_relevance),
        ).fetchall()

        total = self.conn.execute(
            "SELECT COUNT(*) FROM analyses WHERE analyzed_at >= ?",
            (since_iso,),
        ).fetchone()[0]

        records: List[AnalysisRecord] = []
        for row in rows:
            records.append(
                AnalysisRecord(
                    news_title=row["title"] or "",
                    news_url=row["url"] or "",
                    source=row["source"] or "",
                    published_at=_from_iso(row["published_at"]),
                    fingerprint=row["news_fingerprint"],
                    analyzed_at=_from_iso(row["analyzed_at"]),
                    target=row["target"],
                    target_type=row["target_type"],
                    relevance=row["relevance"],
                    impact=row["impact"],
                    time_horizon=row["time_horizon"],
                    confidence=row["confidence"],
                    reason=row["reason"],
                )
            )

        ignored = total - len(records)
        return records, total, ignored

    def apply_retention(self, retention) -> Dict[str, int]:
        now = datetime.now(timezone.utc)
        raw_cutoff = _to_iso(now - timedelta(days=retention.raw_days))
        low_cutoff = _to_iso(now - timedelta(days=retention.low_relevance_days))
        high_cutoff = _to_iso(now - timedelta(days=retention.high_relevance_days))
        run_cutoff = _to_iso(now - timedelta(days=retention.run_history_days))

        removed_high = 0
        removed_low = 0
        removed_runs = 0

        with self.conn:
            # Delete low-impact analyzed items past low retention (relevance below threshold)
            removed_low = self.conn.execute(
                """
                DELETE FROM news_items
                WHERE analyzed_at IS NOT NULL
                  AND analyzed_at < ?
                  AND fingerprint NOT IN (
                    SELECT news_fingerprint FROM analyses WHERE relevance >= ?
                  )
                """,
                (low_cutoff, retention.high_relevance_threshold),
            ).rowcount

            # Delete raw/unanalysed items older than raw_days
            removed_raw = self.conn.execute(
                "DELETE FROM news_items WHERE analyzed_at IS NULL AND last_seen_at < ?",
                (raw_cutoff,),
            ).rowcount

            # Optionally delete high-impact items beyond high retention
            removed_high = self.conn.execute(
                """
                DELETE FROM news_items
                WHERE analyzed_at IS NOT NULL
                  AND analyzed_at < ?
                  AND fingerprint IN (
                    SELECT news_fingerprint FROM analyses WHERE relevance >= ?
                  )
                """,
                (high_cutoff, retention.high_relevance_threshold),
            ).rowcount

            # Delete orphan analyses (news removed)
            self.conn.execute(
                "DELETE FROM analyses WHERE news_fingerprint NOT IN (SELECT fingerprint FROM news_items)"
            )

            removed_runs = self.conn.execute(
                "DELETE FROM runs WHERE finished_at IS NOT NULL AND finished_at < ?",
                (run_cutoff,),
            ).rowcount

        return {
            "removed_raw": removed_raw,
            "removed_low": removed_low,
            "removed_high": removed_high,
            "removed_runs": removed_runs,
        }

    def close(self) -> None:
        self.conn.close()
