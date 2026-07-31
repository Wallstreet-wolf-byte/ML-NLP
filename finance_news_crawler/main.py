from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from clients.cls_client import ClsClient
from clients.fx678_client import Fx678Client
from clients.jin10_client import Jin10Client
from clients.stcn_client import StcnClient
from clients.wallstreetcn_client import WallStreetCnClient
from common.utils import parse_datetime, save_json, sort_records_by_publish_time
from common.dedup import deduplicate_records
from config import (
    CLS_PAGE_LIMIT,
    CONCURRENT_WORKERS,
    DEFAULT_SOURCE,
    END_DATE,
    FX678_PAGE_LIMIT,
    JIN10_FLASH_LIMIT,
    JIN10_PAGE_LIMIT,
    OUTPUT_DIR,
    OUTPUT_PREFIX,
    REQUEST_TIMEOUT,
    SOURCE_CONCURRENT_WORKERS,
    START_DATE,
    STCN_PAGE_LIMIT,
    WALLSTREETCN_PAGE_LIMIT,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finance news crawler for FX678, Jin10, WallStreetCN, CLS, and STCN.")
    parser.add_argument(
        "--source",
        choices=("all", "fx678", "jin10", "wallstreetcn", "cls", "stcn"),
        default=DEFAULT_SOURCE,
    )
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument("--end-date", default=END_DATE)
    parser.add_argument("--fx678-page-limit", type=int, default=FX678_PAGE_LIMIT)
    parser.add_argument("--jin10-limit", type=int, default=JIN10_FLASH_LIMIT)
    parser.add_argument("--jin10-page-limit", type=int, default=JIN10_PAGE_LIMIT)
    parser.add_argument("--wallstreetcn-page-limit", type=int, default=WALLSTREETCN_PAGE_LIMIT)
    parser.add_argument("--cls-page-limit", type=int, default=CLS_PAGE_LIMIT)
    parser.add_argument("--stcn-page-limit", type=int, default=STCN_PAGE_LIMIT)
    parser.add_argument("--concurrent-workers", type=int, default=CONCURRENT_WORKERS)
    parser.add_argument("--parallel-sources", action="store_true", help="Fetch all sources in parallel when --source all.")
    parser.add_argument("--source-workers", type=int, default=SOURCE_CONCURRENT_WORKERS)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    return parser.parse_args()


def crawl_fx678(start_date: str, end_date: str, page_limit: int, concurrent_workers: int) -> List[Dict[str, str]]:
    client = Fx678Client(timeout=REQUEST_TIMEOUT, page_limit=page_limit, concurrent_workers=concurrent_workers)
    start_dt = parse_datetime(start_date)
    end_dt = parse_datetime(end_date, is_end=True)
    return client.fetch_by_time_range(start_dt, end_dt)


def crawl_jin10(start_date: str, end_date: str, limit: int, page_limit: int) -> List[Dict[str, str]]:
    client = Jin10Client(timeout=REQUEST_TIMEOUT, limit=limit, page_limit=page_limit)
    start_dt = parse_datetime(start_date)
    end_dt = parse_datetime(end_date, is_end=True)
    return client.fetch_by_time_range(start_dt, end_dt)


def crawl_wallstreetcn(start_date: str, end_date: str, page_limit: int) -> List[Dict[str, str]]:
    client = WallStreetCnClient(timeout=REQUEST_TIMEOUT, page_limit=page_limit)
    start_dt = parse_datetime(start_date)
    end_dt = parse_datetime(end_date, is_end=True)
    return client.fetch_by_time_range(start_dt, end_dt)


def crawl_cls(start_date: str, end_date: str, page_limit: int) -> List[Dict[str, str]]:
    client = ClsClient(timeout=REQUEST_TIMEOUT, page_limit=page_limit)
    start_dt = parse_datetime(start_date)
    end_dt = parse_datetime(end_date, is_end=True)
    return client.fetch_by_time_range(start_dt, end_dt)


def crawl_stcn(start_date: str, end_date: str, page_limit: int) -> List[Dict[str, str]]:
    client = StcnClient(timeout=REQUEST_TIMEOUT, page_limit=page_limit)
    start_dt = parse_datetime(start_date)
    end_dt = parse_datetime(end_date, is_end=True)
    return client.fetch_by_time_range(start_dt, end_dt)


def crawl_selected_sources(args: argparse.Namespace) -> List[Dict[str, str]]:
    if args.source != "all" or not args.parallel_sources:
        records: List[Dict[str, str]] = []

        if args.source in ("all", "fx678"):
            print("Start FX678 crawl...")
            records.extend(crawl_fx678(args.start_date, args.end_date, args.fx678_page_limit, args.concurrent_workers))

        if args.source in ("all", "jin10"):
            print("Start Jin10 crawl...")
            records.extend(crawl_jin10(args.start_date, args.end_date, args.jin10_limit, args.jin10_page_limit))

        if args.source in ("all", "wallstreetcn"):
            print("Start WallStreetCN crawl...")
            records.extend(crawl_wallstreetcn(args.start_date, args.end_date, args.wallstreetcn_page_limit))

        if args.source in ("all", "cls"):
            print("Start CLS crawl...")
            records.extend(crawl_cls(args.start_date, args.end_date, args.cls_page_limit))

        if args.source in ("all", "stcn"):
            print("Start STCN People Finance crawl...")
            records.extend(crawl_stcn(args.start_date, args.end_date, args.stcn_page_limit))

        return records

    tasks = [
        ("fx678", lambda: crawl_fx678(args.start_date, args.end_date, args.fx678_page_limit, args.concurrent_workers)),
        ("jin10", lambda: crawl_jin10(args.start_date, args.end_date, args.jin10_limit, args.jin10_page_limit)),
        ("wallstreetcn", lambda: crawl_wallstreetcn(args.start_date, args.end_date, args.wallstreetcn_page_limit)),
        ("cls", lambda: crawl_cls(args.start_date, args.end_date, args.cls_page_limit)),
        ("stcn", lambda: crawl_stcn(args.start_date, args.end_date, args.stcn_page_limit)),
    ]

    records: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.source_workers, len(tasks)))) as executor:
        future_to_source: Dict[object, str] = {}
        for source, task in tasks:
            print(f"Start {source.upper()} crawl...")
            future_to_source[executor.submit(task)] = source

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                records.extend(future.result())
            except Exception as exc:
                print(f"{source.upper()} crawl failed: {exc}")

    return records


def main() -> None:
    args = parse_args()
    records = crawl_selected_sources(args)
    records = sort_records_by_publish_time(records)
    before_dedup_count = len(records)
    records = deduplicate_records(records)
    removed_count = before_dedup_count - len(records)
    if removed_count:
        print(f"Deduplicated {removed_count} duplicate records.")

    output_path = save_json(records, OUTPUT_DIR, args.output_prefix)
    print(f"Saved {len(records)} records to {output_path}")


if __name__ == "__main__":
    main()
