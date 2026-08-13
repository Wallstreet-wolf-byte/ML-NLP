# ============================================================
# 资金流数据采集客户端
# 采集北向/南向资金、ETF 持仓变化
# 数据源：东方财富 push2 API
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from common.models import make_fund_flow_record


EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def _safe_float(val) -> float:
    if val is None or val == "-" or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# 北向资金 (沪股通 + 深股通)
# ---------------------------------------------------------------------------

def fetch_northbound_flow() -> Optional[Dict[str, Any]]:
    """获取当日北向资金流向。"""
    try:
        url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54",
            "klt": "101",
            "lmt": "1",
            "secid": "1.000008",  # 北向资金整体
        }
        resp = requests.get(url, params=params, headers=EASTMONEY_HEADERS, timeout=8)
        data = resp.json().get("data", {})
        klines = data.get("klines", [])
        if not klines:
            return None

        # 最新一条: 日期,买额,卖额,净额
        parts = klines[-1].split(",")
        if len(parts) < 4:
            return None

        buy_amount = _safe_float(parts[1])
        sell_amount = _safe_float(parts[2])
        net_amount = _safe_float(parts[3])

        return make_fund_flow_record(
            symbol="NORTHBOUND",
            name="北向资金",
            market="A股",
            flow_type="northbound",
            net_amount=net_amount,
            position_change=net_amount,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="东方财富",
            data_source="东方财富北向资金API",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 南向资金 (港股通)
# ---------------------------------------------------------------------------

def fetch_southbound_flow() -> Optional[Dict[str, Any]]:
    """获取当日南向资金（港股通）流向。"""
    try:
        url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54",
            "klt": "101",
            "lmt": "1",
            "secid": "1.000009",  # 南向资金整体
        }
        resp = requests.get(url, params=params, headers=EASTMONEY_HEADERS, timeout=8)
        data = resp.json().get("data", {})
        klines = data.get("klines", [])
        if not klines:
            return None

        parts = klines[-1].split(",")
        if len(parts) < 4:
            return None

        buy_amount = _safe_float(parts[1])
        sell_amount = _safe_float(parts[2])
        net_amount = _safe_float(parts[3])

        return make_fund_flow_record(
            symbol="SOUTHBOUND",
            name="南向资金（港股通）",
            market="港股",
            flow_type="southbound",
            net_amount=net_amount,
            position_change=net_amount,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="东方财富",
            data_source="东方财富南向资金API",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ETF 持仓 (GLD / SLV)
# ---------------------------------------------------------------------------

def fetch_etf_holding(symbol: str, name: str, market: str = "全球",
                      secid_eastmoney: str = "") -> Optional[Dict[str, Any]]:
    """
    获取 ETF 实时行情（用作持仓变化观测）。
    东方财富国际 ETF 接口。
    """
    try:
        if not secid_eastmoney:
            return None

        params = {
            "secid": secid_eastmoney,
            "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170",
            "fltt": "2",
        }
        resp = requests.get(
            "http://push2.eastmoney.com/api/qt/stock/get",
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            },
            timeout=8,
        )
        d = resp.json().get("data", {})
        if not d or d.get("f43") in (None, "-"):
            return None

        latest = _safe_float(d.get("f43"))
        prev_close = _safe_float(d.get("f60"))
        change = _safe_float(d.get("f169"))
        change_pct = _safe_float(d.get("f170"))

        if change == 0 and latest > 0 and prev_close > 0:
            change = latest - prev_close
        if change_pct == 0 and prev_close > 0:
            change_pct = round((change / prev_close) * 100, 2)

        return make_fund_flow_record(
            symbol=symbol,
            name=name,
            market=market,
            flow_type="etf_holding",
            net_amount=change,
            position_change=change,
            position_change_pct=change_pct,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source="东方财富",
            data_source="东方财富ETF行情",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 统一采集入口
# ---------------------------------------------------------------------------

def fetch_all_fund_flows(etf_configs: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    采集全部启用的资金流数据。

    参数:
        etf_configs: ETF 持仓监控配置列表，每项含 symbol/name/secid_eastmoney

    返回:
        List[Dict] 资金流记录列表
    """
    records: List[Dict[str, Any]] = []

    # 北向资金
    nb = fetch_northbound_flow()
    if nb:
        records.append(nb)

    # 南向资金
    sb = fetch_southbound_flow()
    if sb:
        records.append(sb)

    # ETF 持仓
    if etf_configs:
        for cfg in etf_configs:
            etf = fetch_etf_holding(
                symbol=cfg.get("symbol", ""),
                name=cfg.get("name", ""),
                market=cfg.get("market", "全球"),
                secid_eastmoney=cfg.get("secid_eastmoney", ""),
            )
            if etf:
                records.append(etf)

    return records
