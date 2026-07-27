from __future__ import annotations

import argparse
from typing import Dict, List

from clients.fx678_client import Fx678Client
from clients.jin10_client import Jin10Client
from clients.wallstreetcn_client import WallStreetCnClient
from common.utils import parse_datetime, save_json, sort_records_by_publish_time
from config import (
    CONCURRENT_WORKERS,
    DEFAULT_SOURCE,
    END_DATE,
    FX678_PAGE_LIMIT,
    JIN10_FLASH_LIMIT,
    JIN10_PAGE_LIMIT,
    OUTPUT_DIR,
    OUTPUT_PREFIX,
    REQUEST_TIMEOUT,
    START_DATE,
    WALLSTREETCN_PAGE_LIMIT,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finance news crawler for FX678, Jin10, and WallStreetCN.")
    parser.add_argument("--source", choices=("all", "fx678", "jin10", "wallstreetcn"), default=DEFAULT_SOURCE)
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument("--end-date", default=END_DATE)
    parser.add_argument("--fx678-page-limit", type=int, default=FX678_PAGE_LIMIT)
    parser.add_argument("--jin10-limit", type=int, default=JIN10_FLASH_LIMIT)
    parser.add_argument("--jin10-page-limit", type=int, default=JIN10_PAGE_LIMIT)
    parser.add_argument("--wallstreetcn-page-limit", type=int, default=WALLSTREETCN_PAGE_LIMIT)
    parser.add_argument("--concurrent-workers", type=int, default=CONCURRENT_WORKERS)
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


def crawl_selected_sources(args: argparse.Namespace) -> List[Dict[str, str]]:
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

    return records


def main() -> None:
    args = parse_args()
    records = sort_records_by_publish_time(crawl_selected_sources(args))

    output_path = save_json(records, OUTPUT_DIR, args.output_prefix)
    print(f"Saved {len(records)} records to {output_path}")


if __name__ == "__main__":
    main()
