# ============================================================
# 品种实体匹配器
# 建立统一的「品种 symbol → 关键词」映射，用于给文本/数据打品种标签。
#
# 设计原则（满足用户核心需求）：
#   1. 可重叠：一条文本/数据可同时命中多个品种
#   2. 不遗漏：针对某一品种，直接相关词 + 宏观驱动词都要能命中
# ============================================================
from __future__ import annotations

from typing import Dict, List


# ---------------------------------------------------------------------------
# 品种实体定义
# 每个品种包含：中文名、市场、品种大类、直接相关关键词
# ---------------------------------------------------------------------------

SYMBOL_ENTITIES: Dict[str, Dict] = {
    # --- 贵金属 ---
    "GC": {
        "name": "黄金",
        "market": "全球",
        "asset_class": "期货",
        "keywords": [
            "黄金", "金价", "金矿", "金饰", "金条", "黄金股", "黄金期货",
            "COMEX黄金", "沪金", "现货黄金", "伦敦金", "国际金价", "金价走势",
            "XAU", "黄金ETF", "金股",
        ],
    },
    "SI": {
        "name": "白银",
        "market": "全球",
        "asset_class": "期货",
        "keywords": [
            "白银", "银价", "银矿", "白银股", "白银期货",
            "COMEX白银", "沪银", "现货白银", "伦敦银", "国际银价",
            "XAG", "白银ETF",
        ],
    },

    # --- 港股 / 恒指 ---
    "HSI": {
        "name": "恒生指数",
        "market": "港股",
        "asset_class": "指数",
        "keywords": [
            "恒指", "恒生", "恒生指数", "港股", "港交所", "港股通", "H股",
            "香港股市", "香港", "国企指数", "红筹股", "恒生科技",
            "HSI", "HSCEI", "HSTECH", "恒生中国企业",
        ],
    },

    # --- 美股 ---
    "SPX": {
        "name": "美股",
        "market": "美股",
        "asset_class": "指数",
        "keywords": [
            "美股", "标普", "标普500", "纳斯达克", "纳指", "道琼斯", "道指",
            "华尔街", "美三大股指", "纳指期货", "标普期货", "道指期货",
            "S&P500", "S&P", "纳斯达克指数",
        ],
    },

    # --- 外汇 / 美元 ---
    "DXY": {
        "name": "美元指数",
        "market": "全球",
        "asset_class": "外汇",
        "keywords": [
            "美元指数", "美指", "美元汇率", "美元指数DXY", "离岸人民币",
            "人民币汇率", "在岸人民币", "人民币", "USDCNH", "USDCNY",
            "DXY", "美元兑",
        ],
    },

    # --- 债券 / 利率 ---
    "US10Y": {
        "name": "美债收益率",
        "market": "全球",
        "asset_class": "债券",
        "keywords": [
            "美债", "国债收益率", "美债收益率", "10年期美债", "10年美债",
            "2年期美债", "实际利率", "TIPS", "美债利率", "债券收益率",
            "美国国债", "收益率曲线",
        ],
    },

    # --- 大宗商品 ---
    "CL": {
        "name": "原油",
        "market": "全球",
        "asset_class": "期货",
        "keywords": [
            "原油", "油价", "石油", "WTI", "布伦特", "OPEC", "美油", "布油",
            "原油期货", "国际油价", "成品油",
        ],
    },
    "HG": {
        "name": "铜",
        "market": "全球",
        "asset_class": "期货",
        "keywords": [
            "铜", "铜价", "铜矿", "伦铜", "沪铜", "COMEX铜", "国际铜",
            "铜期货", "精炼铜",
        ],
    },

    # --- 波动率 ---
    "VIX": {
        "name": "恐慌指数",
        "market": "全球",
        "asset_class": "指数",
        "keywords": [
            "VIX", "恐慌指数", "波动率指数", "恐慌情绪", "避险情绪",
            "VHSI", "恒指波幅", "波动率",
        ],
    },

    # --- 加密货币 ---
    "BTC": {
        "name": "比特币",
        "market": "全球",
        "asset_class": "加密货币",
        "keywords": [
            "比特币", "以太坊", "加密货币", "数字货币", "区块链", "虚拟货币",
            "BTC", "ETH", "狗狗币",
        ],
    },

    # --- A股 ---
    "ASHARE": {
        "name": "A股大盘",
        "market": "A股",
        "asset_class": "指数",
        "keywords": [
            "A股", "上证", "深证", "沪深", "创业板", "科创板", "北交所",
            "上证指数", "沪深300", "中证500", "中证1000", "沪指", "深成指",
        ],
    },
}


# ---------------------------------------------------------------------------
# 宏观驱动词 → 受影响的品种列表
# 这些词本身不一定点名某品种，但对这些品种有重大影响。
# 例如「美联储降息」虽未提黄金，但对黄金/白银/美股/美元/美债都有关键影响。
# ---------------------------------------------------------------------------

DRIVER_KEYWORDS: Dict[str, List[str]] = {
    "美联储": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "加息": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "降息": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "FOMC": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "利率决议": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "缩表": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "非农": ["GC", "SI", "HSI", "SPX", "DXY"],
    "CPI": ["GC", "SI", "HSI", "SPX", "DXY", "US10Y"],
    "通胀": ["GC", "SI", "SPX", "DXY", "US10Y"],
    "PCE": ["GC", "SI", "SPX", "DXY", "US10Y"],
    "避险": ["GC", "SI", "US10Y", "VIX"],
    "地缘": ["GC", "SI", "CL", "VIX"],
    "战争": ["GC", "SI", "CL", "VIX"],
    "制裁": ["GC", "SI", "CL", "VIX"],
    # 注意：不使用单字「美元」，避免误匹配价格单位（如「70美元」）。
    # 仅用「美元指数/美元走强走弱」等精确短语。
    "美元走强": ["GC", "SI", "HSI", "CL"],
    "美元走弱": ["GC", "SI", "HSI", "CL"],
    "美元贬值": ["GC", "SI", "HSI", "CL"],
    "美元升值": ["GC", "SI", "HSI", "CL"],
    "强美元": ["GC", "SI", "HSI", "CL"],
    "弱美元": ["GC", "SI", "HSI", "CL"],
    "实际利率": ["GC", "SI", "US10Y"],
}


# ---------------------------------------------------------------------------
# 匹配逻辑
# ---------------------------------------------------------------------------

def match_symbols(text: str) -> List[str]:
    """
    对文本进行品种匹配，返回命中的品种 symbol 列表（去重）。
    支持重叠：一条文本可同时命中多个品种。
    """
    if not text:
        return []

    text_lower = text.lower()
    matched: List[str] = []

    # 1. 直接关键词匹配
    for symbol, entity in SYMBOL_ENTITIES.items():
        for kw in entity.get("keywords", []):
            if kw.lower() in text_lower:
                matched.append(symbol)
                break  # 该品种命中一个词即可

    # 2. 宏观驱动词匹配
    for driver_kw, symbols in DRIVER_KEYWORDS.items():
        if driver_kw.lower() in text_lower:
            for sym in symbols:
                if sym not in matched:
                    matched.append(sym)

    return matched


def get_entity(symbol: str) -> Dict:
    """获取品种实体信息（含 name/market/asset_class）。"""
    return SYMBOL_ENTITIES.get(symbol, {})


def get_entity_name(symbol: str) -> str:
    """获取品种中文名。"""
    return SYMBOL_ENTITIES.get(symbol, {}).get("name", symbol)


def get_all_symbols() -> List[str]:
    """返回所有品种 symbol 列表。"""
    return list(SYMBOL_ENTITIES.keys())


def get_symbols_by_market(market: str) -> List[str]:
    """返回指定市场的所有品种 symbol。"""
    return [s for s, e in SYMBOL_ENTITIES.items() if e.get("market") == market]


def get_symbols_by_asset_class(asset_class: str) -> List[str]:
    """返回指定品种大类的所有品种 symbol。"""
    return [s for s, e in SYMBOL_ENTITIES.items() if e.get("asset_class") == asset_class]


# ---------------------------------------------------------------------------
# 记录打标 & 统一筛选
# ---------------------------------------------------------------------------

def tag_record(record: Dict) -> Dict:
    """
    给记录打品种标签（用于快讯等未打标的文本记录）。

    逻辑：
      - 对 title+content 做品种匹配，得到 symbols
      - 由 symbols 推导 market / asset_class（允许重叠，多标签）
      - 已带 symbol/market/asset_class 字段的记录原样返回（行情/资金/技术已有标签）

    返回：打标后的记录（原地修改并返回）
    """
    # 已打标的记录直接返回
    if record.get("symbol") or record.get("data_type") in ("market_quote", "fund_flow", "technical_signal"):
        return record

    text = " ".join(str(record.get(k, "")) for k in ("title", "content"))
    symbols = match_symbols(text)

    if symbols:
        markets = []
        asset_classes = []
        for sym in symbols:
            entity = SYMBOL_ENTITIES.get(sym, {})
            if entity.get("market") and entity["market"] not in markets:
                markets.append(entity["market"])
            if entity.get("asset_class") and entity["asset_class"] not in asset_classes:
                asset_classes.append(entity["asset_class"])

        record["symbol"] = symbols
        record["market"] = markets if markets else [""]
        record["asset_class"] = asset_classes if asset_classes else [""]
    else:
        record["symbol"] = []
        record["market"] = ["其他"]
        record["asset_class"] = ["其他"]

    return record


def _record_has_value(record: Dict, field: str, target) -> bool:
    """判断记录的某字段是否命中目标值（兼容字符串和列表）。"""
    val = record.get(field, "")
    if isinstance(val, list):
        return target in val
    return str(val) == str(target)


def _record_has_any_symbol(record: Dict, target_symbols: List[str]) -> bool:
    """判断记录的 symbol 字段是否命中任一目标品种（支持列表交集）。"""
    val = record.get("symbol", "")
    if isinstance(val, list):
        return bool(set(val) & set(target_symbols))
    return val in target_symbols


def filter_records_by_criteria(records: List[Dict],
                               market: str = "all",
                               asset_class: str = "all",
                               symbols: List[str] = None) -> List[Dict]:
    """
    统一筛选记录列表（宽匹配，支持重叠，不遗漏）。

    参数：
        records: 记录列表
        market: 目标市场 (all / A股 / 港股 / 美股 / 全球 / 亚太)
        asset_class: 目标品种大类 (all / 期货 / 现货 / 外汇 / 债券 / 指数 / 股票)
        symbols: 目标品种 symbol 列表（如 ["GC", "SI"]），None 表示不按品种过滤

    返回：筛选后的记录列表
    """
    result = list(records)

    if symbols:
        result = [r for r in result if _record_has_any_symbol(r, symbols)]

    if market and market != "all":
        result = [r for r in result if _record_has_value(r, "market", market)]

    if asset_class and asset_class != "all":
        result = [r for r in result if _record_has_value(r, "asset_class", asset_class)]

    return result
