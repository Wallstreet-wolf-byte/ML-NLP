from __future__ import annotations

from clients.flash_registry import crawl_all_flash_sources
from common.dedup import deduplicate_records
from common.utils import save_json, sort_records_by_publish_time
from config import (
    ENABLE_FLASH_NEWS,
    END_DATE,
    NEWS_OUTPUT_DIR,
    NEWS_OUTPUT_PREFIX,
    START_DATE,
)


def run_flash_pipeline() -> None:
    records = crawl_all_flash_sources(START_DATE, END_DATE)
    records = sort_records_by_publish_time(records)
    before_dedup_count = len(records)
    records = deduplicate_records(records)
    removed_count = before_dedup_count - len(records)
    if removed_count:
        print(f"Deduplicated {removed_count} duplicate records.")

    output_path = save_json(records, NEWS_OUTPUT_DIR, NEWS_OUTPUT_PREFIX)
    print(f"Saved {len(records)} flash records to {output_path}")


def main() -> None:
    if not ENABLE_FLASH_NEWS:
        print("Flash news collection is disabled. Set ENABLE_FLASH_NEWS=True in config.py.")
        return

    run_flash_pipeline()


if __name__ == "__main__":
    main()
