# ============================================================
# 分析调度器
# 串联：市场分类 → 情绪分析 → 影响评估
# 对每条新闻执行完整分析，更新 NewsItem 字段
# ============================================================

import os
import sys
import json
from datetime import datetime
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import NewsItem, news_list_to_dicts
from analyzer.classifier import classify_market
from analyzer.sentiment import analyze_sentiment, init_dicts
from analyzer.impact import assess_impact
from analyzer.llm_analyzer import analyze_news_batch, generate_daily_summary
from analyzer.master_agents import run_master_agents

# 模块级缓存：大模型每日总结
_daily_summary = ""
# 模块级缓存：大师Agent分析结果
_master_results = []


def analyze_news(news_list: List[NewsItem]) -> List[NewsItem]:
    """
    对新闻列表执行完整分析（分类 + 情绪 + 影响评估）
    直接修改 NewsItem 对象的字段
    """
    print("=" * 60)
    print(f"  开始新闻分析  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化词典
    init_dicts()
    print()

    stats = {
        "总条数": 0,
        "利好": 0,
        "利空": 0,
        "中性": 0,
        "高影响": 0,
        "中影响": 0,
        "低影响": 0,
    }

    market_stats = {}  # 各市场条数统计

    for news in news_list:
        stats["总条数"] += 1

        # 拼接标题+内容用于分析
        text = f"{news.title} {news.content}"

        # 1. 市场分类
        news.markets = classify_market(text)
        for m in news.markets:
            market_stats[m] = market_stats.get(m, 0) + 1

        # 2. 情绪分析
        sentiment, pos_score, neg_score, hits = analyze_sentiment(text)
        news.sentiment = sentiment
        stats[sentiment] += 1

        # 3. 影响评估
        impact_level, sectors = assess_impact(
            text, sentiment, pos_score, neg_score, news.source
        )
        news.impact_level = impact_level
        news.affected_sectors = sectors

        impact_key = f"{impact_level}影响"
        stats[impact_key] += 1

    # --- 打印统计 ---
    print(f"  分析完成！共分析 {stats['总条数']} 条新闻")
    print()
    print(f"  情绪分布:")
    print(f"    利好: {stats['利好']} 条")
    print(f"    利空: {stats['利空']} 条")
    print(f"    中性: {stats['中性']} 条")
    print()
    print(f"  影响程度分布:")
    print(f"    高: {stats['高影响']} 条")
    print(f"    中: {stats['中影响']} 条")
    print(f"    低: {stats['低影响']} 条")
    print()
    print(f"  市场分布:")
    for market, count in sorted(market_stats.items(), key=lambda x: -x[1]):
        print(f"    {market}: {count} 条")

    print()
    print("=" * 60)

    # --- 4. 大模型深度分析（可选） ---
    print()
    news_list = analyze_news_batch(news_list)

    # --- 5. 生成每日市场总结（可选） ---
    daily_summary = generate_daily_summary(news_list)
    if daily_summary:
        print()
        print("  [大模型] 每日市场总结:")
        print("  " + "-" * 56)
        print(f"  {daily_summary}")
        print("  " + "-" * 56)
        # 保存到模块级变量供 save_analyzed_news 使用
        global _daily_summary
        _daily_summary = daily_summary

    # --- 6. 炒股大师Agent分析 ---
    global _master_results
    _master_results = run_master_agents(news_list)

    return news_list


def save_analyzed_news(news_list: List[NewsItem], output_dir: str = None) -> str:
    """
    保存分析后的新闻到 JSON 文件
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )

    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    filename = f"news_analyzed_{today}.json"
    filepath = os.path.join(output_dir, filename)

    data = {
        "analyze_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(news_list),
        "daily_summary": _daily_summary,
        "master_analysis": _master_results,
        "news": news_list_to_dicts(news_list),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  分析结果已保存: {filepath}")
    return filepath


def load_and_analyze(input_filepath: str = None) -> str:
    """
    加载采集的原始新闻，执行分析，保存结果
    """
    if input_filepath is None:
        # 默认加载今天的采集数据
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        today = datetime.now().strftime("%Y%m%d")
        input_filepath = os.path.join(data_dir, f"news_{today}.json")

    if not os.path.exists(input_filepath):
        print(f"  错误: 找不到新闻数据文件 {input_filepath}")
        print(f"  请先运行第2关的采集模块 (crawlers/collector.py)")
        return None

    # 加载原始新闻
    with open(input_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    news_list = []
    for item in data.get("news", []):
        news_list.append(NewsItem(**item))

    print(f"  已加载 {len(news_list)} 条原始新闻（来源: {input_filepath}）")
    print()

    # 执行分析
    news_list = analyze_news(news_list)

    # 保存结果
    filepath = save_analyzed_news(news_list)

    # 打印高影响新闻预览
    high_impact = [n for n in news_list if n.impact_level == "高"]
    if high_impact:
        print(f"\n  高影响新闻预览（共 {len(high_impact)} 条）:")
        print("  " + "-" * 56)
        for i, n in enumerate(high_impact[:10], 1):
            market_str = "/".join(n.markets)
            sectors_str = "/".join(n.affected_sectors) if n.affected_sectors else "无"
            print(f"  {i}. [{n.source}] [{market_str}] [{n.sentiment}]")
            print(f"     {n.title[:50]}")
            print(f"     板块: {sectors_str}")
            print()

    return filepath


if __name__ == "__main__":
    result = load_and_analyze()
    if result:
        print(f"\n  第3关完成！分析结果: {result}")