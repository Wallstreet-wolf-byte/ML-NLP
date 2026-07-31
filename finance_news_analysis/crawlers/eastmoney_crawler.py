# ============================================================
# 东方财富新闻爬虫
# 接口: search-api-web.eastmoney.com/search/jsonp (JSONP格式)
# 通过关键词搜索获取财经新闻
# ============================================================

import re
import json
import time
import requests
from typing import List
from bs4 import BeautifulSoup

from models import NewsItem


# --- 请求头 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://so.eastmoney.com/",
}

# --- 搜索关键词（覆盖各市场） ---
SEARCH_KEYWORDS = [
    "A股", "港股", "美股", "黄金", "白银", "期货",
    "美联储", "央行", "经济数据",
]


def _parse_jsonp(jsonp_text: str) -> dict:
    """从JSONP响应中提取JSON数据"""
    # 匹配 callback({...}) 格式
    match = re.search(r"\((.+)\)$", jsonp_text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 如果不是JSONP，直接当JSON解析
    return json.loads(jsonp_text)


def _clean_html_tags(text: str) -> str:
    """去除 <em></em> 等 HTML 标签"""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(strip=True)


def fetch_news_by_keyword(keyword: str, page_size: int = 10) -> List[NewsItem]:
    """
    按关键词从东方财富搜索新闻
    返回 NewsItem 列表
    """
    # 构造 param 参数
    param = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": page_size,
                "preTag": "",
                "postTag": "",
            }
        },
    }

    params = {
        "cb": "jQuery_callback",
        "param": json.dumps(param, ensure_ascii=False),
        "_": str(int(time.time() * 1000)),
    }

    news_list = []
    try:
        resp = requests.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        resp.encoding = "utf-8"
        data = _parse_jsonp(resp.text)

        articles = (
            data.get("result", {}).get("cmsArticleWebOld", [])
            if data.get("result")
            else []
        )

        for article in articles:
            title = _clean_html_tags(article.get("title", ""))
            content = _clean_html_tags(article.get("content", ""))
            date = article.get("date", "")
            code = article.get("code", "")
            media = article.get("mediaName", "")

            if not title and not content:
                continue

            url = f"http://finance.eastmoney.com/a/{code}.html" if code else ""

            news_list.append(
                NewsItem(
                    title=title,
                    content=content if content else title,
                    source="东方财富",
                    url=url,
                    publish_time=date,
                )
            )

    except Exception as e:
        print(f"  [东方财富] 关键词「{keyword}」抓取失败: {e}")

    return news_list


def crawl(max_per_keyword: int = 8) -> List[NewsItem]:
    """
    东方财富新闻采集主函数
    按多个关键词搜索，合并去重
    """
    print("[东方财富] 开始采集...")
    all_news = []
    seen_titles = set()

    for keyword in SEARCH_KEYWORDS:
        news = fetch_news_by_keyword(keyword, page_size=max_per_keyword)
        for item in news:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_news.append(item)
        print(f"  关键词「{keyword}」: 获取 {len(news)} 条")
        time.sleep(0.5)  # 礼貌延时

    print(f"[东方财富] 采集完成，共 {len(all_news)} 条（去重后）")
    return all_news