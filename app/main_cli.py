from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

from app.agents.daily_summary import DailySummaryAgent, DailySummaryParams
from app.agents.impact_analyzer import ImpactAnalyzerAgent
from app.agents.news_collector import NewsCollectorAgent
from app.agents.report_writer import ReportWriterAgent
from app.core.config import AppConfig, load_config
from app.repositories.file_repository import ReportRepository
from app.repositories.news_repository import SqliteNewsRepository
from app.services.dedup_service import DeduplicationService
from app.services.openai_service import OpenAIAnalysisService
from app.services.relevance_filter import RelevanceFilterService
from app.services.rss_service import RSSService

log = logging.getLogger("investment-news-agent")

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Investment news agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser("agent", help="Run the news collection + analysis pipeline")
    pipeline.add_argument("--config", default="config.yaml", help="Path to config.yaml")

    summary = subparsers.add_parser("daily-summary", help="Generate a daily summary from stored analyses")
    summary.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    summary.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    summary.add_argument("--min-relevance", type=int, default=7, help="Minimum relevance to include")
    summary.add_argument(
        "--output",
        default="reports/daily-summary.md",
        help="Path to write the daily summary Markdown",
    )

    return parser.parse_args()


async def run_pipeline(config: AppConfig):
    repository = SqliteNewsRepository(config.storage.sqlite_path)
    run_id = repository.start_run(datetime.now(timezone.utc))
    rss_service = RSSService(timeout_seconds=config.limits.request_timeout_seconds)
    dedup_service = DeduplicationService()
    relevance_filter = RelevanceFilterService(
        watchlist=config.watchlist,
        themes=config.themes,
        min_keyword_hits=config.limits.min_keyword_hits,
        fallback_keep=config.limits.fallback_keep,
    )
    openai_service = OpenAIAnalysisService(config.openai)
    report_repository = ReportRepository(archive=config.reporting.archive)

    collector = NewsCollectorAgent(
        rss_service,
        dedup_service,
        relevance_filter,
        repository,
    )
    analyzer = ImpactAnalyzerAgent(openai_service, repository)
    writer = ReportWriterAgent(report_repository)

    try:
        collector_result = await collector.run(config)
        insights = await analyzer.run((collector_result.filtered_news, config, run_id))
        collector_result.stats.analyzed_count = len(insights)
        report_result = await writer.run((insights, config, collector_result.stats))
        repository.finish_run(run_id, collector_result.stats, datetime.now(timezone.utc))
        retention_stats = repository.apply_retention(config.retention)
        if any(retention_stats.values()):
            log.info("Retention cleanup removed %s", retention_stats)
        return report_result.paths
    finally:
        repository.close()


async def run_daily_summary(config: AppConfig, hours: int, min_relevance: int, output: Path):
    repository = SqliteNewsRepository(config.storage.sqlite_path)
    try:
        until = datetime.now(timezone.utc)
        since = until - timedelta(hours=hours)
        agent = DailySummaryAgent(repository)
        result = await agent.run(
            DailySummaryParams(
                since=since,
                until=until,
                min_relevance=min_relevance,
                output_path=output,
            )
        )
        log.info(
            "Daily summary written to %s using %s records (total considered %s)",
            result["output"],
            result["records_used"],
            result["total_considered"],
        )
    finally:
        repository.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = parse_args()
    config = load_config(args.config)

    if args.command == "agent":
        log.info("Starting pipeline with %s feeds", len(config.enabled_feeds))
        try:
            results = asyncio.run(run_pipeline(config))
        except Exception:
            log.exception("Pipeline failed")
            raise SystemExit(1)
        markdown_path = results.get("markdown")
        json_path = results.get("json")
        log.info("Report written to %s and %s", markdown_path, json_path)
    elif args.command == "daily-summary":
        try:
            asyncio.run(
                run_daily_summary(
                    config,
                    hours=args.hours,
                    min_relevance=args.min_relevance,
                    output=Path(args.output),
                )
            )
        except Exception:
            log.exception("Daily summary generation failed")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
