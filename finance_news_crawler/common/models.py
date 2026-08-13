from __future__ import annotations

from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# 快讯模型 (现有)
# ---------------------------------------------------------------------------

NEWS_FIELDS = (
    "id",
    "title",
    "content",
    "publish_time",
    "source",
    "data_source",
    "data_frequency",
)


def make_news_record(
    *,
    news_id: str,
    title: str,
    content: str,
    publish_time: str,
    source: str,
    data_source: str,
    data_frequency: str,
) -> Dict[str, str]:
    return {
        "id": str(news_id or ""),
        "title": str(title or ""),
        "content": str(content or ""),
        "publish_time": str(publish_time or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
        "data_frequency": str(data_frequency or ""),
    }


def normalize_record(record: Dict[str, Any]) -> Dict[str, str]:
    return {field: str(record.get(field) or "") for field in NEWS_FIELDS}


# ---------------------------------------------------------------------------
# 行情快照模型 (新增)
# ---------------------------------------------------------------------------

def make_quote_snapshot(
    *,
    symbol: str,
    name: str = "",
    market: str = "",
    asset_class: str = "",
    latest: float = 0.0,
    prev_close: float = 0.0,
    change: float = 0.0,
    change_pct: float = 0.0,
    high: float = 0.0,
    low: float = 0.0,
    open: float = 0.0,
    volume: float = 0.0,
    amount: float = 0.0,
    timestamp: str = "",
    source: str = "",
    data_source: str = "",
) -> Dict[str, Any]:
    """构造统一的行情快照记录。

    分类标签:
        market:     A股 / 港股 / 美股 / 全球 / 亚太
        asset_class: 股票 / 期货 / 现货 / 外汇 / 债券 / 指数 / 加密货币
    """
    return {
        "id": f"quote_{symbol}_{timestamp}",
        "data_type": "market_quote",
        "symbol": str(symbol or ""),
        "name": str(name or ""),
        "market": str(market or ""),
        "asset_class": str(asset_class or ""),
        "latest": float(latest),
        "prev_close": float(prev_close),
        "change": float(change),
        "change_pct": float(change_pct),
        "high": float(high),
        "low": float(low),
        "open": float(open),
        "volume": float(volume),
        "amount": float(amount),
        "timestamp": str(timestamp or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
    }


# ---------------------------------------------------------------------------
# 资金流模型 (新增)
# ---------------------------------------------------------------------------

def make_fund_flow_record(
    *,
    symbol: str = "",
    name: str = "",
    market: str = "",
    flow_type: str = "",       # northbound / southbound / etf_holding / margin
    net_amount: float = 0.0,
    cumulative: float = 0.0,
    position_change: float = 0.0,
    position_change_pct: float = 0.0,
    timestamp: str = "",
    source: str = "",
    data_source: str = "",
) -> Dict[str, Any]:
    """构造统一的资金流记录。

    flow_type:
        northbound  - 北向资金 (沪/深股通)
        southbound  - 南向资金 (港股通)
        etf_holding - ETF 持仓变化
        margin      - 融资融券
    """
    return {
        "id": f"flow_{symbol}_{flow_type}_{timestamp}",
        "data_type": "fund_flow",
        "symbol": str(symbol or ""),
        "name": str(name or ""),
        "market": str(market or ""),
        "flow_type": str(flow_type or ""),
        "net_amount": float(net_amount),
        "cumulative": float(cumulative),
        "position_change": float(position_change),
        "position_change_pct": float(position_change_pct),
        "timestamp": str(timestamp or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
    }


# ---------------------------------------------------------------------------
# 宏观事件模型 (新增)
# ---------------------------------------------------------------------------

def make_macro_event(
    *,
    event_name: str,
    country: str = "",
    importance: str = "",       # 高 / 中 / 低
    expected: Optional[float] = None,
    actual: Optional[float] = None,
    previous: Optional[float] = None,
    deviation: float = 0.0,
    impact_score: float = 0.0,
    release_time: str = "",
    source: str = "",
    data_source: str = "",
) -> Dict[str, Any]:
    """构造统一的宏观经济事件记录。

    impact_score 计算:
        偏离度 (|actual - expected| / |expected|) × 重要性权重
        高=3, 中=2, 低=1
    """
    return {
        "id": f"macro_{country}_{release_time}_{event_name}",
        "data_type": "macro_event",
        "event_name": str(event_name or ""),
        "country": str(country or ""),
        "importance": str(importance or ""),
        "expected": expected,
        "actual": actual,
        "previous": previous,
        "deviation": float(deviation),
        "impact_score": float(impact_score),
        "release_time": str(release_time or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
    }


# ---------------------------------------------------------------------------
# 技术指标模型 (新增)
# ---------------------------------------------------------------------------

def make_technical_record(
    *,
    symbol: str,
    name: str = "",
    market: str = "",
    asset_class: str = "",
    indicator_type: str = "",   # ma / bollinger / rsi / macd / atr / ratio
    indicator_name: str = "",
    period: str = "",
    value: Any = None,
    timestamp: str = "",
    source: str = "本地计算",
    data_source: str = "技术指标引擎",
) -> Dict[str, Any]:
    """构造统一的技术指标记录。"""
    return {
        "id": f"tech_{symbol}_{indicator_type}_{indicator_name}_{timestamp}",
        "data_type": "technical_signal",
        "symbol": str(symbol or ""),
        "name": str(name or ""),
        "market": str(market or ""),
        "asset_class": str(asset_class or ""),
        "indicator_type": str(indicator_type or ""),
        "indicator_name": str(indicator_name or ""),
        "period": str(period or ""),
        "value": value,
        "timestamp": str(timestamp or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
    }


# ---------------------------------------------------------------------------
# 巨潮公告模型 (现有)
# ---------------------------------------------------------------------------

def make_cninfo_record(
    *,
    record_id: str,
    stock_code: str,
    stock_name: str,
    title: str,
    announcement_type: str,
    publish_time: str,
    source: str,
    data_source: str,
    file_url: str = "",
    content: str = "",
    raw: Any = None,
) -> Dict[str, Any]:
    return {
        "id": str(record_id or ""),
        "record_type": "announcement",
        "stock_code": str(stock_code or ""),
        "stock_name": str(stock_name or ""),
        "title": str(title or ""),
        "announcement_type": str(announcement_type or ""),
        "publish_time": str(publish_time or ""),
        "source": str(source or ""),
        "data_source": str(data_source or ""),
        "file_url": str(file_url or ""),
        "content": str(content or ""),
        "raw": raw if raw is not None else {},
    }
