from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from common.models import make_news_record
from common.utils import DEFAULT_HEADERS, clean_text
from config import JIN10_FLASH_LIMIT, JIN10_PAGE_LIMIT, JIN10_WEB_FLASH_API_URL, JIN10_WEB_FLASH_URL


class Jin10WebFlashClient:
    def __init__(self, *, timeout: int, limit: int = JIN10_FLASH_LIMIT, page_limit: int = JIN10_PAGE_LIMIT) -> None:
        self.timeout = timeout
        self.limit = limit
        self.page_limit = page_limit
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "Referer": "https://www.jin10.com/",
                "Origin": "https://www.jin10.com",
                "x-app-id": "bVBF4FyRTn5NJF5n",
                "x-version": "1.0.0",
                "handleError": "1",
            }
        )

    def fetch_by_time_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        try:
            return self._fetch_from_web_api(start_date, end_date)
        except Exception as exc:
            print(f"Jin10 web API failed: {exc}; trying HTML fallback.")
            return self._fetch_from_html(start_date, end_date)

    def _fetch_from_web_api(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        records: List[Dict[str, str]] = []
        seen_ids = set()
        max_time = ""
        newest_seen: Optional[datetime] = None
        oldest_seen: Optional[datetime] = None

        for page in range(1, self.page_limit + 1):
            params = {"channel": "-8200"}
            if max_time:
                params["max_time"] = max_time

            print(f"Fetching Jin10 market flash page {page}: {JIN10_WEB_FLASH_API_URL}")
            response = self.session.get(JIN10_WEB_FLASH_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()

            if payload.get("status") != 200:
                print(f"Jin10 market flash API returned {payload.get('status')}: {payload.get('message')}")
                return records

            items = payload.get("data")
            if not isinstance(items, list) or not items:
                break

            page_times = [self._parse_publish_time(str(item.get("time") or "")) for item in items]
            valid_page_times = [value for value in page_times if value]
            if valid_page_times:
                page_newest = max(valid_page_times)
                page_oldest = min(valid_page_times)
                newest_seen = page_newest if newest_seen is None else max(newest_seen, page_newest)
                oldest_seen = page_oldest if oldest_seen is None else min(oldest_seen, page_oldest)
                print(
                    "Jin10 public web flash page window: "
                    f"{page_newest:%Y-%m-%d %H:%M:%S} -> {page_oldest:%Y-%m-%d %H:%M:%S}"
                )

            for item in items:
                item_id = str(item.get("id") or "")
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)

                record = self._normalize_api_item(item)
                if not record:
                    continue

                publish_time = self._parse_publish_time(record["publish_time"])
                if publish_time and start_date <= publish_time <= end_date:
                    records.append(record)
                    if len(records) >= self.limit:
                        return records

            if valid_page_times and min(valid_page_times) < start_date:
                break

            next_max_time = str(items[-1].get("time") or "")
            if not next_max_time or next_max_time == max_time:
                break
            max_time = next_max_time

        if not records and newest_seen and oldest_seen and (newest_seen < start_date or oldest_seen > end_date):
            print(
                "Jin10 returned data outside configured range; "
                f"returned window: {newest_seen:%Y-%m-%d %H:%M:%S} -> {oldest_seen:%Y-%m-%d %H:%M:%S}; "
                f"configured range: {start_date:%Y-%m-%d %H:%M:%S} -> {end_date:%Y-%m-%d %H:%M:%S}."
            )
        return records

    def _fetch_from_html(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        print(f"Fetching Jin10 market flash page: {JIN10_WEB_FLASH_URL}")
        response = self.session.get(JIN10_WEB_FLASH_URL, timeout=self.timeout)
        response.raise_for_status()
        html = response.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        page_date = self._read_page_date(soup) or datetime.now().strftime("%Y-%m-%d")
        records: List[Dict[str, str]] = []
        for element in soup.select("div.jin-flash-item.flash")[: self.limit]:
            record = self._normalize_html_item(element, page_date)
            if not record:
                continue

            publish_time = self._parse_publish_time(record["publish_time"])
            if publish_time and start_date <= publish_time <= end_date:
                records.append(record)
        return records

    def _normalize_api_item(self, item: Dict[str, Any]) -> Optional[Dict[str, str]]:
        nested = item.get("data") if isinstance(item.get("data"), dict) else {}
        title, content = self._split_title_content(
            str(nested.get("title") or ""),
            str(nested.get("content") or ""),
        )
        if not content:
            return None
        if self._should_skip_record(title, content):
            return None

        return make_news_record(
            news_id=str(item.get("id") or ""),
            title=title,
            content=content,
            publish_time=str(item.get("time") or ""),
            source="金十数据",
            data_source="金十数据网页爬虫",
            data_frequency="7x24实时",
        )

    def _normalize_html_item(self, element, page_date: str) -> Optional[Dict[str, str]]:
        time_tag = element.select_one("div.item-time")
        right_tag = element.select_one("div.item-right")
        if not time_tag or not right_tag:
            return None

        time_text = clean_text(time_tag.get_text(" ", strip=True))
        raw_content = right_tag.get_text(" ", strip=True)
        if not time_text or not raw_content:
            return None

        title_tag = right_tag.select_one("b.right-common-title")
        raw_title = title_tag.get_text(" ", strip=True) if title_tag else ""
        title, content = self._split_title_content(raw_title, raw_content)
        if not content:
            return None
        if self._should_skip_record(title, content):
            return None

        publish_time = f"{page_date} {time_text}"

        return make_news_record(
            news_id=f"jin10_{publish_time.replace('-', '').replace(':', '').replace(' ', '')}",
            title=title,
            content=content,
            publish_time=publish_time,
            source="金十数据",
            data_source="金十数据网页爬虫",
            data_frequency="7x24实时",
        )

    @classmethod
    def _split_title_content(cls, raw_title: str, raw_content: str) -> Tuple[str, str]:
        title = cls._clean_jin10_text(raw_title)
        content = cls._clean_jin10_text(raw_content)

        bracket_title, bracket_body = cls._split_bracket_title(content)
        if bracket_title and bracket_body:
            return bracket_title, cls._strip_jin10_dateline(bracket_body)

        if title:
            title = cls._strip_title_brackets(title)
            if content.startswith(raw_title.strip()):
                content = cls._strip_leading_separator(content[len(raw_title.strip()) :])
            elif content.startswith(title):
                content = cls._strip_leading_separator(content[len(title) :])

        if not title:
            title, content = cls._infer_title_from_content(content)

        if not title:
            title = content[:80]

        content = cls._strip_jin10_dateline(content)
        return title, content

    @classmethod
    def _split_bracket_title(cls, content: str) -> Tuple[str, str]:
        match = re.match(r"^【(?P<title>[^】]{2,120})】(?P<body>.+)$", content)
        if not match:
            return "", content

        title = cls._strip_title_brackets(match.group("title"))
        body = cls._strip_leading_separator(match.group("body"))
        return title, body

    @classmethod
    def _infer_title_from_content(cls, content: str) -> Tuple[str, str]:
        patterns = [
            r"^(?P<title>.*?)\s+(?P<body>金十数据\d{1,2}月\d{1,2}日讯[，,].*)$",
            r"^(?P<title>.*?)\s+(?P<body>金十数据\d{1,2}月\d{1,2}日讯.*)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, content)
            if not match:
                continue

            title = cls._strip_title_brackets(match.group("title"))
            body = cls._strip_leading_separator(match.group("body"))
            if title and body:
                return title, body
        return "", content

    @staticmethod
    def _clean_jin10_text(content: str) -> str:
        content = re.sub(r"<br\s*/?>", " ", content, flags=re.IGNORECASE)
        content = re.sub(r"<.*?>", " ", content)
        content = clean_text(content)
        content = re.sub(r"\(?金十数据APP\)?$", "", content).strip()
        content = re.sub(r"打开金十数据APP.*$", "", content).strip()
        content = re.sub(r"扫码查看.*$", "", content).strip()
        content = re.sub(r"^\d+订阅\s*", "", content).strip()
        return content

    @staticmethod
    def _should_skip_record(title: str, content: str) -> bool:
        skip_prefixes = ("金十图示",)
        return title.startswith(skip_prefixes) or content.startswith(skip_prefixes)

    @staticmethod
    def _strip_title_brackets(value: str) -> str:
        return clean_text(value).strip("【】[]")

    @staticmethod
    def _strip_leading_separator(value: str) -> str:
        return clean_text(value).lstrip(" ：:，,。.-—").strip()

    @staticmethod
    def _strip_jin10_dateline(value: str) -> str:
        value = clean_text(value)
        value = re.sub(r"^金十数据\d{1,2}月\d{1,2}日讯[，,：: ]*", "", value)
        value = re.sub(r"^金十数据\d{4}-\d{2}-\d{2}日讯[，,：: ]*", "", value)
        return value.strip()

    @staticmethod
    def _parse_publish_time(value: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
        return None

    @staticmethod
    def _read_page_date(soup: BeautifulSoup) -> Optional[str]:
        page_text = soup.get_text(" ", strip=True)
        match = re.search(r"20\d{2}-\d{2}-\d{2}", page_text)
        if match:
            return match.group(0)

        match = re.search(r"\b(\d{2})-(\d{2})\b", page_text)
        if match:
            year = datetime.now().year
            return f"{year}-{match.group(1)}-{match.group(2)}"
        return None
