# ============================================================
# 财联社电报爬虫
# 接口: https://www.cls.cn/v1/roll/get_roll_list
# 需要 sign 签名（SHA1 + MD5）
# ============================================================

import hashlib
import time
import requests
from typing import List
from datetime import datetime

from models import NewsItem


# --- 请求头 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cls.cn/telegraph",
}

# --- 接口配置 ---
API_URL = "https://www.cls.cn/v1/roll/get_roll_list"
APP_NAME = "CailianpressWeb"
SV_VERSION = "8.4.6"


def _calc_sign(params: dict) -> str:
    """
    计算财联社签名
    算法: 参数按key ASCII排序 -> 拼接查询串 -> SHA1 -> MD5
    """
    # 按 key 的 ASCII 升序排序
    sorted_keys = sorted(params.keys())
    # 拼接成查询字符串
    query_string = "&".join(f"{k}={params[k]}" for k in sorted_keys)
    # SHA1
    sha1_hash = hashlib.sha1(query_string.encode("utf-8")).hexdigest()
    # MD5
    sign = hashlib.md5(sha1_hash.encode("utf-8")).hexdigest()
    return sign


def _timestamp_to_str(ts: int) -> str:
    """Unix时间戳转字符串"""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def crawl(rn: int = 50) -> List[NewsItem]:
    """
    财联社电报采集主函数
    rn: 每次获取条数（默认50）
    """
    print("[财联社] 开始采集...")

    current_ts = int(time.time())

    # 构造请求参数（不含 sign）
    params = {
        "app": APP_NAME,
        "category": "",
        "lastTime": str(current_ts),
        "last_time": str(current_ts),
        "os": "web",
        "rn": str(rn),
        "sv": SV_VERSION,
    }

    # 计算签名
    sign = _calc_sign(params)
    params["sign"] = sign

    news_list = []
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        data = resp.json()

        if data.get("errno") != 0:
            print(f"  [财联社] 接口返回错误: {data.get('msg', '未知错误')}")
            print(f"  [财联社] errno: {data.get('errno')}")
            return news_list

        roll_data = data.get("data", {}).get("roll_data", [])

        for item in roll_data:
            content = item.get("content", "")
            title = item.get("title", "")
            ctime = item.get("ctime", 0)
            share_url = item.get("shareurl", "")

            # 财联社电报通常 title 为空，用 content 前几十字作标题
            if not title:
                # 去除 HTML 标签
                clean_content = content.replace("<b>", "").replace("</b>", "")
                title = clean_content[:50] + ("..." if len(clean_content) > 50 else "")
                content = clean_content
            else:
                content = content.replace("<b>", "").replace("</b>", "")

            if not content:
                continue

            news_list.append(
                NewsItem(
                    title=title,
                    content=content,
                    source="财联社",
                    url=share_url,
                    publish_time=_timestamp_to_str(ctime),
                )
            )

    except Exception as e:
        print(f"  [财联社] 抓取失败: {e}")

    print(f"[财联社] 采集完成，共 {len(news_list)} 条")
    return news_list