from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from common.models import make_news_record
from common.utils import DEFAULT_HEADERS, clean_text
from config import STCN_KX_URL, STCN_PAGE_LIMIT


class StcnClient:
    base_url = "https://www.stcn.com"

    def __init__(self, *, timeout: int, page_limit: int = STCN_PAGE_LIMIT) -> None:
        self.timeout = timeout
        self.page_limit = page_limit
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.stcn.com/article/list/kx.html",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def fetch_by_time_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        records: List[Dict[str, str]] = []
        seen_ids = set()
        page_time = ""
        last_time = ""

        for page in range(1, self.page_limit + 1):
            print(f"Fetching STCN People Finance page {page}: {STCN_KX_URL}")
            payload = self._fetch_page(page_time=page_time, last_time=last_time)
            items = payload.get("data", [])
            if not isinstance(items, list) or not items:
                break

            page_times = []
            for item in items:
                publish_time = self._parse_time(item.get("time") or item.get("show_time"))
                if not publish_time:
                    continue
                page_times.append(publish_time)

                if publish_time < start_date:
                    continue
                if publish_time > end_date:
                    continue

                record = self._normalize_item(item, publish_time)
                if not record or record["id"] in seen_ids:
                    continue
                seen_ids.add(record["id"])
                records.append(record)

            if not page_times:
                break

            page_newest = max(page_times)
            page_oldest = min(page_times)
            print(
                "STCN People Finance page window: "
                f"{page_newest:%Y-%m-%d %H:%M:%S} -> {page_oldest:%Y-%m-%d %H:%M:%S}"
            )

            if page_oldest < start_date:
                break

            next_page_time = str(payload.get("page_time") or "")
            next_last_time = str(payload.get("last_time") or "")
            if not next_page_time and not next_last_time:
                break
            if next_page_time == page_time and next_last_time == last_time:
                break
            page_time = next_page_time
            last_time = next_last_time

        return records

    def _fetch_page(self, *, page_time: str, last_time: str) -> Dict[str, Any]:
        params = {}
        if page_time:
            params["page_time"] = page_time
        if last_time:
            params["last_time"] = last_time

        response = self.session.get(STCN_KX_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("state") != 1:
            raise RuntimeError(f"STCN API returned {payload.get('state')}: {payload.get('msg')}")
        return payload

    def _normalize_item(self, item: Dict[str, Any], publish_time: datetime) -> Optional[Dict[str, str]]:
        title = self._clean_title(str(item.get("title") or ""))
        content = self._clean_content(str(item.get("content") or ""))
        if not content and title:
            content = title
        if not content:
            return None
        if not title:
            title = content[:80]

        news_id = str(item.get("id") or "")
        if not news_id:
            news_id = f"stcn_{publish_time.strftime('%Y%m%d%H%M%S')}"
        elif not news_id.startswith("stcn_"):
            news_id = f"stcn_{news_id}"

        return make_news_record(
            news_id=news_id,
            title=title,
            content=content,
            publish_time=publish_time.strftime("%Y-%m-%d %H:%M:%S"),
            source="证券时报-人民财讯",
            data_source="证券时报人民财讯网页接口",
            data_frequency="7x24实时",
        )

    @classmethod
    def _clean_content(cls, content: str) -> str:
        content = cls._clean_base_text(content)
        content = cls._strip_leading_bracket_title(content)
        content = cls._strip_stcn_dateline(content)
        return content

    @classmethod
    def _clean_title(cls, title: str) -> str:
        title = cls._clean_base_text(title)
        return title.strip("【】[]")

    @staticmethod
    def _clean_base_text(content: str) -> str:
        content = re.sub(r"<br\s*/?>", " ", content, flags=re.IGNORECASE)
        content = re.sub(r"<.*?>", " ", content)
        return clean_text(content)

    @staticmethod
    def _strip_leading_bracket_title(content: str) -> str:
        return re.sub(r"^【[^】]{2,120}】\s*", "", content).strip()

    @staticmethod
    def _strip_stcn_dateline(content: str) -> str:
        return re.sub(
            r"^人民财讯\s*\d{1,2}月\d{1,2}日电[，,：:\s]*",
            "",
            content,
        ).strip()

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None

        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        return datetime.fromtimestamp(timestamp)
