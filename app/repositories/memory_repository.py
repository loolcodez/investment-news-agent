from __future__ import annotations

from typing import Iterable, List

from app.core.models import NewsItem


class InMemoryNewsRepository:
    def __init__(self) -> None:
        self._items: List[NewsItem] = []

    def save_news(self, items: Iterable[NewsItem]) -> None:
        self._items.extend(items)

    def list_news(self) -> List[NewsItem]:
        return list(self._items)
