# ============================================================
# Pipeline 注册表
# 统一管理各数据维度的采集入口，类似 flash_registry.py 的模式
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from common.utils import save_json, sort_records_by_publish_time


@dataclass(frozen=True)
class PipelineSpec:
    """单个 pipeline 的描述。"""
    name: str           # 标识符：flash / market / fundflow / macro / technical
    label: str          # 中文名：快讯 / 行情 / 资金 / 宏观 / 技术
    runner: Callable[[], List[Dict[str, Any]]]  # 采集函数，返回记录列表
    enabled_by_default: bool = True


# ---------------------------------------------------------------------------
# Pipeline 运行器工厂
# ---------------------------------------------------------------------------

def _make_flash_runner() -> Callable[[], List[Dict[str, Any]]]:
    """快讯 pipeline 运行器。"""
    from config import DEFAULT_SOURCE
    from clients.flash_registry import FLASH_SOURCE_SPECS, FlashSourceSpec

    def _runner() -> List[Dict[str, Any]]:
        from datetime import datetime
        from config import START_DATE, END_DATE
        from common.dedup import deduplicate_records
        from common.entity_matcher import tag_record

        target = DEFAULT_SOURCE
        if target == "all":
            specs = FLASH_SOURCE_SPECS
        else:
            specs = tuple(s for s in FLASH_SOURCE_SPECS if s.name == target)

        records = []
        for spec in specs:
            try:
                records.extend(spec.runner(START_DATE, END_DATE))
            except Exception as e:
                print(f"[{spec.name}] failed: {e}")

        records = deduplicate_records(records)

        # 快讯打标：为每条快讯打品种/市场/大类标签（支持重叠，不遗漏）
        for r in records:
            tag_record(r)

        return records

    return _runner


def _make_market_runner() -> Callable[[], List[Dict[str, Any]]]:
    """行情 pipeline 运行器（按品种/市场/大类优先级采集，减少请求）。"""
    def _runner() -> List[Dict[str, Any]]:
        from config import (
            MARKET_DATA_CATEGORIES,
            FILTER_DEFAULT_MARKET,
            FILTER_DEFAULT_ASSET_CLASS,
            FILTER_SYMBOLS,
        )
        from clients.market_data_client import (
            fetch_all_quotes,
            fetch_quotes_by_market,
            fetch_quotes_by_asset_class,
            fetch_quotes_by_symbols,
        )

        # 优先级：指定品种 > 指定市场 > 指定大类 > 全量
        if FILTER_SYMBOLS:
            return fetch_quotes_by_symbols(MARKET_DATA_CATEGORIES, FILTER_SYMBOLS)
        elif FILTER_DEFAULT_MARKET != "all":
            return fetch_quotes_by_market(MARKET_DATA_CATEGORIES, FILTER_DEFAULT_MARKET)
        elif FILTER_DEFAULT_ASSET_CLASS != "all":
            return fetch_quotes_by_asset_class(MARKET_DATA_CATEGORIES, FILTER_DEFAULT_ASSET_CLASS)
        else:
            return fetch_all_quotes(MARKET_DATA_CATEGORIES)

    return _runner


def _make_fundflow_runner() -> Callable[[], List[Dict[str, Any]]]:
    """资金流 pipeline 运行器。"""
    def _runner() -> List[Dict[str, Any]]:
        from config import FUND_FLOW_CONFIG
        from clients.fund_flow_client import fetch_all_fund_flows

        etf_configs = FUND_FLOW_CONFIG.get("etf", {}).get("items", [])
        northbound_enabled = FUND_FLOW_CONFIG.get("northbound", {}).get("enabled", True)
        southbound_enabled = FUND_FLOW_CONFIG.get("southbound", {}).get("enabled", True)

        # 简单模式：传递 etf 配置
        return fetch_all_fund_flows(etf_configs=etf_configs)

    return _runner


def _make_macro_runner() -> Callable[[], List[Dict[str, Any]]]:
    """宏观日历 pipeline 运行器。"""
    def _runner() -> List[Dict[str, Any]]:
        from config import MACRO_IMPORTANCE_FILTER, MACRO_COUNTRIES
        from clients.macro_calendar_client import fetch_filtered_calendar

        return fetch_filtered_calendar(
            importance_filter=MACRO_IMPORTANCE_FILTER,
            countries=MACRO_COUNTRIES,
        )

    return _runner


def _make_technical_runner() -> Callable[[], List[Dict[str, Any]]]:
    """技术指标 pipeline 运行器（基于真实历史日线计算）。"""
    def _runner() -> List[Dict[str, Any]]:
        from config import MARKET_DATA_CATEGORIES, TUSHARE_TOKEN
        from clients.market_data_client import fetch_all_quotes
        from clients.technical_client import compute_all_indicators, compute_ratios
        from clients.tushare_client import fetch_kline_by_symbol

        records = []
        quotes = {}

        # 1. 获取行情快照作为输入（用于品种识别和比值计算）
        quote_records = fetch_all_quotes(MARKET_DATA_CATEGORIES)

        for qr in quote_records:
            symbol = qr.get("symbol", "")
            latest = qr.get("latest", 0)
            if symbol and latest > 0:
                quotes[symbol] = latest

        # 2. 对每个品种计算技术指标（优先用 TuShare 真实历史日线）
        for qr in quote_records:
            symbol = qr.get("symbol", "")
            name = qr.get("name", "")
            market = qr.get("market", "")
            asset_class = qr.get("asset_class", "")
            latest = qr.get("latest", 0)

            if latest <= 0:
                continue

            # 从 TuShare 拉取真实历史日线（金银/恒指等品种）
            prices: List[float] = []
            highs: List[float] = []
            lows: List[float] = []

            if TUSHARE_TOKEN:
                klines = fetch_kline_by_symbol(symbol, TUSHARE_TOKEN)
                if klines:
                    prices = [k["close"] for k in klines if k.get("close") is not None]
                    highs = [k["high"] for k in klines if k.get("high") is not None]
                    lows = [k["low"] for k in klines if k.get("low") is not None]

            # 无真实历史数据时跳过指标计算（不编造模拟数据）
            if len(prices) < 30:
                continue

            records.extend(compute_all_indicators(
                symbol=symbol, name=name, market=market, asset_class=asset_class,
                prices=prices, highs=highs, lows=lows,
            ))

        # 3. 计算跨品种比值（基于实时行情快照）
        if quotes:
            records.extend(compute_ratios(quotes))

        return records

    return _runner


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

PIPELINE_SPECS = [
    PipelineSpec(
        name="flash",
        label="7x24快讯",
        runner=_make_flash_runner(),
        enabled_by_default=True,
    ),
    PipelineSpec(
        name="market",
        label="实时行情",
        runner=_make_market_runner(),
        enabled_by_default=True,
    ),
    PipelineSpec(
        name="fundflow",
        label="资金流向",
        runner=_make_fundflow_runner(),
        enabled_by_default=True,
    ),
    PipelineSpec(
        name="macro",
        label="宏观日历",
        runner=_make_macro_runner(),
        enabled_by_default=True,
    ),
    PipelineSpec(
        name="technical",
        label="技术指标",
        runner=_make_technical_runner(),
        enabled_by_default=True,
    ),
]


def get_pipelines(pipeline_name: str = "all") -> list:
    """获取要执行的 pipeline 列表。"""
    if pipeline_name == "all":
        return PIPELINE_SPECS
    for spec in PIPELINE_SPECS:
        if spec.name == pipeline_name:
            return [spec]
    return PIPELINE_SPECS  # 未知名称回退到全部


def run_pipelines(pipeline_name: str = "all",
                  output_dir=None,
                  output_prefix: str = "finance_data") -> Dict[str, int]:
    """
    执行指定的 pipeline(s)，统一应用品种/市场/大类筛选后输出结果。

    参数:
        pipeline_name: pipeline 名称 (all / flash / market / fundflow / macro / technical)
        output_dir: 输出目录（默认使用 NEWS_OUTPUT_DIR）
        output_prefix: 输出文件前缀

    返回:
        {"pipeline_name": record_count, ...} 各 pipeline 采集记录数
    """
    import config
    from common.entity_matcher import filter_records_by_criteria

    specs = get_pipelines(pipeline_name)
    odir = output_dir or config.NEWS_OUTPUT_DIR

    # 统一筛选条件
    market = config.FILTER_DEFAULT_MARKET
    asset_class = config.FILTER_DEFAULT_ASSET_CLASS
    symbols = config.FILTER_SYMBOLS

    if symbols:
        print(f"[筛选] 品种: {symbols}")
    if market != "all":
        print(f"[筛选] 市场: {market}")
    if asset_class != "all":
        print(f"[筛选] 品种大类: {asset_class}")

    stats = {}
    for spec in specs:
        label = spec.name
        try:
            records = spec.runner()
            if records:
                # 统一筛选（宽匹配，支持重叠，不遗漏）
                records = filter_records_by_criteria(
                    records, market=market, asset_class=asset_class, symbols=symbols
                )
            if records:
                records = sort_records_by_publish_time(records)
                path = save_json(records, odir, f"{output_prefix}_{label}")
                print(f"[{spec.label}] {len(records)} records -> {path}")
            else:
                print(f"[{spec.label}] 0 records (无数据或采集失败)")
            stats[label] = len(records)
        except Exception as e:
            print(f"[{spec.label}] failed: {e}")
            stats[label] = 0

    return stats
