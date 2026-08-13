# ============================================================
# 通达信 (TDX) 数据客户端
# 通过通达信官方 TdxQuant 本地 HTTP 服务获取行情/K线数据
#
# 前置条件（重要）：
#   - 需在本机运行「支持 TQ 的通达信客户端」
#   - 默认服务地址 http://127.0.0.1:17709/
#   - 服务未开启时所有请求返回空，需如实提示而非编造数据
#
# 数据定位：
#   - 实时行情 / K线：A股、港股、指数、国内期货（沪金 AU / 沪银 AG 等）
#   - 与东方财富互补：东财主外盘，通达信主 A股/港股/国内期货
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


TDX_DEFAULT_BASE_URL = "http://127.0.0.1:17709/"


def _safe_float(val) -> Optional[float]:
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class TdxClient:
    """通达信 TdxQuant 本地 HTTP 服务客户端。"""

    def __init__(self, base_url: str = TDX_DEFAULT_BASE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()
        self._req_id = 0

    def _call(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用 TdxQuant 本地服务。"""
        self._req_id += 1
        body = {"id": self._req_id, "method": method, "params": params}
        try:
            resp = self.session.post(self.base_url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            # 返回结构: {"id": ..., "result": {...}}
            return result.get("result")
        except Exception:
            # 本地服务未开启或不可用
            return None

    # ------------------------------------------------------------------
    # K线数据 (get_market_data)
    # ------------------------------------------------------------------

    def get_market_data(self, stock_list: List[str], period: str = "1d",
                        count: int = 100) -> Dict[str, Dict[str, Any]]:
        """
        获取 K 线数据。

        参数：
            stock_list: 证券代码列表，格式「代码.市场后缀」
                        如 "688318.SH"（A股）、"00700.HK"（港股）、"AU2606.SHF"（沪金期货）
            period: 周期 "1d"(日) "1w"(周) "1m"(月) "1"(分钟) "5" "15" "30" "60"
            count: 返回 K 线数量

        返回：
            {code: {date[], open[], high[], low[], close[], volume[]}}
        """
        result = self._call("get_market_data", {
            "stock_list": stock_list,
            "period": period,
            "count": count,
            "dividend_type": "none",
        })
        if not result:
            return {}
        # result.Value 结构: {code: {Date[], Open[], High[], Low[], Close[], Volume[]}}
        return result.get("Value", {})

    def fetch_daily(self, code: str, period: str = "1d",
                    count: int = 150) -> List[Dict[str, Any]]:
        """
        获取单品种 K 线，标准化为 [{date, open, high, low, close, volume}]。
        """
        raw = self.get_market_data([code], period=period, count=count)
        if not raw or code not in raw:
            return []

        data = raw[code]
        dates = data.get("Date", [])
        opens = data.get("Open", [])
        highs = data.get("High", [])
        lows = data.get("Low", [])
        closes = data.get("Close", [])
        volumes = data.get("Volume", [])

        klines = []
        n = min(len(dates), len(opens), len(highs), len(lows), len(closes))
        for i in range(n):
            klines.append({
                "date": str(dates[i]),
                "open": _safe_float(opens[i]),
                "high": _safe_float(highs[i]),
                "low": _safe_float(lows[i]),
                "close": _safe_float(closes[i]),
                "volume": _safe_float(volumes[i]) if i < len(volumes) else None,
            })
        return klines


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def get_client(base_url: str = TDX_DEFAULT_BASE_URL) -> TdxClient:
    return TdxClient(base_url)


def is_available(base_url: str = TDX_DEFAULT_BASE_URL, timeout: int = 3) -> bool:
    """检测通达信本地服务是否可用。"""
    try:
        resp = requests.post(base_url.rstrip("/") + "/",
                            json={"id": 0, "method": "get_market_data",
                                  "params": {"stock_list": ["000001.SZ"], "period": "1d", "count": 1}},
                            timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False
