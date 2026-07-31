# ============================================================
# Finnhub 国际新闻爬虫
# 通过 Finnhub API 获取美股/全球市场新闻
# 免费注册: https://finnhub.io/register
# ============================================================

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FINNHUB_CONFIG
from models import NewsItem


def _fetch_market_news(api_key: str, base_url: str) -> List[dict]:
    """获取通用市场新闻"""
    url = f"{base_url}/news"
    params = {"category": "general", "token": api_key}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [Finnhub] 市场新闻获取失败: {e}")
        return []


def _fetch_company_news(api_key: str, base_url: str, symbols: List[str]) -> List[dict]:
    """获取关注公司的新闻"""
    all_news = []
    today = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for symbol in symbols:
        url = f"{base_url}/company-news"
        params = {
            "symbol": symbol,
            "from": from_date,
            "to": today,
            "token": api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            news_items = resp.json()
            # 限制每个公司最多5条，避免过多
            all_news.extend(news_items[:5])
        except Exception as e:
            print(f"  [Finnhub] {symbol} 公司新闻获取失败: {e}")
            continue

    return all_news


def crawl(max_news: int = 30) -> List[NewsItem]:
    """
    通过 Finnhub API 采集国际市场新闻
    """
    if not FINNHUB_CONFIG.get("enabled"):
        print("  [Finnhub] 未启用（在config.py中设置FINNHUB_CONFIG.enabled=True）")
        return []

    api_key = FINNHUB_CONFIG.get("api_key", "")
    if not api_key:
        print("  [Finnhub] 未配置API Key")
        return []

    base_url = FINNHUB_CONFIG.get("base_url", "https://finnhub.io/api/v1")
    symbols = FINNHUB_CONFIG.get("symbols", [])

    print(f"  [Finnhub] 开始采集国际新闻...")
    print(f"  [Finnhub] 关注股票: {', '.join(symbols)}")

    news_list = []

    # 1. 获取通用市场新闻
    market_news = _fetch_market_news(api_key, base_url)
    print(f"  [Finnhub] 市场新闻: {len(market_news)} 条")

    for item in market_news[:max_news]:
        try:
            news = NewsItem(
                title=item.get("headline", ""),
                content=item.get("summary", item.get("headline", "")),
                source="Finnhub",
                url=item.get("url", ""),
                publish_time=datetime.fromtimestamp(
                    item.get("datetime", 0)
                ).strftime("%Y-%m-%d %H:%M:%S") if item.get("datetime") else "",
            )
            news_list.append(news)
        except Exception:
            continue

    # 2. 获取公司新闻
    company_news = _fetch_company_news(api_key, base_url, symbols)
    print(f"  [Finnhub] 公司新闻: {len(company_news)} 条")

    seen_urls = {n.url for n in news_list if n.url}
    for item in company_news:
        url = item.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            news = NewsItem(
                title=item.get("headline", ""),
                content=item.get("summary", item.get("headline", "")),
                source=f"Finnhub-{item.get('related', '')}",
                url=url,
                publish_time=datetime.fromtimestamp(
                    item.get("datetime", 0)
                ).strftime("%Y-%m-%d %H:%M:%S") if item.get("datetime") else "",
            )
            news_list.append(news)
        except Exception:
            continue

    print(f"  [Finnhub] 采集完成: {len(news_list)} 条")
    return news_list


if __name__ == "__main__":
    news = crawl()
    for n in news[:5]:
        print(f"  [{n.source}] {n.title}")
