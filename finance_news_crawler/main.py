from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

from clients.cninfo_client import CninfoClient
from clients.flash_registry import FLASH_SOURCE_SPECS, FlashSourceSpec
from common.dedup import deduplicate_records
from common.state import CrawlState, compute_incremental_start
from common.utils import parse_datetime, save_json, sort_records_by_publish_time
from config import (
    BASE_DIR,
    CNINFO_DATASETS,
    CNINFO_OUTPUT_DIR,
    CNINFO_OUTPUT_PREFIX,
    ENABLE_CNINFO,
    ENABLE_FLASH_NEWS,
    END_DATE,
    INCREMENTAL_ENABLED,
    ITEM_RETENTION_DAYS,
    NEWS_OUTPUT_DIR,
    NEWS_OUTPUT_PREFIX,
    SOURCE_CONCURRENT_WORKERS,
    START_DATE,
    STATE_DB_PATH,
    apply_cli_overrides,
)

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("finance_news_crawler")


# ---------------------------------------------------------------------------
# CLI 参数解析
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="财经数据采集平台 - 多维度即时数据采集工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 快讯采集 (原有功能)
  python main.py --pipeline flash --source all
  python main.py --pipeline flash --source jin10 --start-date "2026-08-04 09:00:00"

  # 行情采集
  python main.py --pipeline market
  python main.py --pipeline market --market 港股

  # 资金流采集
  python main.py --pipeline fundflow

  # 宏观日历
  python main.py --pipeline macro

  # 技术指标
  python main.py --pipeline technical

  # 全量采集 + 筛选
  python main.py --pipeline all
  python main.py --pipeline all --market 港股 --asset-class 期货

  # 指定品种
  python main.py --pipeline market --symbol GC,SI,HSI
        """,
    )

    # --- 核心维度选择 ---
    parser.add_argument(
        "--pipeline",
        default=None,
        choices=["all", "flash", "market", "fundflow", "macro", "technical"],
        help="选择数据维度 (默认: flash 快讯)",
    )

    # --- 筛选参数 ---
    parser.add_argument(
        "--market",
        default=None,
        help="按市场筛选 (all / A股 / 港股 / 美股 / 全球)",
    )
    parser.add_argument(
        "--asset-class",
        default=None,
        dest="asset_class",
        help="按品种大类筛选 (all / 期货 / 股票 / 现货 / 外汇 / 债券 / 指数)",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="按品种代码筛选，逗号分隔 (如: GC,SI,HSI,VIX)",
    )
    parser.add_argument(
        "--importance",
        default=None,
        help="按重要度筛选 (all / 高 / 中 / 低)",
    )

    # --- 来源与日期 ---
    parser.add_argument(
        "--source",
        default=None,
        choices=["all", "fx678", "jin10", "wallstreetcn", "cls", "stcn"],
        help="选择新闻来源 (默认: config.yaml 中 default.source)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="开始时间 (格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="结束时间 (格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)",
    )

    # --- 分页与数量 ---
    parser.add_argument("--fx678-page-limit", type=int, default=None, help="汇通财经最大翻页数")
    parser.add_argument("--jin10-limit", type=int, default=None, help="金十最多保留记录数")
    parser.add_argument("--jin10-page-limit", type=int, default=None, help="金十最大翻页数")
    parser.add_argument("--wallstreetcn-page-limit", type=int, default=None, help="华尔街见闻最大翻页数")
    parser.add_argument("--cls-page-limit", type=int, default=None, help="财联社最大翻页数")
    parser.add_argument("--stcn-page-limit", type=int, default=None, help="证券时报-人民财讯最大翻页数")

    # --- 并发 ---
    parser.add_argument("--concurrent-workers", type=int, default=None, help="详情页并发抓取线程数 (FX678)")
    parser.add_argument(
        "--parallel-sources",
        action="store_true",
        default=None,
        help="并行抓取不同数据源",
    )
    parser.add_argument("--source-workers", type=int, default=None, help="来源级并发线程数")

    # --- 输出 ---
    parser.add_argument("--output-prefix", default=None, help="输出 JSON 文件名前缀")

    # --- 增量与状态 ---
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=None,
        help="增量爬取模式（仅抓取上次之后的新数据）",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        default=False,
        help="重置指定源的增量状态后重新全量爬取",
    )

    return parser


def _kwargs_from_args(args: argparse.Namespace) -> Dict[str, object]:
    """将 argparse 命名空间转为 config.apply_cli_overrides 所需的关键字参数。"""
    overrides: Dict[str, object] = {}

    if args.start_date is not None:
        overrides["start_date"] = args.start_date
    if args.end_date is not None:
        overrides["end_date"] = args.end_date
    if args.source is not None:
        overrides["source"] = args.source
    if args.fx678_page_limit is not None:
        overrides["fx678_page_limit"] = args.fx678_page_limit
    if args.jin10_limit is not None:
        overrides["jin10_flash_limit"] = args.jin10_limit
    if args.jin10_page_limit is not None:
        overrides["jin10_page_limit"] = args.jin10_page_limit
    if args.wallstreetcn_page_limit is not None:
        overrides["wallstreetcn_page_limit"] = args.wallstreetcn_page_limit
    if args.cls_page_limit is not None:
        overrides["cls_page_limit"] = args.cls_page_limit
    if args.stcn_page_limit is not None:
        overrides["stcn_page_limit"] = args.stcn_page_limit
    if args.concurrent_workers is not None:
        overrides["concurrent_workers"] = args.concurrent_workers
    if args.source_workers is not None:
        overrides["source_concurrent_workers"] = args.source_workers
    if args.output_prefix is not None:
        overrides["output_prefix"] = args.output_prefix
    if args.incremental is not None:
        overrides["incremental"] = args.incremental

    # --- 新增: pipeline & 筛选 ---
    if getattr(args, "pipeline", None) is not None:
        overrides["pipeline"] = args.pipeline
    if getattr(args, "market", None) is not None:
        overrides["market"] = args.market
    if getattr(args, "asset_class", None) is not None:
        overrides["asset_class"] = args.asset_class
    if getattr(args, "importance", None) is not None:
        overrides["importance"] = args.importance
    if getattr(args, "symbol", None) is not None:
        overrides["symbols"] = args.symbol

    return overrides


# ---------------------------------------------------------------------------
# 核心流水线
# ---------------------------------------------------------------------------

def _resolve_source_specs(target_source: str) -> Sequence[FlashSourceSpec]:
    """根据 --source 参数过滤要运行的爬虫。"""
    if target_source == "all":
        return FLASH_SOURCE_SPECS
    for spec in FLASH_SOURCE_SPECS:
        if spec.name == target_source:
            return (spec,)
    logger.warning("Unknown source '%s', fallback to all.", target_source)
    return FLASH_SOURCE_SPECS


def _resolve_time_range(args: argparse.Namespace) -> tuple:
    """解析时间范围，支持增量模式下的动态调整。"""
    start = parse_datetime(START_DATE)
    end = parse_datetime(END_DATE, is_end=True)

    if args.start_date:
        start = parse_datetime(args.start_date)
    if args.end_date:
        end = parse_datetime(args.end_date, is_end=True)

    return start, end


def _should_use_parallel(args: argparse.Namespace) -> bool:
    """是否启用并行源抓取。"""
    if args.parallel_sources is not None:
        return args.parallel_sources
    return False


def run_single_source(
    spec: FlashSourceSpec,
    start_date: str,
    end_date: str,
) -> List[Dict[str, str]]:
    """运行单个数据源爬虫，封装异常处理。"""
    logger.info("Starting %s crawl...", spec.name.upper())
    try:
        records = spec.runner(start_date, end_date)
        logger.info("%s crawl finished: %d records", spec.name.upper(), len(records))
        return records
    except Exception as exc:
        logger.error("%s crawl failed: %s", spec.name.upper(), exc, exc_info=True)
        return []


def run_flash_pipeline_serial(
    specs: Sequence[FlashSourceSpec],
    start_date_str: str,
    end_date_str: str,
) -> List[Dict[str, str]]:
    """串行执行多个数据源爬虫。"""
    records: List[Dict[str, str]] = []
    for spec in specs:
        records.extend(run_single_source(spec, start_date_str, end_date_str))
    return records


def run_flash_pipeline_parallel(
    specs: Sequence[FlashSourceSpec],
    start_date_str: str,
    end_date_str: str,
    max_workers: int,
) -> List[Dict[str, str]]:
    """并行执行多个数据源爬虫。"""
    records: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single_source, spec, start_date_str, end_date_str): spec.name
            for spec in specs
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                records.extend(future.result())
            except Exception as exc:
                logger.error("%s parallel crawl failed: %s", name, exc)
    return records


def _finalize_records(
    records: List[Dict[str, str]],
    output_prefix: str,
) -> None:
    """排序、去重、保存最终结果。"""
    records = sort_records_by_publish_time(records)

    before_dedup = len(records)
    records = deduplicate_records(records)
    removed = before_dedup - len(records)
    if removed:
        logger.info("Deduplicated %d duplicate records.", removed)

    output_path = save_json(records, NEWS_OUTPUT_DIR, output_prefix)
    logger.info("Saved %d flash records to %s", len(records), output_path)


def run_flash_pipeline(args: argparse.Namespace) -> None:
    """快讯主线流水线。"""
    specs = _resolve_source_specs(DEFAULT_SOURCE)
    if not ENABLE_FLASH_NEWS or not specs:
        logger.info("Flash news pipeline disabled or no sources matched.")
        return

    start_dt, end_dt = _resolve_time_range(args)

    # --- 增量模式处理 ---
    state: CrawlState | None = None
    if INCREMENTAL_ENABLED:
        state = CrawlState(STATE_DB_PATH, item_retention_days=ITEM_RETENTION_DAYS)
        state.print_summary()

        # 重置指定源
        if args.reset_state:
            for spec in specs:
                state.reset_source(spec.name)
                logger.info("Reset state for source: %s", spec.name)

        # 动态调整起始时间：每个源从各自上次结束时间开始
        start_dt = compute_incremental_start(state, "global", start_dt)
        end_dt = datetime.now()

    start_date_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_date_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Time range: %s -> %s", start_date_str, end_date_str)

    # --- 执行爬取 ---
    use_parallel = _should_use_parallel(args)
    if use_parallel:
        workers = SOURCE_CONCURRENT_WORKERS
        logger.info("Running %d sources in parallel (workers=%d)", len(specs), workers)
        records = run_flash_pipeline_parallel(specs, start_date_str, end_date_str, workers)
    else:
        logger.info("Running %d sources serially", len(specs))
        records = run_flash_pipeline_serial(specs, start_date_str, end_date_str)

    if not records:
        logger.warning("No records collected from any source.")
        return

    # --- 去重 + 保存 ---
    _finalize_records(records, NEWS_OUTPUT_PREFIX)

    # --- 更新增量状态 ---
    if state and records:
        # 记录本次爬取中每个源的新条目
        for spec in specs:
            source_records = [r for r in records if r.get("data_source", "").startswith(spec.name)]
            if source_records:
                item_ids = [r["id"] for r in source_records if r.get("id")]
                state.mark_items_crawled(spec.name, item_ids)
                state.update_crawl_state(
                    spec.name,
                    end_dt,
                    count=len(source_records),
                )

        # 定期清理过期记录
        state.prune_old_items()
        logger.info("Incremental state updated.")


def run_cninfo_pipeline() -> None:
    """CNINFO 巨潮资讯公告流水线。"""
    client = CninfoClient(datasets=CNINFO_DATASETS)
    dataset_records = client.fetch_selected_datasets(START_DATE, END_DATE)

    if not dataset_records:
        logger.info("No CNINFO records fetched.")
        return

    total = 0
    for dataset, records in dataset_records.items():
        if not records:
            continue
        output_path = save_json(records, CNINFO_OUTPUT_DIR, f"{CNINFO_OUTPUT_PREFIX}_{dataset}")
        total += len(records)
        logger.info("Saved %d CNINFO records for %s to %s", len(records), dataset, output_path)

    if total == 0:
        logger.info("No CNINFO records fetched.")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # CLI 参数覆盖 YAML 配置
    apply_cli_overrides(**_kwargs_from_args(args))

    # 确定 pipeline 模式
    pipeline_mode = getattr(args, "pipeline", None) or "flash"

    logger.info("=" * 60)
    logger.info("Finance Data Platform starting")
    logger.info("Config: %s", BASE_DIR / "config.yaml")
    logger.info("Pipeline: %s", pipeline_mode)
    if getattr(args, "market", None):
        logger.info("Market filter: %s", args.market)
    if getattr(args, "asset_class", None):
        logger.info("Asset class filter: %s", args.asset_class)
    logger.info("=" * 60)

    # --- 新 pipeline 模式（非 flash）---
    if pipeline_mode != "flash":
        from clients.pipeline_registry import run_pipelines

        stats = run_pipelines(
            pipeline_name=pipeline_mode,
            output_prefix=NEWS_OUTPUT_PREFIX,
        )
        total = sum(stats.values())
        logger.info("Pipeline complete: %d total records", total)
        logger.info("Stats: %s", stats)
        return

    # --- 原有 flash 模式 ---
    if not ENABLE_FLASH_NEWS and not ENABLE_CNINFO:
        logger.warning("No task enabled. Set enable_flash_news or enable_cninfo in config.yaml.")
        sys.exit(0)

    if ENABLE_FLASH_NEWS:
        run_flash_pipeline(args)

    if ENABLE_CNINFO:
        run_cninfo_pipeline()

    logger.info("Done.")


if __name__ == "__main__":
    main()
