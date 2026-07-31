# ============================================================
# 新闻数据模型 - 所有爬虫返回的统一格式
# ============================================================

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class NewsItem:
    """单条新闻的统一数据结构"""
    title: str                          # 标题
    content: str                        # 正文内容
    source: str                         # 数据来源（东方财富/财联社/金十数据）
    url: str = ""                       # 原文链接
    publish_time: str = ""              # 发布时间（格式: YYYY-MM-DD HH:MM:SS）
    # 以下字段在第3关分析时填充
    markets: List[str] = field(default_factory=list)      # 关联市场
    sentiment: str = "中性"              # 情绪：利好/利空/中性
    impact_level: str = "低"            # 影响程度：高/中/低
    affected_sectors: List[str] = field(default_factory=list)  # 受影响板块
    # 大模型深度分析字段（可选）
    llm_analysis: str = ""              # 大模型影响分析
    llm_prediction: str = ""            # 大模型走势预测
    llm_suggestion: str = ""            # 大模型操作建议
    llm_confidence: float = 0.0         # 大模型置信度

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        market_str = "/".join(self.markets) if self.markets else "未分类"
        return f"[{self.source}] [{market_str}] [{self.sentiment}] {self.title[:40]}..."


def news_list_to_dicts(news_list: List[NewsItem]) -> List[dict]:
    """将新闻列表转为字典列表"""
    return [n.to_dict() for n in news_list]