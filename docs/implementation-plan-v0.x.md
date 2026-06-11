# Investment News Agent – Roadmap (v0.x)

## Summary
- Extend the v0.1 pipeline with durable storage, history-aware analysis, and a simple web interface without rewriting the existing agents/services architecture.
- Introduce PostgreSQL persistence, FastAPI-powered UI + APIs, scheduling, and deployment tooling so the system can run continuously and surface historical insights.

## Key Themes & Deliverables
1. **Data Persistence & Schema**
   - Adopt PostgreSQL via SQLAlchemy ORM; define tables for `stocks`, `themes`, `news_items`, `news_analysis`, `reports`, and `pipeline_runs`.
   - Use Alembic migrations for schema evolution; seed watchlist/themes from config on first run.
   - Replace in-memory/file repositories with interfaces backed by Postgres while keeping the file-based report output for compatibility.
2. **Historical Workflow Enhancements**
   - Collector skips already-seen items via unique URL index; analyzer updates existing analyses if rerun.
   - Store OpenAI raw JSON, derived metrics, and processing timestamps for each news item.
   - Add lightweight feedback hooks (manual tagging, later automated outcome tracking) to adjust relevance scoring.
3. **Web UI & APIs**
   - Expand `app/main.py` FastAPI app with routes:
     - `/` dashboard summarizing latest run, top impacts, and per-symbol cards.
     - `/reports/{date}` to view historical Markdown rendered as HTML.
     - `/api/news`, `/api/analyses`, `/api/reports` returning paginated JSON filtered by symbol/theme/date.
   - Reuse Jinja templates under `app/templates/`; include simple charts or tables (no heavy JS yet).
4. **Scheduling & Automation**
   - Add APScheduler (or similar) job inside FastAPI startup or a separate worker process to run the pipeline at configurable intervals.
   - Log pipeline runs to `pipeline_runs` table with duration, counts, and error status for observability.
5. **Performance & Cost Controls**
   - Batch OpenAI prompts further by grouping related symbols/themes when feasible, caching prior analyses for repeated news, and short-circuiting items whose analysis already exists in DB with high confidence.
   - Introduce Redis-ready cache interface (optional) for feed content and OpenAI responses.
6. **Deployment & Ops**
   - Provide Dockerfile + docker-compose.yml (app + Postgres) for local/dev deployments.
   - Update systemd service (existing `investment-news-agent.service`) to run the scheduler/worker and ensure environment variables/secrets are loaded securely.
   - Enhance logging/metrics (structured JSON logs, health endpoints) for production readiness.

## Acceptance Criteria
- Pipeline can be triggered via CLI, scheduled job, or HTTP endpoint, all hitting the same underlying orchestration logic.
- Each news item and analysis persists to PostgreSQL with full history and can be queried via API/UI.
- FastAPI UI surfaces latest analyses and allows filtering by symbol/theme/date; APIs return JSON conforming to documented schemas.
- Docker-based setup (`docker compose up`) launches PostgreSQL, runs migrations, starts the FastAPI app, and schedules the agent.

## Testing Strategy
- Database integration tests covering migrations, repository CRUD, and dedup uniqueness constraints.
- FastAPI endpoint tests using TestClient for HTML + JSON routes (auth not required yet).
- Scheduler smoke tests verifying periodic execution and error handling.

## Assumptions
- Same OpenAI model as v0.1 unless future analysis tier is needed.
- PostgreSQL connection info supplied via environment variables; secrets managed outside repo.
- Frontend remains server-rendered for this version; richer SPA can be deferred to later releases.
