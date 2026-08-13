# ============================================================
# 大盘指数模块（重构版）
# 从 config.yaml 驱动，覆盖 A股/港股/美股/贵金属/外汇/大宗商品等全品种
# 数据源：东方财富 push2 API → 新浪财经备用
#
# 保持与旧版调用接口兼容: fetch_index_data() / generate_market_summary()
# ============================================================

import sys
import os
from datetime import datetime
from typing import List, Dict

# 尝试从 finance_news_crawler 导入配置
try:
    _crawler_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "finance_news_crawler")
    )
    sys.path.insert(0, _crawler_root)
    from config import MARKET_DATA_CATEGORIES
except ImportError:
    # 回退：使用内置精简配置
    MARKET_DATA_CATEGORIES = {
        "a_share": {
            "label": "A股指数", "enabled": True, "market": "A股", "asset_class": "指数",
            "items": [
                {"symbol": "000016", "secid_eastmoney": "1.000016", "name": "上证50"},
                {"symbol": "000300", "secid_eastmoney": "1.000300", "name": "沪深300"},
                {"symbol": "000905", "secid_eastmoney": "1.000905", "name": "中证500"},
                {"symbol": "000852", "secid_eastmoney": "1.000852", "name": "中证1000"},
            ],
        },
        "us_market": {
            "label": "美股指数", "enabled": True, "market": "美股", "asset_class": "指数",
            "items": [
                {"symbol": "DJIA", "secid_eastmoney": "100.DJIA", "name": "道琼斯"},
                {"symbol": "NDX", "secid_eastmoney": "100.NDX", "name": "纳斯达克"},
                {"symbol": "SPX", "secid_eastmoney": "100.SPX", "name": "标普500"},
            ],
        },
    }

try:
    from clients.market_data_client import (
        fetch_all_quotes,
        fetch_quotes_by_market,
        fetch_quotes_by_asset_class,
        fetch_quotes_by_symbols,
    )
    _use_client = True
except ImportError:
    _use_client = False


# ============================================================
# 公开 API：获取指数实时行情（保持旧版兼容）
# ============================================================

def fetch_index_data(market_filter: str = "all") -> Dict:
    """
    获取指数实时行情。
    market_filter: all / A股 / 港股 / 美股 / 全球
    保持与旧版 fetch_index_data() 兼容的返回格式。
    """
    if _use_client:
        if market_filter != "all":
            records = fetch_quotes_by_market(MARKET_DATA_CATEGORIES, market_filter)
        else:
            records = fetch_all_quotes(MARKET_DATA_CATEGORIES)
    else:
        records = _legacy_fetch()

    # 转换为旧版兼容格式
    indices_result = []
    for r in records:
        indices_result.append({
            "secid": r.get("symbol", ""),
            "code": r.get("symbol", ""),
            "name": r.get("name", ""),
            "market": r.get("market", ""),
            "group": r.get("asset_class", ""),
            "latest": r.get("latest", 0),
            "prev_close": r.get("prev_close", 0),
            "change": r.get("change", 0),
            "change_pct": r.get("change_pct", 0),
            "high": r.get("high", 0),
            "low": r.get("low", 0),
            "open": r.get("open", 0),
            "volume": r.get("volume", 0),
            "amount": r.get("amount", 0),
            "data_source": r.get("source", "未知"),
        })

    return {
        "indices": indices_result,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "东方财富/新浪财经",
        "total": len(indices_result),
    }


# ============================================================
# 新增 API：按条件筛选行情
# ============================================================

def fetch_by_asset_class(asset_class: str) -> Dict:
    """按品种大类获取行情（期货/现货/外汇/债券/指数/股票）。"""
    if not _use_client:
        return {"indices": [], "fetch_time": "", "source": "", "total": 0}

    records = fetch_quotes_by_asset_class(MARKET_DATA_CATEGORIES, asset_class)
    indices_result = _records_to_indices(records)
    return {
        "indices": indices_result,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "东方财富/新浪财经",
        "total": len(indices_result),
    }


def fetch_by_symbols(symbols: List[str]) -> Dict:
    """按品种代码获取行情（如 ["GC", "SI", "HSI"]）。"""
    if not _use_client:
        return {"indices": [], "fetch_time": "", "source": "", "total": 0}

    records = fetch_quotes_by_symbols(MARKET_DATA_CATEGORIES, symbols)
    indices_result = _records_to_indices(records)
    return {
        "indices": indices_result,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "东方财富/新浪财经",
        "total": len(indices_result),
    }


def _records_to_indices(records: List[Dict]) -> List[Dict]:
    """将行情记录转换为旧版兼容格式。"""
    return [{
        "secid": r.get("symbol", ""),
        "code": r.get("symbol", ""),
        "name": r.get("name", ""),
        "market": r.get("market", ""),
        "group": r.get("asset_class", ""),
        "latest": r.get("latest", 0),
        "prev_close": r.get("prev_close", 0),
        "change": r.get("change", 0),
        "change_pct": r.get("change_pct", 0),
        "high": r.get("high", 0),
        "low": r.get("low", 0),
        "open": r.get("open", 0),
        "volume": r.get("volume", 0),
        "amount": r.get("amount", 0),
        "data_source": r.get("source", "未知"),
    } for r in records]


# ============================================================
# 旧版兼容：简单版本（无 market_data_client 时使用）
# ============================================================

def _legacy_fetch() -> List[Dict]:
    """旧版简易获取逻辑（备用）。"""
    import requests
    import random

    records = []
    for cat_key, cat_meta in MARKET_DATA_CATEGORIES.items():
        if not cat_meta.get("enabled", True):
            continue
        for item in cat_meta.get("items", []):
            secid = item.get("secid_eastmoney", "")
            if not secid:
                continue
            try:
                params = {
                    "secid": secid,
                    "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170",
                    "fltt": "2",
                }
                resp = requests.get(
                    "http://push2.eastmoney.com/api/qt/stock/get",
                    params=params,
                    headers={"User-Agent": "Mozilla/5.0",
                             "Referer": "https://quote.eastmoney.com/"},
                    timeout=8,
                )
                d = resp.json().get("data", {})
                if d and d.get("f43") not in (None, "-"):
                    latest = float(d.get("f43", 0))
                    prev_close = float(d.get("f60", 0))
                    change = float(d.get("f169", 0))
                    change_pct = float(d.get("f170", 0))
                    if change == 0 and latest > 0 and prev_close > 0:
                        change = latest - prev_close
                    if change_pct == 0 and prev_close > 0:
                        change_pct = round((change / prev_close) * 100, 2)

                    records.append({
                        "symbol": item["symbol"],
                        "name": item["name"],
                        "latest": latest,
                        "prev_close": prev_close,
                        "change": change,
                        "change_pct": change_pct,
                        "high": float(d.get("f44", 0)),
                        "low": float(d.get("f45", 0)),
                        "open": float(d.get("f46", 0)),
                        "volume": float(d.get("f47", 0)),
                        "amount": float(d.get("f48", 0)),
                        "market": cat_meta.get("market", ""),
                        "asset_class": cat_meta.get("asset_class", ""),
                        "source": "东方财富实时",
                    })
            except Exception:
                pass
    return records


# ============================================================
# 大盘综合研判（保持旧版兼容）
# ============================================================

def generate_market_summary(indices: List[dict]) -> dict:
    """
    根据指数涨跌情况生成大盘综合研判。
    保持与旧版完全兼容的接口。
    """
    if not indices:
        return {"summary": "暂无指数数据", "a_share_trend": "未知", "us_trend": "未知"}

    # 按市场分组
    grouped: Dict[str, List] = {}
    for i in indices:
        mkt = i.get("market", i.get("group", "未知"))
        grouped.setdefault(mkt, []).append(i)

    def _trend(group):
        if not group:
            return "未知"
        up = sum(1 for i in group if i.get("change_pct", 0) > 0)
        down = sum(1 for i in group if i.get("change_pct", 0) < 0)
        avg_pct = sum(i.get("change_pct", 0) for i in group) / len(group)
        if up > down and avg_pct > 0.5:
            return "偏强"
        elif down > up and avg_pct < -0.5:
            return "偏弱"
        else:
            return "震荡"

    parts = []
    for mkt_name, group in grouped.items():
        trend = _trend(group)
        pct_str = ", ".join(
            f"{i.get('name', '?')} {i.get('change_pct', 0):+.2f}%" for i in group
        )
        parts.append(f"{mkt_name}方面：{pct_str}，整体{trend}")

    summary = "；".join(parts) + "。"

    a_trend = _trend(grouped.get("A股", []))
    us_trend = _trend(grouped.get("美股", []))

    return {
        "summary": summary,
        "a_share_trend": a_trend,
        "us_trend": us_trend,
    }
