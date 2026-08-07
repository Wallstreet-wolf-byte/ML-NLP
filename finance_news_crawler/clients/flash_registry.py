from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from clients.cls_client import ClsClient
from clients.fx678_client import Fx678Client
from clients.jin10_client import Jin10Client
from clients.stcn_client import StcnClient
from clients.wallstreetcn_client import WallStreetCnClient
from common.utils import parse_datetime
from config import (
    CLS_PAGE_LIMIT,
    CONCURRENT_WORKERS,
    END_DATE,
    FX678_PAGE_LIMIT,
    JIN10_FLASH_LIMIT,
    JIN10_PAGE_LIMIT,
    REQUEST_TIMEOUT,
    START_DATE,
    STCN_PAGE_LIMIT,
    WALLSTREETCN_PAGE_LIMIT,
)


@dataclass(frozen=True)
class FlashSourceSpec:
    name: str
    runner: Callable[[str, str], List[Dict[str, str]]]


def _run_fx678(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = Fx678Client(timeout=REQUEST_TIMEOUT, page_limit=FX678_PAGE_LIMIT, concurrent_workers=CONCURRENT_WORKERS)
    return client.fetch_by_time_range(parse_datetime(start_date), parse_datetime(end_date, is_end=True))


def _run_jin10(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = Jin10Client(timeout=REQUEST_TIMEOUT, limit=JIN10_FLASH_LIMIT, page_limit=JIN10_PAGE_LIMIT)
    return client.fetch_by_time_range(parse_datetime(start_date), parse_datetime(end_date, is_end=True))


def _run_wallstreetcn(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = WallStreetCnClient(timeout=REQUEST_TIMEOUT, page_limit=WALLSTREETCN_PAGE_LIMIT)
    return client.fetch_by_time_range(parse_datetime(start_date), parse_datetime(end_date, is_end=True))


def _run_cls(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = ClsClient(timeout=REQUEST_TIMEOUT, page_limit=CLS_PAGE_LIMIT)
    return client.fetch_by_time_range(parse_datetime(start_date), parse_datetime(end_date, is_end=True))


def _run_stcn(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = StcnClient(timeout=REQUEST_TIMEOUT, page_limit=STCN_PAGE_LIMIT)
    return client.fetch_by_time_range(parse_datetime(start_date), parse_datetime(end_date, is_end=True))


FLASH_SOURCE_SPECS: Sequence[FlashSourceSpec] = (
    FlashSourceSpec(name="fx678", runner=_run_fx678),
    FlashSourceSpec(name="jin10", runner=_run_jin10),
    FlashSourceSpec(name="wallstreetcn", runner=_run_wallstreetcn),
    FlashSourceSpec(name="cls", runner=_run_cls),
    FlashSourceSpec(name="stcn", runner=_run_stcn),
)


def crawl_all_flash_sources(start_date: str = START_DATE, end_date: str = END_DATE) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for spec in FLASH_SOURCE_SPECS:
        print(f"Start {spec.name.upper()} crawl...")
        try:
            records.extend(spec.runner(start_date, end_date))
        except Exception as exc:
            print(f"{spec.name.upper()} crawl failed: {exc}")
    return records


def iter_flash_sources() -> Iterable[FlashSourceSpec]:
    return FLASH_SOURCE_SPECS
