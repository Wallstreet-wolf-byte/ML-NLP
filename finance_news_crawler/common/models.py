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


def make_cninfo_record(
    *,
    record_id: str,
    stock_code: str,
    stock_name: str,
    title: str,
    announcement_type: str,
    publish_time: str,
    source: str,
    data_source: str,
    file_url: str = "",
    content: str = "",
    raw: Any = None,
) -> Dict[str, Any]:
    return {
        "id": str(record_id or ""),
        "record_type": "announcement",
        "stock_code": str(stock_code or ""),
        "stock_name": str(stock_name or ""),
        "title": str(title or ""),
        "announcement_type": str(announcement_type or ""),
        "publish_time": str(publish_time or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
        "file_url": str(file_url or ""),
        "content": str(content or ""),
        "raw": raw if raw is not None else {},
    }
