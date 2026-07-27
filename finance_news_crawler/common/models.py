from __future__ import annotations

from typing import Any, Dict


NEWS_FIELDS = (
    "id",
    "title",
    "content",
    "publish_time",
    "source",
    "data_source",
    "data_frequency",
)


def make_news_record(
    *,
    news_id: str,
    title: str,
    content: str,
    publish_time: str,
    source: str,
    data_source: str,
    data_frequency: str,
) -> Dict[str, str]:
    return {
        "id": str(news_id or ""),
        "title": str(title or ""),
        "content": str(content or ""),
        "publish_time": str(publish_time or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
        "data_frequency": str(data_frequency or ""),
    }


def normalize_record(record: Dict[str, Any]) -> Dict[str, str]:
    return {field: str(record.get(field) or "") for field in NEWS_FIELDS}
