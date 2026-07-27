from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from common.models import make_news_record
from common.utils import DEFAULT_HEADERS, clean_fx678_content, fetch_text


class Fx678Client:
    base_url = "https://www.fx678.com"
    list_base_url = "https://www.fx678.com/p/"

    def __init__(self, *, timeout: int, page_limit: int, concurrent_workers: int = 6) -> None:
        self.timeout = timeout
        self.page_limit = page_limit
        self.concurrent_workers = max(1, concurrent_workers)
        self.headers = {**DEFAULT_HEADERS, "Referer": "https://www.fx678.com/"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_by_time_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        tasks = self._get_tasks_by_date_range(start_date, end_date)
        if not tasks:
            return []

        with ThreadPoolExecutor(max_workers=self.concurrent_workers) as executor:
            details = executor.map(self._extract_detail, tasks)

        return [detail for detail in details if detail]

    def _get_tasks_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        tasks: List[Dict[str, str]] = []
        current_page = 1
        current_date_obj = datetime.now()

        while True:
            if self.page_limit > 0 and current_page > self.page_limit:
                break

            list_url = f"{self.list_base_url}{current_page}"
            print(f"Fetching FX678 list page {current_page}: {list_url}")
            html = fetch_text(self.session, list_url, timeout=self.timeout)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_elements = soup.select("div.time_i, li.body_zb_li")
            if not page_elements:
                break

            earliest_news_on_page: Optional[datetime] = None

            for element in page_elements:
                classes = element.get("class", [])
                if "time_i" in classes:
                    current_date_obj = self._parse_date_label(element.get_text(strip=True), current_date_obj)
                    continue

                if "body_zb_li" not in classes:
                    continue

                task = self._parse_list_item(element, current_date_obj)
                if not task:
                    continue

                news_time = task["news_time"]
                earliest_news_on_page = news_time

                if news_time < start_date:
                    return tasks

                if start_date <= news_time <= end_date:
                    tasks.append(
                        {
                            "id": f"fx678_{news_time.strftime('%Y%m%d%H%M%S')}",
                            "url": task["url"],
                            "title": task["title"],
                            "time": news_time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

            if earliest_news_on_page and earliest_news_on_page < start_date:
                break

            current_page += 1
            time.sleep(0.5)

        return tasks

    @staticmethod
    def _parse_date_label(date_text: str, fallback: datetime) -> datetime:
        try:
            return datetime.strptime(date_text.split()[0], "%Y-%m-%d")
        except ValueError:
            return fallback

    def _parse_list_item(self, element, current_date_obj: datetime) -> Optional[Dict[str, object]]:
        time_tag = element.select_one("div.zb_time a")
        title_tag = element.select_one("div.list_font_pic a")
        if not time_tag or not title_tag or not title_tag.get("href"):
            return None

        time_str = time_tag.get_text(strip=True)
        news_time = self._parse_news_time(current_date_obj, time_str)
        if not news_time:
            return None

        raw_title = title_tag.get_text(strip=True).replace("\n", " ").strip()
        match = re.search(r"【(.*?)】", raw_title)
        title = match.group(1) if match else raw_title.strip("【】")
        if "VIP" in title:
            return None

        return {
            "url": urljoin(self.base_url, title_tag["href"]),
            "title": title,
            "news_time": news_time,
        }

    @staticmethod
    def _parse_news_time(current_date_obj: datetime, time_str: str) -> Optional[datetime]:
        full_time_str = f"{current_date_obj.strftime('%Y%m%d')} {time_str}"
        for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d %H:%M"):
            try:
                return datetime.strptime(full_time_str, fmt)
            except ValueError:
                pass
        return None

    def _extract_detail(self, task: Dict[str, str]) -> Optional[Dict[str, str]]:
        detail_session = requests.Session()
        detail_session.headers.update(self.headers)
        html = fetch_text(detail_session, task["url"], timeout=self.timeout)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        content_tag = soup.select_one("div.article-main")
        if content_tag:
            content = clean_fx678_content(content_tag.get_text(strip=True))
        else:
            content = "No content found."

        return make_news_record(
            news_id=task["id"],
            title=task["title"],
            content=content,
            publish_time=task["time"],
            source="汇通财经",
            data_source="汇通财经网页爬虫",
            data_frequency="7x24实时",
        )
