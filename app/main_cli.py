from __future__ import annotations

import argparse
import asyncio
import logging

from app.agents.impact_analyzer import ImpactAnalyzerAgent
from app.agents.news_collector import NewsCollectorAgent
from app.agents.report_writer import ReportWriterAgent
from app.core.config import AppConfig, load_config
from app.repositories.file_repository import ReportRepository
from app.repositories.memory_repository import InMemoryNewsRepository
from app.services.dedup_service import DeduplicationService
from app.services.openai_service import OpenAIAnalysisService
from app.services.relevance_filter import RelevanceFilterService
from app.services.rss_service import RSSService

log = logging.getLogger("investment-news-agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the investment news agent pipeline")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml",
    )
    return parser.parse_args()


async def run_pipeline(config: AppConfig):
    rss_service = RSSService(timeout_seconds=config.limits.request_timeout_seconds)
    dedup_service = DeduplicationService()
    relevance_filter = RelevanceFilterService(
        watchlist=config.watchlist,
        themes=config.themes,
        min_keyword_hits=config.limits.min_keyword_hits,
        fallback_keep=config.limits.fallback_keep,
    )
    memory_repo = InMemoryNewsRepository()
    openai_service = OpenAIAnalysisService(config.openai)
    report_repository = ReportRepository(archive=config.reporting.archive)

    collector = NewsCollectorAgent(rss_service, dedup_service, relevance_filter, memory_repo)
    analyzer = ImpactAnalyzerAgent(openai_service)
    writer = ReportWriterAgent(report_repository)

    filtered_news = await collector.run(config)

    insights = await analyzer.run((filtered_news, config))
    result_paths = await writer.run((insights, config))
    return result_paths


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = parse_args()
    config = load_config(args.config)
    log.info("Starting pipeline with %s feeds", len(config.enabled_feeds))
    try:
        results = asyncio.run(run_pipeline(config))
    except Exception:
        log.exception("Pipeline failed")
        raise SystemExit(1)

    markdown_path = results.get("markdown")
    json_path = results.get("json")
    log.info("Report written to %s and %s", markdown_path, json_path)


if __name__ == "__main__":
    main()
