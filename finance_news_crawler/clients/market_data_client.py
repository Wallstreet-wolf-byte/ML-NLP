# ============================================================
# 行情数据采集客户端
# 从东方财富 push2 + 新浪财经获取全品种实时行情
# 数据源优先级: eastmoney > sina
# ============================================================
from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from common.models import make_quote_snapshot

# ---------------------------------------------------------------------------
# 东方财富 push2 API 基础
# ---------------------------------------------------------------------------

EASTMONEY_PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
# 东方财富 push2 接口必要参数（外盘期货必须携带，否则被拒）
EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
EASTMONEY_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"

SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.sina.com.cn",
}


def _safe_float(val) -> float:
    """安全转换为 float。"""
    if val is None or val == "-" or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# 东方财富数据获取
# ---------------------------------------------------------------------------

def _fetch_eastmoney(secid: str, retries: int = 3) -> Optional[Dict[str, Any]]:
    """从东方财富 push2 获取单品种行情（带重试，规避限流）。"""
    params = {
        "secid": secid,
        "fields": EASTMONEY_FIELDS,
        "fltt": "2",
        "ut": EASTMONEY_UT,
    }

    for attempt in range(retries):
        try:
            resp = requests.get(EASTMONEY_PUSH2_URL, params=params,
                               headers=EASTMONEY_HEADERS, timeout=8)
            resp.raise_for_status()
            body = resp.json()
            d = body.get("data", {})

            if not d or d.get("f43") is None or d.get("f43") == "-":
                return None

            latest = _safe_float(d.get("f43"))
            prev_close = _safe_float(d.get("f60"))
            change = _safe_float(d.get("f169"))
            change_pct = _safe_float(d.get("f170"))

            if change == 0 and latest > 0 and prev_close > 0:
                change = latest - prev_close
            if change_pct == 0 and prev_close > 0:
                change_pct = round((change / prev_close) * 100, 2)

            return {
                "latest": latest,
                "prev_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "high": _safe_float(d.get("f44")),
                "low": _safe_float(d.get("f45")),
                "open": _safe_float(d.get("f46")),
                "volume": _safe_float(d.get("f47")),
                "amount": _safe_float(d.get("f48")),
            }
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# 新浪财经备用源
# ---------------------------------------------------------------------------

def _fetch_sina(sina_code: str) -> Optional[Dict[str, Any]]:
    """从新浪财经获取单品种行情。"""
    try:
        url = f"http://hq.sinajs.cn/list={sina_code}"
        resp = requests.get(url, headers=SINA_HEADERS, timeout=8)
        resp.encoding = "gbk"
        text = resp.text.strip()

        if '="' not in text:
            return None

        content = text.split('="')[1].rstrip('";')
        fields = content.split(",")
        if len(fields) < 4:
            return None

        latest = _safe_float(fields[1])
        change = _safe_float(fields[2])
        change_pct = _safe_float(fields[3])
        prev_close = _safe_float(fields[8]) if len(fields) > 8 else (latest - change)
        open_price = _safe_float(fields[9]) if len(fields) > 9 else 0
        high = _safe_float(fields[10]) if len(fields) > 10 else 0
        low = _safe_float(fields[11]) if len(fields) > 11 else 0

        if latest == 0:
            return None

        return {
            "latest": latest,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "high": high,
            "low": low,
            "open": open_price,
            "volume": 0,
            "amount": 0,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 主采集逻辑
# ---------------------------------------------------------------------------

def _fetch_single_item(item: Dict[str, str], category_meta: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """获取单个品种行情，按优先级尝试数据源。"""
    result = None
    data_source = ""

    # 1. 东方财富
    secid = item.get("secid_eastmoney", "")
    if secid:
        result = _fetch_eastmoney(secid)
        data_source = "东方财富实时"

    # 2. 新浪备用
    if result is None:
        sina_code = item.get("secid_sina", "")
        if sina_code:
            result = _fetch_sina(sina_code)
            data_source = "新浪财经实时"

    # 3. 失败返回 None
    if result is None:
        return None

    return make_quote_snapshot(
        symbol=item.get("symbol", ""),
        name=item.get("name", ""),
        market=category_meta.get("market", ""),
        asset_class=category_meta.get("asset_class", ""),
        latest=result["latest"],
        prev_close=result["prev_close"],
        change=result["change"],
        change_pct=result["change_pct"],
        high=result["high"],
        low=result["low"],
        open=result["open"],
        volume=result["volume"],
        amount=result["amount"],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        source=data_source,
        data_source=data_source,
    )


def fetch_all_quotes(categories: Dict[str, Any] = None,
                     enabled_only: bool = True) -> List[Dict[str, Any]]:
    """
    采集所有启用品种的实时行情。

    参数:
        categories: 品种分类配置 dict（从 MARKET_DATA_CATEGORIES 传入）
        enabled_only: 仅采集 enabled=true 的分类

    返回:
        List[Dict] 行情快照记录列表
    """
    if categories is None:
        return []

    records: List[Dict[str, Any]] = []

    for cat_key, cat_meta in categories.items():
        if enabled_only and not cat_meta.get("enabled", True):
            continue

        items = cat_meta.get("items", [])
        cat_label = cat_meta.get("label", cat_key)

        for item in items:
            try:
                record = _fetch_single_item(item, cat_meta)
                if record:
                    records.append(record)
            except Exception:
                pass
            # 每个品种之间稍作等待，避免触发东方财富限流
            time.sleep(0.5)

    return records


def fetch_quotes_by_market(categories: Dict[str, Any],
                           target_market: str = "all") -> List[Dict[str, Any]]:
    """按目标市场筛选后采集行情。"""
    if target_market == "all":
        return fetch_all_quotes(categories)

    # 筛选出目标市场的分类
    filtered: Dict[str, Any] = {}
    for cat_key, cat_meta in categories.items():
        if cat_meta.get("market", "") == target_market:
            filtered[cat_key] = cat_meta

    return fetch_all_quotes(filtered)


def fetch_quotes_by_asset_class(categories: Dict[str, Any],
                                 target_class: str = "all") -> List[Dict[str, Any]]:
    """按品种大类筛选后采集行情。"""
    if target_class == "all":
        return fetch_all_quotes(categories)

    filtered: Dict[str, Any] = {}
    for cat_key, cat_meta in categories.items():
        if cat_meta.get("asset_class", "") == target_class:
            filtered[cat_key] = cat_meta

    return fetch_all_quotes(filtered)


def fetch_quotes_by_symbols(categories: Dict[str, Any],
                            symbols: List[str]) -> List[Dict[str, Any]]:
    """按指定品种代码采集行情。"""
    if not symbols:
        return []

    symbol_set = set(symbols)
    records: List[Dict[str, Any]] = []

    for cat_key, cat_meta in categories.items():
        if not cat_meta.get("enabled", True):
            continue
        for item in cat_meta.get("items", []):
            if item.get("symbol", "") in symbol_set:
                try:
                    record = _fetch_single_item(item, cat_meta)
                    if record:
                        records.append(record)
                except Exception:
                    pass
                time.sleep(0.3)

    return records


# ---------------------------------------------------------------------------
# 便捷函数：获取完整行情汇总
# ---------------------------------------------------------------------------

def get_market_summary(categories: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取行情汇总，包含所有品种数据和分类统计。

    返回:
    {
        "records": [...],       # 所有行情记录
        "fetch_time": "...",    # 采集时间
        "summary": {...},       # 分市场汇总
        "total": int,           # 总数
    }
    """
    records = fetch_all_quotes(categories)

    # 分市场汇总
    by_market: Dict[str, List[Dict]] = {}
    for r in records:
        mkt = r.get("market", "未知")
        by_market.setdefault(mkt, []).append(r)

    # 各市场涨跌统计
    market_stats = {}
    for mkt, items in by_market.items():
        up = sum(1 for i in items if i.get("change_pct", 0) > 0)
        down = sum(1 for i in items if i.get("change_pct", 0) < 0)
        avg_pct = sum(i.get("change_pct", 0) for i in items) / max(len(items), 1)
        market_stats[mkt] = {
            "total": len(items),
            "up": up,
            "down": down,
            "avg_change_pct": round(avg_pct, 2),
            "trend": "偏强" if avg_pct > 0.5 else ("偏弱" if avg_pct < -0.5 else "震荡"),
        }

    return {
        "records": records,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": market_stats,
        "total": len(records),
    }
