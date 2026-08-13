# ============================================================
# 技术指标计算客户端
# 从行情数据计算常用技术指标：MA/布林带/RSI/MACD/ATR/品种比值
# 基于 numpy 本地计算，不依赖外部 API
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from common.models import make_technical_record


def _ensure_numpy():
    """确保 numpy 可用。"""
    try:
        import numpy as np
        return np
    except ImportError:
        raise ImportError(
            "numpy is required for technical indicators. "
            "Run: pip install numpy"
        )


# ---------------------------------------------------------------------------
# MA 移动平均线
# ---------------------------------------------------------------------------

def calc_ma(prices: List[float], period: int) -> Optional[float]:
    """计算简单移动平均线。"""
    if len(prices) < period:
        return None
    np = _ensure_numpy()
    return float(np.mean(prices[-period:]))


# ---------------------------------------------------------------------------
# 布林带 (Bollinger Bands)
# ---------------------------------------------------------------------------

def calc_bollinger(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, Optional[float]]:
    """计算布林带上中下轨。"""
    if len(prices) < period:
        return {"upper": None, "middle": None, "lower": None}

    np = _ensure_numpy()
    window = np.array(prices[-period:])
    middle = float(np.mean(window))
    std = float(np.std(window, ddof=0))
    return {
        "upper": round(middle + std_dev * std, 4),
        "middle": round(middle, 4),
        "lower": round(middle - std_dev * std, 4),
    }


# ---------------------------------------------------------------------------
# RSI 相对强弱指标
# ---------------------------------------------------------------------------

def calc_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """计算 RSI (Wilder's smoothing)。"""
    if len(prices) < period + 1:
        return None

    np = _ensure_numpy()
    deltas = np.diff(prices[-period - 1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def calc_macd(prices: List[float],
              fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
    """计算 MACD (EMA 方式)。"""
    if len(prices) < slow + signal:
        return {"dif": None, "dea": None, "macd": None}

    np = _ensure_numpy()
    prices_arr = np.array(prices)

    def _ema(data, period):
        if len(data) < period:
            return None
        alpha = 2 / (period + 1)
        ema = float(data[0])
        for val in data[1:]:
            ema = alpha * float(val) + (1 - alpha) * ema
        return ema

    ema_fast_series = [_ema(prices_arr[:i+1], fast) for i in range(fast-1, len(prices_arr))]
    ema_slow_series = [_ema(prices_arr[:i+1], slow) for i in range(slow-1, len(prices_arr))]

    # 对齐长度
    min_len = min(len(ema_fast_series), len(ema_slow_series))
    dif_series = [ema_fast_series[-min_len + i] - ema_slow_series[-min_len + i] for i in range(min_len)]

    if len(dif_series) < signal:
        return {"dif": None, "dea": None, "macd": None}

    dea = _ema(np.array(dif_series), signal)
    if dea is None:
        return {"dif": None, "dea": None, "macd": None}

    dif = dif_series[-1]
    macd_val = (dif - dea) * 2  # 柱状线

    return {
        "dif": round(dif, 4),
        "dea": round(dea, 4),
        "macd": round(macd_val, 4),
    }


# ---------------------------------------------------------------------------
# ATR 真实波幅
# ---------------------------------------------------------------------------

def calc_atr(highs: List[float], lows: List[float], closes: List[float],
             period: int = 14) -> Optional[float]:
    """计算 ATR (Average True Range)。"""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None

    np = _ensure_numpy()
    true_ranges = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1]),
        )
        true_ranges.append(tr)

    return round(float(np.mean(true_ranges[-period:])), 4)


# ---------------------------------------------------------------------------
# 跨品种比值
# ---------------------------------------------------------------------------

def calc_ratio(numerator: float, denominator: float) -> Optional[float]:
    """计算比值。"""
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


# ---------------------------------------------------------------------------
# 批量技术指标计算
# ---------------------------------------------------------------------------

def compute_all_indicators(
    symbol: str,
    name: str,
    market: str,
    asset_class: str,
    prices: List[float],
    highs: List[float] = None,
    lows: List[float] = None,
) -> List[Dict[str, Any]]:
    """
    对单个品种计算全部启用的技术指标。

    参数:
        symbol / name / market / asset_class: 品种标识
        prices: 收盘价序列（从旧到新）
        highs / lows: 最高/最低价序列

    返回:
        List[Dict] 技术指标记录列表
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results: List[Dict[str, Any]] = []

    # MA
    for period in [5, 10, 20, 60, 120]:
        val = calc_ma(prices, period)
        if val is not None:
            results.append(make_technical_record(
                symbol=symbol, name=name, market=market, asset_class=asset_class,
                indicator_type="ma", indicator_name=f"MA{period}",
                period=str(period), value=val, timestamp=timestamp,
            ))

    # Bollinger
    bb = calc_bollinger(prices, 20, 2)
    if bb["upper"] is not None:
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="bollinger", indicator_name="BOLL_UPPER",
            period="20", value=bb["upper"], timestamp=timestamp,
        ))
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="bollinger", indicator_name="BOLL_MIDDLE",
            period="20", value=bb["middle"], timestamp=timestamp,
        ))
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="bollinger", indicator_name="BOLL_LOWER",
            period="20", value=bb["lower"], timestamp=timestamp,
        ))

    # RSI
    rsi = calc_rsi(prices, 14)
    if rsi is not None:
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="rsi", indicator_name="RSI14",
            period="14", value=rsi, timestamp=timestamp,
        ))

    # MACD
    macd = calc_macd(prices)
    if macd["dif"] is not None:
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="macd", indicator_name="MACD_DIF",
            period="12/26/9", value=macd["dif"], timestamp=timestamp,
        ))
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="macd", indicator_name="MACD_DEA",
            period="12/26/9", value=macd["dea"], timestamp=timestamp,
        ))
        results.append(make_technical_record(
            symbol=symbol, name=name, market=market, asset_class=asset_class,
            indicator_type="macd", indicator_name="MACD_HIST",
            period="12/26/9", value=macd["macd"], timestamp=timestamp,
        ))

    # ATR
    if highs is not None and lows is not None:
        atr = calc_atr(highs, lows, prices, 14)
        if atr is not None:
            results.append(make_technical_record(
                symbol=symbol, name=name, market=market, asset_class=asset_class,
                indicator_type="atr", indicator_name="ATR14",
                period="14", value=atr, timestamp=timestamp,
            ))

    return results


def compute_ratios(quotes: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    计算跨品种比值（金银比、金油比、铜金比）。

    参数:
        quotes: {"GC": 2650.5, "SI": 31.2, "CL": 72.0, "HG": 4.5, ...}

    返回:
        List[Dict] 比值记录
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    ratio_configs = [
        ("金银比", "GC", "SI"),
        ("金油比", "GC", "CL"),
        ("铜金比", "HG", "GC"),
    ]

    for ratio_name, num_sym, den_sym in ratio_configs:
        num = quotes.get(num_sym)
        den = quotes.get(den_sym)
        if num and den:
            val = calc_ratio(num, den)
            if val is not None:
                results.append(make_technical_record(
                    symbol=f"{num_sym}/{den_sym}",
                    name=ratio_name,
                    market="全球",
                    asset_class="比值",
                    indicator_type="ratio",
                    indicator_name=ratio_name,
                    period="实时",
                    value=val,
                    timestamp=timestamp,
                ))

    return results
