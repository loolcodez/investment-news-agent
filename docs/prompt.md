Create a Python MVP for an investment news agent.

Requirements:
1. Read watchlist and themes from config.yaml.
2. Fetch news from RSS feeds.
3. Normalize news into objects with title, url, source, published_at, summary.
4. Deduplicate by URL and similar title.
5. Use OpenAI API to analyze relevance and likely impact for each watched stock/theme.
6. Return analysis as strict JSON
7. Output a Markdown report to reports/latest.md.
8. Keep the code modular and easy to extend later with PostgreSQL and a web UI.
9. Add README.md with setup and usage instructions.

Return analysis as strict JSON:
{
  "symbol": "NIO",
  "relevance": 0,
  "impact": "neutral",
  "time_horizon": "short",
  "confidence": 0.0,
  "reason": "..."
}

There is skeleton application which is use as basis for the implementation. Read it and create implementation-plan.md
for v0.1 and v0.2. Read also plan.md. It contains some ideas what we are implementing. We will start with very simple
implementation and enhance that gradually. 