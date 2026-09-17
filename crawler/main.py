from __future__ import annotations

from pathlib import Path

from clients.flash_registry import crawl_all_flash_sources
from common.dedup import deduplicate_records
from common.logger import setup_logger, get_logger
from common.utils import save_json, sort_records_by_publish_time
from config import (
    ENABLE_FLASH_NEWS,
    END_DATE,
    NEWS_OUTPUT_DIR,
    NEWS_OUTPUT_PREFIX,
    START_DATE,
)

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"


def run_flash_pipeline() -> None:
    logger = get_logger("main")

    logger.info("=== 财经新闻爬虫启动 ===")
    logger.info(f"时间范围: {START_DATE} ~ {END_DATE}")

    records = crawl_all_flash_sources(START_DATE, END_DATE)
    logger.info(f"原始抓取: {len(records)} 条记录")

    records = sort_records_by_publish_time(records)
    before_dedup_count = len(records)

    logger.info("开始去重...")
    records = deduplicate_records(records)
    removed_count = before_dedup_count - len(records)

    if removed_count:
        logger.info(
            f"去重完成: 移除 {removed_count} 条重复 "
            f"({removed_count / before_dedup_count:.1%})"
        )
    else:
        logger.info("去重完成: 无重复记录")

    output_path = save_json(records, NEWS_OUTPUT_DIR, NEWS_OUTPUT_PREFIX)
    logger.info(f"保存成功: {len(records)} 条记录 -> {output_path}")
    logger.info("=== 爬虫任务完成 ===")


def main() -> None:
    setup_logger(
        log_dir=LOG_DIR,
        level="INFO",
        console=True,
        file_output=True,
        backup_days=30,
    )
    logger = get_logger("main")

    if not ENABLE_FLASH_NEWS:
        logger.warning(
            "快讯采集已禁用。在 config.py 中设置 ENABLE_FLASH_NEWS=True 可开启。"
        )
        return

    try:
        run_flash_pipeline()
    except Exception as e:
        logger.exception(f"爬虫执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
