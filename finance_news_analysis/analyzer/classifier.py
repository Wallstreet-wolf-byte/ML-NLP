# ============================================================
# 多维分类器（升级版）
# 按市场 / 品种大类 / 地域 / 板块 / 数据维度 进行多标签分类
# ============================================================

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MARKET_KEYWORDS


# ---------------------------------------------------------------------------
# 品种大类分类关键词
# ---------------------------------------------------------------------------

ASSET_CLASS_KEYWORDS = {
    "股票": ["A股", "股票", "个股", "涨停", "跌停", "主板", "创业板", "科创板", "北交所",
            "港股通", "沪深", "股东", "高送转"],
    "期货": ["期货", "主力合约", "近月", "远月", "交割", "保证金", "多空", "开仓", "平仓",
            "COMEX", "NYMEX", "CBOT", "LME", "ICE", "SHFE", "DCE", "CZCE"],
    "现货": ["现货", "伦敦金", "伦敦银", "XAU", "XAG", "实物", "金条", "金锭", "银锭"],
    "外汇": ["美元指数", "DXY", "汇率", "人民币", "CNH", "CNY", "欧元", "日元", "英镑",
            "美联储", "央行", "加息", "降息", "利率决议"],
    "债券": ["国债", "美债", "收益率", "YTM", "信用债", "可转债", "利率债", "TIPS"],
    "指数": ["指数", "大盘", "上证", "深证", "恒生", "道琼斯", "纳斯达克", "标普",
            "日经", "KOSPI", "VIX"],
    "加密货币": ["比特币", "以太坊", "BTC", "ETH", "加密货币", "区块链", "狗狗币", "USDT"],
}


# ---------------------------------------------------------------------------
# 地域分类关键词
# ---------------------------------------------------------------------------

REGION_KEYWORDS = {
    "中国": ["A股", "上证", "深证", "沪深", "北交所", "科创板", "创业板", "国资委",
            "国务院", "央行", "人民银行", "银保监", "证监会", "发改委", "工信部",
            "港股", "恒生", "港交所", "港股通", "香港", "上海", "深圳", "北京"],
    "美国": ["美股", "纳斯达克", "标普", "道琼斯", "美联储", "华尔街", "SEC",
            "美国", "美元", "COMEX", "NYMEX", "FOMC", "拜登", "特朗普"],
    "欧洲": ["欧洲", "欧元区", "欧央行", "ECB", "英国", "伦敦", "LME", "德国",
            "法国", "意大利", "欧元"],
    "亚太": ["日本", "日经", "日元", "韩国", "KOSPI", "台湾", "印度", "澳大利亚",
            "澳洲央行", "东盟"],
    "中东": ["中东", "沙特", "伊朗", "以色列", "阿联酋", "OPEC", "原油", "地缘"],
}


# ---------------------------------------------------------------------------
# 数据维度分类（用于统一分类器）
# ---------------------------------------------------------------------------

def classify_data_type(record: dict) -> str:
    """根据记录结构判断数据维度类型。"""
    dt = record.get("data_type", "")
    if dt:
        return dt
    # 回退判断
    if "symbol" in record and "latest" in record:
        return "market_quote"
    if "flow_type" in record:
        return "fund_flow"
    if "event_name" in record:
        return "macro_event"
    if "indicator_type" in record:
        return "technical_signal"
    if "content" in record:
        return "flash_news"
    return "unknown"


# ---------------------------------------------------------------------------
# 市场分类（保持原有，增加输出格式）
# ---------------------------------------------------------------------------

def classify_market(text: str) -> list:
    """
    分析文本，返回关联的市场列表。
    一条新闻可能同时关联多个市场（如美联储影响美股和金银）。
    返回: List[str] 市场列表
    """
    if not text:
        return ["其他"]

    markets = []
    text_lower = text.lower()

    for market, keywords in MARKET_KEYWORDS.items():
        for kw in keywords:
            if kw in text or kw.lower() in text_lower:
                markets.append(market)
                break

    if not markets:
        markets.append("其他")

    return markets


# ---------------------------------------------------------------------------
# 品种大类分类（新增）
# ---------------------------------------------------------------------------

def classify_asset_class(text: str) -> list:
    """
    分析文本，返回关联的品种大类列表。
    例如: ["期货", "贵金属"] 或 ["股票"] 或 ["外汇", "债券"]
    返回: List[str] 品种大类列表
    """
    if not text:
        return ["其他"]

    classes = []
    for asset_class, keywords in ASSET_CLASS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                classes.append(asset_class)
                break

    if not classes:
        classes.append("其他")

    return classes


# ---------------------------------------------------------------------------
# 地域分类（新增）
# ---------------------------------------------------------------------------

def classify_region(text: str) -> list:
    """
    分析文本，返回关联的地域列表。
    例如: ["美国", "中国"] 或 ["欧洲"] 或 ["中东"]
    返回: List[str] 地域列表
    """
    if not text:
        return ["全球"]

    regions = []
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                regions.append(region)
                break

    if not regions:
        regions.append("全球")

    return regions


# ---------------------------------------------------------------------------
# 统一分类器（新增）
# ---------------------------------------------------------------------------

def classify_text_full(text: str) -> dict:
    """
    对文本进行全维度分类，返回所有标签。
    返回:
    {
        "markets": [...],        # 关联市场
        "asset_classes": [...],  # 品种大类
        "regions": [...],        # 地域
    }
    """
    return {
        "markets": classify_market(text),
        "asset_classes": classify_asset_class(text),
        "regions": classify_region(text),
    }


def matches_filter(record: dict,
                   target_market: str = "all",
                   target_asset_class: str = "all",
                   target_importance: str = "all") -> bool:
    """
    判断一条记录是否匹配筛选条件。

    参数:
        record: 数据记录（dict）
        target_market: 目标市场 (all / A股 / 港股 / 美股 / ...)
        target_asset_class: 目标品种 (all / 期货 / 股票 / ...)
        target_importance: 目标重要度 (all / 高 / 中 / 低)

    返回:
        bool: 是否通过筛选
    """
    if target_market != "all":
        record_market = record.get("market", "")
        # 记录中可能是列表或字符串
        if isinstance(record_market, list):
            if target_market not in record_market:
                return False
        else:
            if record_market != target_market:
                return False

    if target_asset_class != "all":
        record_ac = record.get("asset_class", "")
        if isinstance(record_ac, list):
            if target_asset_class not in record_ac:
                return False
        else:
            if record_ac != target_asset_class:
                return False

    if target_importance != "all":
        record_imp = record.get("importance", "")
        if isinstance(record_imp, list):
            if target_importance not in record_imp:
                return False
        else:
            if record_imp != target_importance:
                return False

    return True


def filter_records(records: list,
                   market: str = "all",
                   asset_class: str = "all",
                   importance: str = "all") -> list:
    """
    对记录列表进行多维筛选。

    参数:
        records: 记录列表
        market: 目标市场 (all / A股 / 港股 / 美股 / 全球)
        asset_class: 目标品种 (all / 期货 / 股票 / 现货 / 外汇 / 债券 / 指数)
        importance: 目标重要度 (all / 高 / 中 / 低)

    返回:
        筛选后的记录列表
    """
    if market == "all" and asset_class == "all" and importance == "all":
        return records

    return [
        r for r in records
        if matches_filter(r, market, asset_class, importance)
    ]
