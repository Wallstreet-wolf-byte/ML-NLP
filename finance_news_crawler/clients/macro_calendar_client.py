# ============================================================
# 宏观经济日历采集客户端
# 采集经济数据发布日历、预期 vs 实际值、冲击评分
# 数据源：东方财富财经日历页面
# ============================================================
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from common.models import make_macro_event


EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# 重要性与权重映射
IMPORTANCE_WEIGHT = {"高": 3, "中": 2, "低": 1}


def _safe_float(val) -> Optional[float]:
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compute_impact_score(expected: Optional[float],
                          actual: Optional[float],
                          importance: str) -> float:
    """计算宏观事件的冲击评分。"""
    if expected is None or actual is None or expected == 0:
        return 0.0

    deviation = abs(actual - expected) / abs(expected)
    weight = IMPORTANCE_WEIGHT.get(importance, 1)
    return round(deviation * weight * 10, 2)  # 放大便于比较


# ---------------------------------------------------------------------------
# 东方财富财经日历
# ---------------------------------------------------------------------------

def fetch_eastmoney_calendar(date_str: str = "") -> List[Dict[str, Any]]:
    """
    从东方财富获取财经日历。

    参数:
        date_str: 日期 YYYY-MM-DD，默认今日

    返回:
        List[Dict] 宏观事件记录列表
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMIC_CALENDAR",
        "columns": "ALL",
        "sortColumns": "PUBLISHDATE",
        "sortTypes": "1",
        "pageSize": "50",
        "pageNumber": "1",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(PUBLISHDATE>=\'{date_str}\')(PUBLISHDATE<=\'{date_str}\')',
    }

    records = []
    try:
        resp = requests.get(url, params=params, headers=EASTMONEY_HEADERS, timeout=10)
        data = resp.json()
        items = data.get("result", {}).get("data", [])
        if not items:
            return records

        for item in items:
            event_name = item.get("EVENT", "")
            country = item.get("COUNTRY", "")
            importance = item.get("IMPORTANCE", "")
            if isinstance(importance, str):
                # 映射: "3" -> "高", "2" -> "中", "1" -> "低"
                imp_map = {"3": "高", "2": "中", "1": "低"}
                importance = imp_map.get(importance, "中")

            expected = _safe_float(item.get("CONSENSUS"))
            actual = _safe_float(item.get("ACTUAL"))
            previous = _safe_float(item.get("PREVIOUS"))

            impact_score = _compute_impact_score(expected, actual, importance)

            records.append(make_macro_event(
                event_name=event_name,
                country=country,
                importance=importance,
                expected=expected,
                actual=actual,
                previous=previous,
                deviation=abs(actual - expected) if (actual and expected) else 0.0,
                impact_score=impact_score,
                release_time=item.get("PUBLISHDATE", datetime.now().strftime("%Y-%m-%d")),
                source="东方财富",
                data_source="东方财富财经日历",
            ))
    except Exception:
        pass

    return records


# ---------------------------------------------------------------------------
# 筛选与汇总
# ---------------------------------------------------------------------------

def fetch_filtered_calendar(importance_filter: List[str] = None,
                            countries: List[str] = None,
                            date_str: str = "") -> List[Dict[str, Any]]:
    """
    采集财经日历并按条件筛选。

    参数:
        importance_filter: 重要性过滤 (["高", "中"])
        countries: 国家/地区过滤 (["美国", "中国"])
        date_str: 日期

    返回:
        筛选后的事件列表
    """
    events = fetch_eastmoney_calendar(date_str)

    if importance_filter:
        events = [e for e in events if e.get("importance") in importance_filter]

    if countries:
        events = [e for e in events if e.get("country") in countries]

    return events


def get_high_impact_events(date_str: str = "") -> List[Dict[str, Any]]:
    """获取当日高影响事件（重要性 ≥ 中）。"""
    return fetch_filtered_calendar(
        importance_filter=["高", "中"],
        date_str=date_str,
    )
