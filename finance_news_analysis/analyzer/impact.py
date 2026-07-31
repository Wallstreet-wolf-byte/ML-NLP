# ============================================================
# 影响评估器
# 评估新闻对市场的影响程度（高/中/低）和关联板块
# ============================================================

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.sentiment import analyze_sentiment


# --- 板块关键词映射 ---
SECTOR_KEYWORDS = {
    "半导体": ["半导体", "芯片", "光刻", "封装", "晶圆", "集成电路", "中芯", "台积电", "英伟达"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电", "锂电池", "充电桩", "新能源车", "电动车", "比亚迪", "宁德时代"],
    "医药": ["医药", "医疗", "生物", "疫苗", "创新药", "中药", "医院", "药品", "制药", "医保"],
    "房地产": ["房地产", "楼市", "房价", "土地", "房企", "万科", "融创", "保障房", "公积金"],
    "银行": ["银行", "贷款", "利率", "存款", "信贷", "建行", "工行", "招行", "农行", "中行"],
    "证券": ["证券", "券商", "牛市", "熊市", "融资融券", "开户", "交易量", "成交额"],
    "消费": ["消费", "零售", "白酒", "茅台", "食品", "饮料", "旅游", "餐饮", "电商", "免税"],
    "军工": ["军工", "国防", "导弹", "军备", "航天", "航空", "兵器", "舰船"],
    "科技": ["科技", "人工智能", "AI", "大数据", "云计算", "5G", "6G", "物联网", "算力", "机器人"],
    "能源": ["原油", "石油", "天然气", "煤炭", "石化", "中石油", "中石化", "新能源"],
    "贵金属": ["黄金", "白银", "铂金", "贵金属", "COMEX", "沪金", "沪银"],
    "农业": ["农业", "粮食", "大豆", "猪肉", "生猪", "化肥", "种子", "养殖"],
    "汽车": ["汽车", "整车", "车企", "新能源车", "比亚迪", "特斯拉", "蔚小理"],
    "地产建材": ["水泥", "钢铁", "建材", "玻璃", "铝", "铜"],
}


def assess_impact(text: str, sentiment: str, pos_score: int, neg_score: int,
                  source: str = "") -> tuple:
    """
    评估新闻影响程度和关联板块
    返回: (影响程度, 关联板块列表)
    """
    # --- 影响程度评估 ---
    # 因素1: 情绪强度（命中关键词数）
    emotion_score = pos_score + neg_score

    # 因素2: 来源权重（财联社和金十的快讯通常更重要）
    source_weight = {
        "财联社": 1.5,
        "金十数据": 1.5,
        "东方财富": 1.0,
    }.get(source, 1.0)

    # 综合评分
    total_score = emotion_score * source_weight

    # 因素3: 包含高影响关键词时直接升级
    high_impact_keywords = [
        "降息", "加息", "降准", "美联储", "央行", "国务院",
        "贸易战", "关税", "制裁", "战争", "冲突",
        "退市", "爆仓", "暴跌", "涨停", "崩盘",
        "重大", "紧急", "突发", "重磅",
    ]
    has_high_impact = any(kw in text for kw in high_impact_keywords)
    if has_high_impact:
        total_score += 3

    # 判定影响程度
    if total_score >= 5 or has_high_impact:
        impact_level = "高"
    elif total_score >= 2:
        impact_level = "中"
    else:
        impact_level = "低"

    # --- 关联板块 ---
    sectors = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                sectors.append(sector)
                break

    return (impact_level, sectors)