# ============================================================
# 市场分类器
# 将新闻按关键词归入 A股/恒指期货主连/美股/黄金期货/白银期货/其他期货
# ============================================================

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MARKET_KEYWORDS


def classify_market(text: str) -> list:
    """
    分析文本，返回关联的市场列表
    一条新闻可能同时关联多个市场（如美联储影响美股和金银）
    """
    if not text:
        return ["其他"]

    markets = []
    text_lower = text.lower()

    for market, keywords in MARKET_KEYWORDS.items():
        for kw in keywords:
            if kw in text or kw.lower() in text_lower:
                markets.append(market)
                break  # 一个关键词命中即可归入该市场

    if not markets:
        markets.append("其他")

    return markets