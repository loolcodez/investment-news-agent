Investment News Agent

Mission:
Help identify information that could materially affect stocks on the watchlist.

Not a trading bot.
Not a price predictor.
Not an automatic portfolio manager.

Goal:
Reduce the amount of news and research the user must manually read every day.


Ideas for the implementation:

News themes:
- Company related news
- General semiconductor news
- AI datacenters
- Humanoid robots
- Interest rates
- China EV

Pipeline:
1. Fetch news
2. Normalize
3. Remove duplicates
4. Pre-filter relevance cheaply 
5. Estimate relevance to watched stocks
6. Estimate effect: + / - / 0
7. Store in database
8. Create report
9. Show in web page and send email notification
10. Configurable how often it is run. Later maybe more detailed specified when run


PostgreSQL:
stocks
themes
news_items
news_analysis
reports

Agent analysis for every news:
stock: INTEL
relevance: 0-10
impact: positive / negative / neutral
time_horizon: short / medium / long
reason: short reasoning
confidence: 0-1

Example news:

China expands EV subsidies

NIO:
relevance: 9
impact: positive
time_horizon: medium
confidence: 0.75
reason: Supports premium-EV market in China.

Agent stores:

2026-06-07

News:
China increased EV-subsides

Effect:
NIO +

Confidence:
0.75

After some time agent checks what happened
If NIO stock prize raised agent confidence + else -
Agent learns relevance of the news

Possible solution in the beginning:

PostgreSQL + pgvector

Agent 1:
Collects the news

Agent 2:
Estimates news effect

Agent 3:
Creates report and sends notification


Result could be TOP 5 most important events

1. China reduced EV subsides
Effect NIO: +++

2. Nvidia published new AI-chip
Effect NIO: 0

3. Fed hinted coming rate decrease
Effect NIO: 0

...


Technology:
Python
PostgreSQL
pgvector later
FastAPI
yfinance or something else for stock data
RSS / NewsAPI / Yahoo Finance in the beginning
OpenAI API for analysis

Gradual implementation:

v0.1:
- config.yaml,  contains watchlist ja themes
- script fetches news
- script asks AI to analyze the news
- prints report as markdown file

v0.2:
- PostgreSQL
- web UI
- history