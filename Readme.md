## Quick Start

### 1. Install dependencies
```bash
make setup
```

### 2. Configure environment
- Copy and edit `config.yaml` to adjust the watchlist, themes, RSS feeds, and limits.
- Export your OpenAI API key (required for the analysis stage):
  ```bash
  export OPENAI_API_KEY="sk-your-key"
  ```

### 3. Run the v0.1 pipeline (CLI)
```bash
make news-agent
```
This command loads the configuration, fetches RSS feeds, deduplicates and filters news, calls OpenAI once per news item, and writes both Markdown and JSON reports to `reports/latest.*` (with optional timestamped archives).

### 4. (Optional) Run the FastAPI UI
```bash
make run
```
The server starts on **port 8000** and can be used for future UI work (v0.2+). You can change the port in the `makefile`.

## Available Make Commands

### `make run`
Run the FastAPI application. Also installs dependencies when needed.

### `make setup`
Install dependencies defined in the `Pipfile` into the virtual environment.  
Use this after adding new dependencies to `Pipfile`.

### `make news-agent`
Execute the investment news pipeline once. Requires `OPENAI_API_KEY` and a valid `config.yaml`.

### `make env`
Enter the pipenv shell for interactive work.  
Only needed if you want to run commands interactively in the virtual environment.

### `make clean`
Remove cache files and delete the virtual environment to free up space.

### `make clean-all`
Complete clean including removal of `Pipfile.lock`.

**Note:** Virtual environment is created at `~/.local/share/virtualenvs`

The location varies by operating system:
- **Linux/macOS:** `~/.local/share/virtualenvs/`
- **Windows:** `%USERPROFILE%\.virtualenvs\`

To create the virtual environment inside the project folder instead (as `.venv`), set:
```bash
export PIPENV_VENV_IN_PROJECT=1
```

## Configuration Overview

`config.yaml` controls the pipeline:

| Key | Description |
| --- | --- |
| `watchlist` | List of ticker symbols to monitor. |
| `themes` | Narrative themes/keywords to track (e.g., "Interest rates"). |
| `rss_feeds` | Objects with `name`, `url`, and `enabled` flags for each feed. |
| `limits.max_items_per_run` | Hard cap on analyzed news items per execution. |
| `limits.min_keyword_hits` | Minimum keyword matches (watchlist/theme) required before OpenAI analysis; fallback items still allowed via `fallback_keep`. |
| `limits.fallback_keep` | Number of newest items kept even if no keyword match, to catch surprises. |
| `limits.request_timeout_seconds` | HTTP timeout for RSS fetching. |
| `reporting.archive` | Whether to keep timestamped report copies alongside `reports/latest.*`. |
| `reporting.min_highlight_relevance` | Minimum relevance (0-10) required for an item to be listed under Highlights. |
| `reporting.max_highlights` | Maximum number of highlight entries shown per run. |
| `storage.sqlite_path` | Path to the SQLite database file used for persistence (default `data/news_agent.db`). |
| `storage.reanalyze_after_hours` | Minimum hours before previously analyzed news becomes eligible for re-analysis. |
| `retention.raw_days` | Days to retain news items that have never been analyzed (dedupe cache). |
| `retention.low_relevance_days` | Days to retain analyzed items whose relevance never exceeded the high threshold. |
| `retention.high_relevance_days` | Days to retain high-impact analyses (those meeting the threshold). |
| `retention.high_relevance_threshold` | Relevance score (0-10) that qualifies an analysis as “high impact”. |
| `retention.run_history_days` | Days to retain run statistics in the `runs` table. |

OpenAI runtime settings (`model`, `temperature`, etc.) can be overridden via environment variables `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_MAX_RETRIES`, and `OPENAI_TIMEOUT`.

## Outputs & Runtime Data

- `reports/latest.md`: Human-readable Markdown summary with highlights, per-story analyses, counters (fetched / already seen / new / analyzed, plus reanalysis notes when applicable), and embedded JSON payload.
- `reports/latest.json`: Machine-readable payload mirroring the Markdown content.
- Timestamped archives (e.g., `reports/20260609-120000.md/json`) when `reporting.archive` is enabled.
- `data/news_agent.db`: SQLite database storing `news_items`, `analyses`, and `runs`, enabling incremental processing without loading large JSON blobs into memory.
