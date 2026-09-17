from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from common.logger import get_logger
from common.models import make_news_record
from common.utils import DEFAULT_HEADERS, clean_text
from config import CLS_PAGE_LIMIT, CLS_PAGE_SIZE, CLS_TELEGRAPH_URL

logger = get_logger(__name__)


class ClsClient:
    app_name = "CailianpressWeb"
    sv_version = "8.4.6"

    def __init__(self, *, timeout: int, page_limit: int = CLS_PAGE_LIMIT, page_size: int = CLS_PAGE_SIZE) -> None:
        self.timeout = timeout
        self.page_limit = page_limit
        self.page_size = page_size
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.cls.cn/telegraph",
            }
        )

    def fetch_by_time_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        records: List[Dict[str, str]] = []
        seen_ids = set()
        last_time = int(end_date.timestamp())

        for page in range(1, self.page_limit + 1):
            logger.info(f"Fetching CLS telegraph page {page}: {CLS_TELEGRAPH_URL}")
            payload = self._fetch_page(last_time)
            items = payload.get("data", {}).get("roll_data", [])
            if not isinstance(items, list) or not items:
                break

            page_times = []
            for item in items:
                publish_time = self._parse_timestamp(item.get("ctime"))
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
            logger.info(
                "CLS telegraph page window: "
                f"{page_newest:%Y-%m-%d %H:%M:%S} -> {page_oldest:%Y-%m-%d %H:%M:%S}"
            )

            if page_oldest < start_date:
                break

            next_last_time = int(page_oldest.timestamp())
            if next_last_time >= last_time:
                break
            last_time = next_last_time

        return records

    def _fetch_page(self, last_time: int) -> Dict[str, Any]:
        params = {
            "app": self.app_name,
            "category": "",
            "lastTime": str(last_time),
            "last_time": str(last_time),
            "os": "web",
            "refresh_type": "1",
            "rn": str(self.page_size),
            "sv": self.sv_version,
        }
        params["sign"] = self._calc_sign(params)

        response = self.session.get(CLS_TELEGRAPH_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("errno") != 0:
            raise RuntimeError(f"CLS API returned {payload.get('errno')}: {payload.get('msg')}")
        return payload

    @classmethod
    def _calc_sign(cls, params: Dict[str, str]) -> str:
        query_string = "&".join(f"{key}={params[key]}" for key in sorted(params.keys()))
        sha1_hash = hashlib.sha1(query_string.encode("utf-8")).hexdigest()
        return hashlib.md5(sha1_hash.encode("utf-8")).hexdigest()

    def _normalize_item(self, item: Dict[str, Any], publish_time: datetime) -> Optional[Dict[str, str]]:
        raw_content = str(item.get("content") or "")
        raw_title = str(item.get("title") or "")
        content = self._clean_content(raw_content)
        title = self._clean_title(raw_title)

        if not content and title:
            content = title
        if not content:
            return None

        if not title:
            title = content[:80]

        news_id = str(item.get("id") or item.get("news_id") or "")
        if not news_id:
            news_id = f"cls_{publish_time.strftime('%Y%m%d%H%M%S')}"
        elif not news_id.startswith("cls_"):
            news_id = f"cls_{news_id}"

        return make_news_record(
            news_id=news_id,
            title=title,
            content=content,
            publish_time=publish_time.strftime("%Y-%m-%d %H:%M:%S"),
            source="财联社",
            data_source="财联社电报网页接口",
            data_frequency="7x24实时",
        )

    @classmethod
    def _clean_content(cls, content: str) -> str:
        content = cls._clean_base_text(content)
        content = cls._strip_leading_bracket_title(content)
        content = cls._strip_cls_dateline(content)
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
    def _strip_cls_dateline(content: str) -> str:
        return re.sub(
            r"^财联社\s*\d{1,2}月\d{1,2}日电[，,：:\s]*",
            "",
            content,
        ).strip()

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp)
