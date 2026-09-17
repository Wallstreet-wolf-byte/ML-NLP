from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from common.logger import get_logger
from common.models import make_news_record
from common.utils import DEFAULT_HEADERS, clean_text
from config import WALLSTREETCN_LIVE_URL, WALLSTREETCN_PAGE_LIMIT, WALLSTREETCN_PAGE_SIZE

logger = get_logger(__name__)


class WallStreetCnClient:
    def __init__(
        self,
        *,
        timeout: int,
        page_limit: int = WALLSTREETCN_PAGE_LIMIT,
        page_size: int = WALLSTREETCN_PAGE_SIZE,
    ) -> None:
        self.timeout = timeout
        self.page_limit = page_limit
        self.page_size = page_size
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://wallstreetcn.com/live/global",
            }
        )

    def fetch_by_time_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        records: List[Dict[str, str]] = []
        seen_ids = set()
        cursor: Optional[str] = None

        for page in range(1, self.page_limit + 1):
            logger.info(f"Fetching WallStreetCN live page {page}: {WALLSTREETCN_LIVE_URL}")
            payload = self._fetch_page(cursor=cursor, first_page=(page == 1))
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            items = data.get("items") if isinstance(data, dict) else []
            if not isinstance(items, list) or not items:
                break

            earliest_on_page: Optional[datetime] = None
            for item in items:
                if not isinstance(item, dict):
                    continue

                publish_time = self._parse_display_time(item.get("display_time"))
                if not publish_time:
                    continue
                earliest_on_page = publish_time

                if publish_time < start_date:
                    break
                if publish_time > end_date:
                    continue

                record = self._normalize_item(item, publish_time)
                if not record or record["id"] in seen_ids:
                    continue
                seen_ids.add(record["id"])
                records.append(record)

            if earliest_on_page and earliest_on_page < start_date:
                break

            cursor_value = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor_value:
                break
            cursor = str(cursor_value)

        return records

    def _fetch_page(self, *, cursor: Optional[str], first_page: bool) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "channel": "global-channel",
            "client": "pc",
            "limit": self.page_size,
            "accept": "live,vip-live",
        }
        if first_page:
            params["first_page"] = "true"
        if cursor:
            params["cursor"] = cursor

        response = self.session.get(WALLSTREETCN_LIVE_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 20000:
            raise RuntimeError(f"WallStreetCN API returned {payload.get('code')}: {payload.get('message')}")
        return payload

    def _normalize_item(self, item: Dict[str, Any], publish_time: datetime) -> Optional[Dict[str, str]]:
        raw_content = str(item.get("content_text") or "")
        content = self._clean_content(raw_content)
        if not content:
            return None
        if item.get("is_paid") and not raw_content.strip():
            return None

        title, content = self._split_title_content(str(item.get("title") or ""), content)
        if not content:
            return None
        title = title or content[:80]

        news_id = str(item.get("id") or "")
        if not news_id:
            news_id = publish_time.strftime("%Y%m%d%H%M%S")

        return make_news_record(
            news_id=f"wallstreetcn_{news_id}",
            title=title,
            content=content,
            publish_time=publish_time.strftime("%Y-%m-%d %H:%M:%S"),
            source="华尔街见闻",
            data_source="华尔街见闻网页爬虫",
            data_frequency="7x24实时",
        )

    @staticmethod
    def _clean_content(content: str) -> str:
        content = re.sub(r"<br\s*/?>", " ", content, flags=re.IGNORECASE)
        content = re.sub(r"<.*?>", " ", content)
        return clean_text(content)

    @classmethod
    def _split_title_content(cls, raw_title: str, raw_content: str) -> Tuple[str, str]:
        title = clean_text(raw_title)
        content = clean_text(raw_content)

        bracket_title, bracket_body = cls._split_bracket_title(content)
        if bracket_title and bracket_body:
            return bracket_title, bracket_body

        bracket_title, _ = cls._split_bracket_title(title)
        if bracket_title:
            title = bracket_title
        else:
            title = cls._strip_title_brackets(title)

        if title and content.startswith(raw_title.strip()):
            content = cls._strip_leading_separator(content[len(raw_title.strip()) :])
        elif title and content.startswith(title):
            content = cls._strip_leading_separator(content[len(title) :])

        return title, content

    @classmethod
    def _split_bracket_title(cls, content: str) -> Tuple[str, str]:
        match = re.match(r"^【(?P<title>[^】]{2,120})】(?P<body>.*)$", content)
        if not match:
            return "", content

        title = cls._strip_title_brackets(match.group("title"))
        body = cls._strip_leading_separator(match.group("body"))
        return title, body

    @staticmethod
    def _strip_title_brackets(value: str) -> str:
        return clean_text(value).strip("【】[]")

    @staticmethod
    def _strip_leading_separator(value: str) -> str:
        return clean_text(value).lstrip(" ：:，,。.-—").strip()

    @staticmethod
    def _parse_display_time(value: Any) -> Optional[datetime]:
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp)
