# ============================================================
# 金十数据快讯爬虫
# 接口: https://flash-api.jin10.com/get_flash_list
# 需要 x-app-id 请求头
# ============================================================

import re
import time
import requests
from typing import List
from datetime import datetime

from models import NewsItem


# --- 请求头 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-app-id": "SO1EJGmNgCtmpcPF",
    "x-version": "1.0.0",
    "Origin": "https://www.jin10.com",
    "Referer": "https://www.jin10.com/",
}

# --- 接口配置 ---
API_URL = "https://flash-api.jin10.com/get_flash_list"


def _clean_text(text: str) -> str:
    """清洗 HTML 标签和特殊字符"""
    if not text:
        return ""
    # 去除 <b></b> 等标签
    text = re.sub(r"<[^>]+>", "", text)
    # 去除 &nbsp; 等
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return text.strip()


def crawl(count: int = 50) -> List[NewsItem]:
    """
    金十数据快讯采集主函数
    count: 获取条数（默认50）
    """
    print("[金十数据] 开始采集...")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "channel": "-8200",
        "vip": "1",
        "max_time": now_str,
        "count": str(count),
        "t": str(int(time.time() * 1000)),
    }

    news_list = []
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        data = resp.json()

        flash_list = data.get("data", [])

        if not flash_list:
            print("  [金十数据] 未获取到数据")
            return news_list

        for item in flash_list:
            # 金十数据的标题和内容嵌套在 data 字段中
            inner_data = item.get("data", {})
            # inner_data 可能是 dict（有 title/content）或字符串
            if isinstance(inner_data, dict):
                title = inner_data.get("title", "")
                content = inner_data.get("content", "")
            elif isinstance(inner_data, str):
                title = ""
                content = inner_data
            else:
                continue

            content = _clean_text(content)
            title = _clean_text(title)

            # 如果没有标题，用内容前50字作标题
            if not title:
                title = content[:50] + ("..." if len(content) > 50 else "")

            if not content:
                continue

            publish_time = item.get("time", "")
            item_id = item.get("id", "")
            url = f"https://flash.jin10.com/detail/{item_id}" if item_id else ""
            important = item.get("important", 0)

            news_list.append(
                NewsItem(
                    title=title,
                    content=content,
                    source="金十数据",
                    url=url,
                    publish_time=publish_time,
                )
            )

    except Exception as e:
        print(f"  [金十数据] 抓取失败: {e}")

    print(f"[金十数据] 采集完成，共 {len(news_list)} 条")
    return news_list