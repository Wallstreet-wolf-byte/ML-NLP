# ============================================================
# Flask 网页看板
# 展示新闻分析结果，按市场分类，带情绪颜色标签
# ============================================================

import os
import sys
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, redirect, send_file

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WEB_HOST, WEB_PORT, WEB_DEBUG, DATA_DIR

app = Flask(__name__)


def load_analyzed_news():
    """加载最新分析结果"""
    today = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(DATA_DIR, f"news_analyzed_{today}.json")

    if not os.path.exists(filepath):
        # 尝试找最新的分析文件
        files = sorted(
            [f for f in os.listdir(DATA_DIR) if f.startswith("news_analyzed_")],
            reverse=True,
        )
        if files:
            filepath = os.path.join(DATA_DIR, files[0])
        else:
            return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# --- 高影响关键词（用于星级评分加成） ---
_HIGH_IMPACT_KEYWORDS = [
    "降息", "加息", "降准", "美联储", "央行", "国务院",
    "贸易战", "关税", "制裁", "战争", "冲突",
    "退市", "爆仓", "暴跌", "涨停", "崩盘",
    "重大", "紧急", "突发", "重磅",
]

_SOURCE_WEIGHT = {
    "财联社": 1.5,
    "金十数据": 1.5,
    "华尔街见闻": 1.3,
    "新浪财经": 1.1,
    "东方财富": 1.0,
}


def compute_news_score(news: dict) -> float:
    """
    计算单条新闻的综合影响力评分（用于 Top 10 排序）
    评分因素：影响等级 + 情绪方向 + 来源权重 + 高影响关键词 + 大模型置信度
    """
    score = 0.0

    # 1. 影响等级基础分
    impact = news.get("impact_level", "低")
    score += {"高": 3.0, "中": 2.0, "低": 1.0}.get(impact, 1.0)

    # 2. 情绪方向加分（有利空或利多方向比中性更有参考价值）
    sentiment = news.get("sentiment", "中性")
    if sentiment in ("利好", "利空"):
        score += 1.0

    # 3. 来源权重
    source = news.get("source", "")
    score += _SOURCE_WEIGHT.get(source, 1.0) - 1.0  # 归一化到 0~0.5

    # 4. 高影响关键词加成
    text = f"{news.get('title', '')} {news.get('content', '')}"
    keyword_hits = sum(1 for kw in _HIGH_IMPACT_KEYWORDS if kw in text)
    score += keyword_hits * 0.5

    # 5. 关联板块数量（涉及越多板块影响越大）
    sectors = news.get("affected_sectors", [])
    score += min(len(sectors), 3) * 0.3

    # 6. 大模型置信度加成
    llm_conf = news.get("llm_confidence", 0.0)
    if llm_conf > 0:
        score += llm_conf * 0.5

    # 7. 大模型已分析的新闻额外加分（说明被AI判定为重要）
    if news.get("llm_analysis"):
        score += 0.5

    return score


def score_to_stars(score: float) -> int:
    """将评分转换为 1-5 星"""
    if score >= 6.0:
        return 5
    elif score >= 4.5:
        return 4
    elif score >= 3.0:
        return 3
    elif score >= 2.0:
        return 2
    else:
        return 1


def get_top_news(news_list: list, top_n: int = 10) -> list:
    """
    获取影响力最大的 N 条新闻，附带星级评分
    """
    scored = []
    for n in news_list:
        score = compute_news_score(n)
        stars = score_to_stars(score)
        # 复制一份，避免修改原始数据
        item = dict(n)
        item["_score"] = round(score, 2)
        item["_stars"] = stars
        scored.append(item)

    # 按评分降序排列
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_n]


def get_stats(news_list):
    """计算统计概览"""
    stats = {
        "total": len(news_list),
        "利好": 0,
        "利空": 0,
        "中性": 0,
        "高影响": 0,
        "中影响": 0,
        "低影响": 0,
        "markets": {},
        "sectors": {},
    }

    for n in news_list:
        sentiment = n.get("sentiment", "中性")
        impact = n.get("impact_level", "低")
        stats[sentiment] += 1
        stats[f"{impact}影响"] += 1

        for m in n.get("markets", []):
            stats["markets"][m] = stats["markets"].get(m, 0) + 1

        for s in n.get("affected_sectors", []):
            stats["sectors"][s] = stats["sectors"].get(s, 0) + 1

    return stats


@app.route("/")
def index():
    """默认入口：跳转到 React + ECharts 单页看板"""
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    """React + TypeScript + ECharts 单页看板（原始 HTML，不经 Jinja 渲染，避免与 JSX 的 {{ }} 冲突）"""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "dashboard.html")
    return send_file(html_path)


@app.route("/classic")
def classic():
    """旧版服务端渲染看板（备用）"""
    data = load_analyzed_news()
    if data is None:
        return render_template("index.html", error=True)

    news_list = data.get("news", [])
    stats = get_stats(news_list)

    # 按市场分组
    market_groups = {}
    for n in news_list:
        for m in n.get("markets", ["其他"]):
            if m not in market_groups:
                market_groups[m] = []
            market_groups[m].append(n)

    # 按影响程度排序（高>中>低）
    impact_order = {"高": 0, "中": 1, "低": 2}
    for m in market_groups:
        market_groups[m].sort(key=lambda x: impact_order.get(x.get("impact_level", "低"), 3))

    # 按市场条数排序
    sorted_markets = sorted(market_groups.items(), key=lambda x: -len(x[1]))

    # 获取影响最大的10条新闻（带星级评分）
    top_news = get_top_news(news_list, top_n=10)

    # 获取大师Agent分析结果
    master_analysis = data.get("master_analysis", [])

    return render_template(
        "index.html",
        news_list=news_list,
        stats=stats,
        market_groups=sorted_markets,
        top_news=top_news,
        master_analysis=master_analysis,
        analyze_time=data.get("analyze_time", ""),
        daily_summary=data.get("daily_summary", ""),
        error=False,
    )


@app.route("/api/news")
def api_news():
    """API: 返回所有新闻JSON"""
    data = load_analyzed_news()
    if data is None:
        return jsonify({"error": "暂无数据，请先运行采集和分析"}), 404
    return jsonify(data)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """API: 重新采集+分析（触发完整流程）"""
    try:
        from crawlers.collector import collect_all_news, save_news
        from analyzer.analyzer import analyze_news, save_analyzed_news

        news = collect_all_news()
        if news:
            save_news(news)
            news = analyze_news(news)
            save_analyzed_news(news)
            return jsonify({"status": "ok", "count": len(news)})
        return jsonify({"status": "error", "message": "未采集到新闻"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/trends")
def api_trends():
    """API: 返回历史趋势数据（最近N天）"""
    try:
        files = sorted(
            [f for f in os.listdir(DATA_DIR) if f.startswith("news_analyzed_")],
        )
    except Exception:
        return jsonify({"error": "无法读取数据目录"}), 500

    if not files:
        return jsonify({"error": "暂无历史数据"}), 404

    # 最多取最近30天
    recent_files = files[-30:]

    trends = []
    for filename in recent_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        # 从文件名提取日期: news_analyzed_20260730.json -> 2026-07-30
        date_str = filename.replace("news_analyzed_", "").replace(".json", "")
        if len(date_str) == 8:
            date_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
            date_display = date_str

        news_list = data.get("news", [])
        pos = sum(1 for n in news_list if n.get("sentiment") == "利好")
        neg = sum(1 for n in news_list if n.get("sentiment") == "利空")
        neu = sum(1 for n in news_list if n.get("sentiment") == "中性")
        total = len(news_list)

        # 市场分布
        market_counts = {}
        for n in news_list:
            for m in n.get("markets", []):
                market_counts[m] = market_counts.get(m, 0) + 1

        trends.append({
            "date": date_display,
            "total": total,
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "markets": market_counts,
        })

    return jsonify({"trends": trends})


@app.route("/api/masters")
def api_masters():
    """API: 返回大师Agent分析结果"""
    data = load_analyzed_news()
    if data is None:
        return jsonify({"error": "暂无数据"}), 404
    masters = data.get("master_analysis", [])
    if not masters:
        return jsonify({"error": "暂无大师分析数据，请先运行分析模块"}), 404
    return jsonify({"masters": masters})


@app.route("/api/market-indices")
def api_market_indices():
    """API: 返回大盘指数实时行情（A股/美股/韩股）"""
    try:
        from analyzer.market_index import fetch_index_data, generate_market_summary

        result = fetch_index_data()
        summary = generate_market_summary(result["indices"])
        result["market_summary"] = summary
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"获取大盘指数失败: {str(e)}"}), 500


if __name__ == "__main__":
    print(f"  网页看板启动中...")
    print(f"  访问地址: http://{WEB_HOST}:{WEB_PORT}")
    print(f"  按 Ctrl+C 停止")
    print()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)