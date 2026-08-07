from __future__ import annotations

from clients.cninfo_client import CninfoClient
from clients.flash_registry import crawl_all_flash_sources
from common.dedup import deduplicate_records
from common.utils import save_json, sort_records_by_publish_time
from config import (
    CNINFO_DATASETS,
    CNINFO_OUTPUT_DIR,
    CNINFO_OUTPUT_PREFIX,
    ENABLE_CNINFO,
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


def run_cninfo_pipeline() -> None:
    client = CninfoClient(datasets=CNINFO_DATASETS)
    dataset_records = client.fetch_selected_datasets(START_DATE, END_DATE)

    if not dataset_records:
        print("No CNINFO records fetched.")
        return

    total = 0
    for dataset, records in dataset_records.items():
        if not records:
            continue
        output_path = save_json(records, CNINFO_OUTPUT_DIR, f"{CNINFO_OUTPUT_PREFIX}_{dataset}")
        total += len(records)
        print(f"Saved {len(records)} CNINFO records for {dataset} to {output_path}")

    if total == 0:
        print("No CNINFO records fetched.")


def main() -> None:
    if not ENABLE_FLASH_NEWS and not ENABLE_CNINFO:
        print("No task enabled. Set ENABLE_FLASH_NEWS or ENABLE_CNINFO in config.py.")
        return

    if ENABLE_FLASH_NEWS:
        run_flash_pipeline()

    if ENABLE_CNINFO:
        run_cninfo_pipeline()


if __name__ == "__main__":
    main()
