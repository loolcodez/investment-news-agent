# Investment News Agent – Implementation Plan (v0.1)

## Summary
- Deliver a CLI-driven pipeline that ingests RSS feeds, normalizes and deduplicates items, filters cheaply for relevance, batches OpenAI analysis **once per news item**, and emits a Markdown report plus strict JSON payloads.
- Keep all state in memory and filesystem outputs to stay lightweight, but structure the code with services/agents so later PostgreSQL and FastAPI layers can plug in without rewrites.
- Provide clear testing and acceptance criteria so v0.1 can ship independently while setting expectations for v0.2.

## Pipeline & Trigger
1. **Entrypoint**: Add `app/main_cli.py` (or similar) invoked via `python -m app.main_cli` and `make agent`. Responsibilities:
   - Load configuration.
   - Instantiate services (RSS, dedup, relevance filter, OpenAI, report writer).
   - Execute collector → analyzer → report writer.
   - Exit non-zero on failures and write structured logs to `app.log`.
2. **Execution Flow**:
   - RSS fetch (async) → normalization → deduplication → cheap relevance filter → OpenAI batch analysis (per news item) → aggregation → Markdown + JSON outputs.
3. **FastAPI**: Existing server in `app/main.py` remains untouched for v0.1.

## Configuration & Data Models
- **`config.yaml`** gains:
  - `rss_feeds`: list of `{ name, url, enabled }` entries.
  - `max_items_per_run`: hard cap on news processed each run (defaults to e.g., 40).
  - Optional `min_keyword_hits` / `always_keep` counts for the relevance filter.
- **Loader (`app/core/config.py`)**:
  - Use `pydantic` to validate watchlist symbols, themes, feed URLs, and numeric limits.
  - Support `.env` overrides for OpenAI settings (model, temperature, timeout).
- **Models (`app/core/models.py`)**:
  - `Config`, `FeedConfig`, `WatchTarget`, and `Theme` dataclasses/pydantic models.
  - `NewsItem`: `id`, `title`, `url`, `canonical_url`, `source`, `published_at`, `summary`, `raw` (dict).
  - `NewsAnalysis`: `news_url`, `symbol`, `relevance:int`, `impact:str`, `time_horizon:str`, `confidence:float`, `reason`.
  - `NewsInsights`: container bundling one `NewsItem` with `List[NewsAnalysis]` for batching.

## Services & Agents
- **RSS Service (`app/services/rss_service.py`)**
  - Use `httpx.AsyncClient` + `feedparser` to pull feeds concurrently.
  - Normalize timestamps to UTC `datetime`, fall back to published/updated order.
  - Tag each item with `source` derived from feed config.
- **Dedup Service (`app/services/dedup_service.py`)**
  - Canonicalize URLs (strip params, lowercase host) for hash-based dedupe.
  - Apply title similarity via `difflib.SequenceMatcher` threshold (~0.88) and keep the newest item when conflict.
- **Cheap Relevance Filter**
  - Tokenize title + summary; keyword match against watchlist symbols (case-insensitive) and theme keywords (allow multi-word phrases).
  - Keep any items meeting `min_keyword_hits` AND always retain top `fallback_keep` items sorted by recency to catch surprises.
  - Enforce global `max_items_per_run` after filtering.
- **OpenAI Service (`app/services/openai_service.py`)**
  - For each remaining news item, call OpenAI once with a structured prompt listing watchlist symbols + themes and request JSON schema output: `{"analyses": [{symbol,...}]}`.
  - Use `response_format`/JSON mode; retry malformed responses up to N times.
  - Return `NewsInsights` with parsed analyses and log token usage.
- **Agents**
  - `news_collector`: orchestrates RSS fetch → normalization → dedup → filter; returns ordered `List[NewsItem]`.
  - `impact_analyzer`: maps each `NewsItem` to `NewsInsights` by invoking OpenAI service.
  - `report_writer`: formats Markdown/JSON outputs and archives timestamped copies when configured.
- **Repositories**
  - `memory_repository`: optional cache of collected news within run.
  - `file_repository`: handles writes to `reports/latest.md` and `reports/{timestamp}.json/md`.

## Output & Storage
- **Markdown report (`reports/latest.md`)**
  - Header with run timestamp, number of feeds, number of filtered items.
  - Per-symbol/theme highlights (top N by relevance/confidence) with bullet summaries.
  - Raw JSON appendix containing ordered `NewsInsights` array.
- **JSON artifact**
  - Write strict JSON to `reports/latest.json` (mirrors Markdown appendix) to simplify downstream integrations.
- **Archival**
  - Optional timestamped copies (config flag) for historical reference until DB arrives in v0.2.

## Testing & Validation
- **Unit Tests**
  - Config loader validation (good/bad YAML, missing keys).
  - RSS normalization with mocked feedparser payloads.
  - Dedup collision scenarios (same URL, similar title, multi-source).
  - Relevance filter edge cases (symbols embedded in words, multi-word themes, fallback behavior).
  - OpenAI service parsing using mocked JSON responses (valid / malformed / retries).
  - Report writer snapshot comparing Markdown structure.
- **Integration Tests**
  - End-to-end pipeline test against recorded RSS fixtures to ensure deterministic ordering, filtering, and output file creation respecting `max_items_per_run`.

## Acceptance Criteria
- Running `make agent` (after configuring `OPENAI_API_KEY`) fetches feeds, logs progress, writes `reports/latest.md` and `.json` with strict schema, and exits successfully.
- OpenAI is called at most once per retained news item, even if multiple symbols/themes are relevant.
- Dedup + filter reduce noise so max processed items never exceed configured cap.
- No database or FastAPI changes required; code remains modular for v0.2.

## Assumptions & Defaults
- Watchlist symbols and theme keywords are curated manually in `config.yaml`.
- Default OpenAI model: `gpt-4o-mini` (override via env `OPENAI_MODEL`).
- Network errors/retries handled gracefully with exponential backoff; failures log and skip the item after max retries.
- Running environment has Pipenv + Python 3.11+.
