# ============================================================
# 华尔街见闻快讯爬虫
# 接口: api-one.wallstcn.com/apiv1/content/lives
# ============================================================

import time
import requests
from typing import List
from datetime import datetime

from models import NewsItem


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# 快讯API
LIVES_API = "https://api-one.wallstcn.com/apiv1/content/lives"
# 文章API
ARTICLES_API = "https://api-one.wallstcn.com/apiv1/content/information-flow"


def _timestamp_to_str(ts) -> str:
    """时间戳转字符串"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def crawl(limit: int = 30) -> List[NewsItem]:
    """华尔街见闻采集主函数（快讯+文章）"""
    print("[华尔街见闻] 开始采集...")

    all_news = []
    seen_titles = set()

    # --- 1. 快讯流 ---
    try:
        params = {"channel": "global-channel", "limit": str(limit)}
        resp = requests.get(LIVES_API, params=params, headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        data = resp.json()

        items = data.get("data", {}).get("items", [])

        count = 0
        for item in items:
            title = item.get("title", "")
            content = item.get("content_text", "") or item.get("content_short", "")
            display_time = item.get("display_time", "")
            uri = item.get("uri", "")

            if not title and not content:
                continue

            if not title:
                title = content[:50] + ("..." if len(content) > 50 else "")

            if title in seen_titles:
                continue
            seen_titles.add(title)

            url = f"https://wallstreetcn.com/news/global/{uri}" if uri else ""

            all_news.append(NewsItem(
                title=title,
                content=content if content else title,
                source="华尔街见闻",
                url=url,
                publish_time=_timestamp_to_str(display_time),
            ))
            count += 1

        print(f"  快讯流: 获取 {count} 条")

    except Exception as e:
        print(f"  [华尔街见闻] 快讯抓取失败: {e}")

    # --- 2. 文章流 ---
    try:
        params = {"channel": "global-channel", "accept": "article", "limit": "20"}
        resp = requests.get(ARTICLES_API, params=params, headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        data = resp.json()

        items = data.get("data", {}).get("items", [])

        count = 0
        for item in items:
            # 过滤广告和专题
            resource_type = item.get("resource_type", "")
            if resource_type in ("ad", "theme"):
                continue

            resource = item.get("resource", {})
            title = resource.get("title", "")
            content = resource.get("content_short", "")
            display_time = resource.get("display_time", "")
            uri = resource.get("uri", "")

            if not title:
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)

            url = f"https://wallstreetcn.com/articles/{uri}" if uri else ""

            all_news.append(NewsItem(
                title=title,
                content=content if content else title,
                source="华尔街见闻",
                url=url,
                publish_time=_timestamp_to_str(display_time),
            ))
            count += 1

        print(f"  文章流: 获取 {count} 条")

    except Exception as e:
        print(f"  [华尔街见闻] 文章抓取失败: {e}")

    print(f"[华尔街见闻] 采集完成，共 {len(all_news)} 条")
    return all_news