Create a Python MVP for an investment news agent.

Requirements:
1. Read watchlist and themes from config.yaml.
2. Fetch news from RSS feeds.
3. Normalize news into objects with title, url, source, published_at, summary.
4. Deduplicate by URL and similar title.
5. Use OpenAI API to analyze relevance and likely impact for each watched stock/theme.
6. Output a Markdown report to reports/latest.md.
7. Keep the code modular and easy to extend later with PostgreSQL and a web UI.
8. Add README.md with setup and usage instructions.