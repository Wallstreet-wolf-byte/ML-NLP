# ============================================================
# Alpha Vantage 国际新闻爬虫
# 通过 Alpha Vantage News & Sentiments API 获取全球市场新闻
# 免费注册: https://www.alphavantage.co/support/#api-key
# 免费层每天25次调用
# ============================================================

import os
import sys
import requests
from datetime import datetime
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ALPHAVANTAGE_CONFIG
from models import NewsItem


def crawl(max_news: int = 30) -> List[NewsItem]:
    """
    通过 Alpha Vantage API 采集全球市场新闻
    """
    if not ALPHAVANTAGE_CONFIG.get("enabled"):
        print("  [AlphaVantage] 未启用（在config.py中设置ALPHAVANTAGE_CONFIG.enabled=True）")
        return []

    api_key = ALPHAVANTAGE_CONFIG.get("api_key", "")
    if not api_key:
        print("  [AlphaVantage] 未配置API Key")
        return []

    base_url = ALPHAVANTAGE_CONFIG.get("base_url", "https://www.alphavantage.co/api")
    topics = ALPHAVANTAGE_CONFIG.get("topics", "financial_markets")

    print(f"  [AlphaVantage] 开始采集全球市场新闻...")

    url = f"{base_url}/news_sentiment"
    params = {
        "function": "NEWS_SENTIMENT",
        "topics": topics,
        "apikey": api_key,
        "limit": str(max_news),
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [AlphaVantage] API请求失败: {e}")
        return []

    # 检查API返回的信息
    if "Information" in data:
        print(f"  [AlphaVantage] API提示: {data['Information']}")
        return []
    if "Note" in data:
        print(f"  [AlphaVantage] API频率限制: {data['Note']}")
        return []

    feed = data.get("feed", [])
    print(f"  [AlphaVantage] 获取到 {len(feed)} 条新闻")

    news_list = []
    for item in feed[:max_news]:
        try:
            # Alpha Vantage 返回的 sentiment_label: "Positive"/"Negative"/"Neutral"
            av_sentiment = item.get("overall_sentiment_label", "")

            # 提取标题
            title = item.get("title", "")

            # 提取摘要
            summary = item.get("summary", title)

            # 提取来源
            source_name = item.get("source", "AlphaVantage")

            # 提取时间
            time_str = item.get("time_published", "")
            publish_time = ""
            if time_str and len(time_str) >= 14:
                # 格式: 20260730T103000 -> 2026-07-30 10:30:00
                try:
                    publish_time = (
                        f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]} "
                        f"{time_str[9:11]}:{time_str[11:13]}:{time_str[13:15]}"
                    )
                except Exception:
                    publish_time = time_str

            # 提取URL
            url = item.get("url", "")

            # 提取关联的股票代码
            ticker_sentiments = item.get("ticker_sentiment", [])
            tickers = [ts.get("ticker", "") for ts in ticker_sentiments[:5]]
            ticker_str = ", ".join(tickers) if tickers else ""

            # 在内容中加上关联股票和情绪评分
            sentiment_score = item.get("overall_sentiment_score", 0)
            content = summary
            if ticker_str:
                content += f"\n关联股票: {ticker_str}"
            content += f"\n情绪评分: {sentiment_score} ({av_sentiment})"

            # 提取相关话题
            topics_raw = item.get("topics", [])
            topic_names = [t.get("topic", "") for t in topics_raw[:3]]
            if topic_names:
                content += f"\n话题: {', '.join(topic_names)}"

            news = NewsItem(
                title=title,
                content=content,
                source=f"AlphaVantage",
                url=url,
                publish_time=publish_time,
            )
            news_list.append(news)

        except Exception as e:
            print(f"  [AlphaVantage] 解析新闻失败: {e}")
            continue

    print(f"  [AlphaVantage] 采集完成: {len(news_list)} 条")
    return news_list


if __name__ == "__main__":
    news = crawl()
    for n in news[:5]:
        print(f"  [{n.source}] {n.title}")
