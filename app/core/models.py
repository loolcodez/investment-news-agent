@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None

@dataclass
class NewsAnalysis:
    news_url: str
    symbol: str
    relevance: int
    impact: str          # positive / negative / neutral
    time_horizon: str    # short / medium / long
    confidence: float
    reason: str
