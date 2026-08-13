# ============================================================
# TuShare 数据客户端
# 通过 TuShare Pro HTTP API 获取历史日线数据
# 用于补充东方财富实时行情缺失的历史数据，支撑技术指标真实计算
#
# 覆盖品种（重点金银/恒指）：
#   - 期货日线   (fut_daily):    沪金 AU / 沪银 AG / 沪铜 CU / 原油 SC
#   - 上海黄金现货 (sge_daily):   黄金 T+D / 白银 T+D
#   - 港股日线   (hk_daily):     恒生指数等
#   - 全球指数   (index_global): 恒生指数 / 美元指数等
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


TUSHARE_API_URL = "https://api.tushare.pro"


def _safe_float(val) -> Optional[float]:
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 核心调用
# ---------------------------------------------------------------------------

class TuShareClient:
    """TuShare Pro HTTP API 客户端。"""

    def __init__(self, token: str, timeout: int = 15):
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _call(self, api_name: str, params: Dict[str, Any] = None,
              fields: str = "") -> Optional[Dict[str, Any]]:
        """调用 TuShare Pro 接口，返回 {fields, items} 结构。"""
        if not self.enabled:
            return None

        body = {
            "api_name": api_name,
            "token": self.token,
            "params": params or {},
            "fields": fields,
        }
        try:
            resp = self.session.post(TUSHARE_API_URL, json=body, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                # code 非 0 表示接口错误（如积分不足、无权限）
                return None
            data = result.get("data") or {}
            return data
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 日线获取（统一解析为标准化 K 线）
    # ------------------------------------------------------------------

    def _fetch_daily(self, api_name: str, ts_code: str,
                     start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
        """获取日线并标准化为 [{date, open, high, low, close, volume}]。"""
        params: Dict[str, Any] = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = self._call(api_name, params)
        if not data:
            return []

        fields = data.get("fields", [])
        items = data.get("items", [])
        if not fields or not items:
            return []

        # 建立字段索引
        idx = {name: i for i, name in enumerate(fields)}
        klines = []
        for row in items:
            klines.append({
                "date": str(row[idx.get("trade_date", 0)]),
                "open": _safe_float(row[idx["open"]]) if "open" in idx else None,
                "high": _safe_float(row[idx["high"]]) if "high" in idx else None,
                "low": _safe_float(row[idx["low"]]) if "low" in idx else None,
                "close": _safe_float(row[idx["close"]]) if "close" in idx else None,
                "volume": _safe_float(row[idx["vol"]]) if "vol" in idx else None,
            })
        return klines

    # ------------------------------------------------------------------
    # 具体品种接口
    # ------------------------------------------------------------------

    def fetch_fut_daily(self, ts_code: str,
                        start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
        """期货日线（沪金 AU.SHF / 沪银 AG.SHF / 沪铜 CU.SHF / 原油 SC.INE）。"""
        return self._fetch_daily("fut_daily", ts_code, start_date, end_date)

    def fetch_sge_daily(self, ts_code: str,
                        start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
        """上海黄金现货日线（AU9999.SGE / AG9999.SGE）。"""
        return self._fetch_daily("sge_daily", ts_code, start_date, end_date)

    def fetch_hk_daily(self, ts_code: str,
                       start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
        """港股日线（恒生指数等）。"""
        return self._fetch_daily("hk_daily", ts_code, start_date, end_date)

    def fetch_index_global(self, ts_code: str,
                           start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
        """国际主要指数日线（恒生指数 HSI / 美元指数等）。"""
        return self._fetch_daily("index_global", ts_code, start_date, end_date)


# ---------------------------------------------------------------------------
# 便捷函数：构造客户端
# ---------------------------------------------------------------------------

_client_cache: Dict[str, TuShareClient] = {}


def get_client(token: str = "") -> TuShareClient:
    """获取（缓存的）TuShare 客户端实例。"""
    global _client_cache
    if not token:
        return TuShareClient("")
    if token not in _client_cache:
        _client_cache[token] = TuShareClient(token)
    return _client_cache[token]


def fetch_kline_by_symbol(symbol: str, token: str,
                          start_date: str = "", end_date: str = "") -> List[Dict[str, Any]]:
    """
    按品种 symbol 获取历史日线（简化入口）。

    支持品种映射：
        GC -> 沪金期货 AU.SHF
        SI -> 沪银期货 AG.SHF
        HG -> 沪铜期货 CU.SHF
        CL -> 原油 SC.INE
        HSI -> 恒生指数
        XAUUSD -> 上海黄金现货 AU9999.SGE
        XAGUSD -> 上海白银现货 AG9999.SGE
    """
    client = get_client(token)
    if not client.enabled:
        return []

    # symbol -> (api_name, ts_code)
    mapping = {
        "GC": ("fut_daily", "AU.SHF"),
        "SI": ("fut_daily", "AG.SHF"),
        "HG": ("fut_daily", "CU.SHF"),
        "CL": ("fut_daily", "SC.INE"),
        "HSI": ("index_global", "HSI"),
        "XAUUSD": ("sge_daily", "AU9999.SGE"),
        "XAGUSD": ("sge_daily", "AG9999.SGE"),
    }

    if symbol not in mapping:
        return []

    api_name, ts_code = mapping[symbol]
    return client._fetch_daily(api_name, ts_code, start_date, end_date)
