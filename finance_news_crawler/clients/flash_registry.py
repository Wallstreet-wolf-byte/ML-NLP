from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import config
from clients.cls_client import ClsClient
from clients.fx678_client import Fx678Client
from clients.jin10_client import Jin10Client
from clients.stcn_client import StcnClient
from clients.wallstreetcn_client import WallStreetCnClient
from common.utils import parse_datetime


@dataclass(frozen=True)
class FlashSourceSpec:
    name: str
    runner: Callable[[str, str], List[Dict[str, str]]]


def _run_fx678(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = Fx678Client(
        timeout=config.REQUEST_TIMEOUT,
        page_limit=config.FX678_PAGE_LIMIT,
        concurrent_workers=config.CONCURRENT_WORKERS,
    )
    return client.fetch_by_time_range(
        parse_datetime(start_date),
        parse_datetime(end_date, is_end=True),
    )


def _run_jin10(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = Jin10Client(
        timeout=config.REQUEST_TIMEOUT,
        limit=config.JIN10_FLASH_LIMIT,
        page_limit=config.JIN10_PAGE_LIMIT,
    )
    return client.fetch_by_time_range(
        parse_datetime(start_date),
        parse_datetime(end_date, is_end=True),
    )


def _run_wallstreetcn(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = WallStreetCnClient(
        timeout=config.REQUEST_TIMEOUT,
        page_limit=config.WALLSTREETCN_PAGE_LIMIT,
    )
    return client.fetch_by_time_range(
        parse_datetime(start_date),
        parse_datetime(end_date, is_end=True),
    )


def _run_cls(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = ClsClient(
        timeout=config.REQUEST_TIMEOUT,
        page_limit=config.CLS_PAGE_LIMIT,
    )
    return client.fetch_by_time_range(
        parse_datetime(start_date),
        parse_datetime(end_date, is_end=True),
    )


def _run_stcn(start_date: str, end_date: str) -> List[Dict[str, str]]:
    client = StcnClient(
        timeout=config.REQUEST_TIMEOUT,
        page_limit=config.STCN_PAGE_LIMIT,
    )
    return client.fetch_by_time_range(
        parse_datetime(start_date),
        parse_datetime(end_date, is_end=True),
    )


FLASH_SOURCE_SPECS: Sequence[FlashSourceSpec] = (
    FlashSourceSpec(name="fx678", runner=_run_fx678),
    FlashSourceSpec(name="jin10", runner=_run_jin10),
    FlashSourceSpec(name="wallstreetcn", runner=_run_wallstreetcn),
    FlashSourceSpec(name="cls", runner=_run_cls),
    FlashSourceSpec(name="stcn", runner=_run_stcn),
)


def crawl_all_flash_sources(
    start_date: str = config.START_DATE,
    end_date: str = config.END_DATE,
) -> List[Dict[str, str]]:
    """串行爬取全部已注册的快讯数据源。"""
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
