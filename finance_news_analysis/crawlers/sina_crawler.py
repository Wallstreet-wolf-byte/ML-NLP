# ============================================================
# 新浪财经新闻爬虫
# 接口: feed.mix.sina.com.cn/api/roll/get
# ============================================================

import time
import requests
from typing import List
from datetime import datetime

from models import NewsItem


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

API_URL = "https://feed.mix.sina.com.cn/api/roll/get"

# 多个频道ID
CHANNELS = [
    ("2509", "财经"),
    ("2510", "股票"),
    ("2511", "港股"),
    ("2512", "美股"),
    ("2516", "期货"),
    ("2517", "外汇"),
]


def crawl(num_per_channel: int = 20) -> List[NewsItem]:
    """新浪财经新闻采集主函数"""
    print("[新浪财经] 开始采集...")

    all_news = []
    seen_titles = set()

    for lid, channel_name in CHANNELS:
        params = {
            "pageid": "153",
            "lid": lid,
            "k": "",
            "num": str(num_per_channel),
            "page": "1",
        }

        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=10)
            resp.encoding = "utf-8"
            data = resp.json()

            items = data.get("result", {}).get("data", [])

            count = 0
            for item in items:
                title = item.get("title", "")
                url = item.get("url", "")
                intro = item.get("intro", "")
                ctime = item.get("ctime", "")
                media = item.get("media_name", "")

                if not title:
                    continue
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # 时间转换
                publish_time = ""
                if ctime:
                    try:
                        publish_time = datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        publish_time = str(ctime)

                content = intro if intro else title

                all_news.append(NewsItem(
                    title=title,
                    content=content,
                    source="新浪财经",
                    url=url,
                    publish_time=publish_time,
                ))
                count += 1

            print(f"  频道「{channel_name}」: 获取 {count} 条")
            time.sleep(0.3)

        except Exception as e:
            print(f"  [新浪财经] 频道「{channel_name}」抓取失败: {e}")

    print(f"[新浪财经] 采集完成，共 {len(all_news)} 条")
    return all_news