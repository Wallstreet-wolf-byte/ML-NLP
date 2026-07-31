# ============================================================
# 统一采集调度器
# 调用所有爬虫，合并结果，去重，保存到JSON文件
# ============================================================

import json
import os
import sys
from datetime import datetime
from typing import List

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import NewsItem, news_list_to_dicts
from crawlers.eastmoney_crawler import crawl as crawl_eastmoney
from crawlers.cls_crawler import crawl as crawl_cls
from crawlers.jinshi_crawler import crawl as crawl_jinshi
from crawlers.sina_crawler import crawl as crawl_sina
from crawlers.wallstreet_crawler import crawl as crawl_wallstreet
from crawlers.finnhub_crawler import crawl as crawl_finnhub
from crawlers.alphavantage_crawler import crawl as crawl_alphavantage


def collect_all_news() -> List[NewsItem]:
    """
    调用所有数据源采集新闻，合并去重
    返回统一的 NewsItem 列表
    """
    print("=" * 60)
    print(f"  开始采集财经新闻  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    all_news: List[NewsItem] = []
    seen_contents = set()  # 用于去重（取内容前100字）

    # --- 1. 东方财富 ---
    try:
        em_news = crawl_eastmoney(max_per_keyword=8)
        for news in em_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [东方财富] 采集异常: {e}")

    print()

    # --- 2. 财联社 ---
    try:
        cls_news = crawl_cls(rn=50)
        for news in cls_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [财联社] 采集异常: {e}")

    print()

    # --- 3. 金十数据 ---
    try:
        js_news = crawl_jinshi(count=50)
        for news in js_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [金十数据] 采集异常: {e}")

    print()

    # --- 4. 新浪财经 ---
    try:
        sina_news = crawl_sina(num_per_channel=20)
        for news in sina_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [新浪财经] 采集异常: {e}")

    print()

    # --- 5. 华尔街见闻 ---
    try:
        ws_news = crawl_wallstreet(limit=30)
        for news in ws_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [华尔街见闻] 采集异常: {e}")

    print()

    # --- 6. Finnhub (国际API) ---
    try:
        fh_news = crawl_finnhub(max_news=30)
        for news in fh_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [Finnhub] 采集异常: {e}")

    print()

    # --- 7. Alpha Vantage (国际API) ---
    try:
        av_news = crawl_alphavantage(max_news=30)
        for news in av_news:
            key = news.content[:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_news.append(news)
    except Exception as e:
        print(f"  [AlphaVantage] 采集异常: {e}")

    print()
    print("=" * 60)
    print(f"  采集完成！")
    print(f"  7个数据源去重后共: {len(all_news)} 条")
    print("=" * 60)

    return all_news


def save_news(news_list: List[NewsItem], output_dir: str = None) -> str:
    """
    将新闻列表保存为 JSON 文件
    返回保存的文件路径
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )

    os.makedirs(output_dir, exist_ok=True)

    # 文件名格式: news_20260730.json
    today = datetime.now().strftime("%Y%m%d")
    filename = f"news_{today}.json"
    filepath = os.path.join(output_dir, filename)

    # 转为字典列表
    data = {
        "collect_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(news_list),
        "news": news_list_to_dicts(news_list),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  数据已保存: {filepath}")
    return filepath


def load_news(filepath: str) -> List[NewsItem]:
    """
    从 JSON 文件加载新闻
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    news_list = []
    for item in data.get("news", []):
        news_list.append(NewsItem(**item))

    return news_list


if __name__ == "__main__":
    # 直接运行此文件时执行采集
    news = collect_all_news()

    if news:
        filepath = save_news(news)

        # 打印前5条预览
        print(f"\n  前5条新闻预览:")
        print("  " + "-" * 56)
        for i, n in enumerate(news[:5], 1):
            print(f"  {i}. [{n.source}] {n.title[:40]}")
            print(f"     时间: {n.publish_time}")
            print()
    else:
        print("\n  未采集到任何新闻，请检查网络或数据源。")