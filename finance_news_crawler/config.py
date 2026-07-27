from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "crawler_data"
DEFAULT_SOURCE = "all"
OUTPUT_PREFIX = "finance_news"

START_DATE = "2026-07-27 14:00:00"
END_DATE = "2026-07-27 14:59:59"

REQUEST_TIMEOUT = 15
FX678_PAGE_LIMIT = 2
CONCURRENT_WORKERS = 6

JIN10_WEB_FLASH_URL = "https://www.jin10.com/news/"
JIN10_WEB_FLASH_API_URL = "https://flash-api.jin10.com/get_flash_list"
JIN10_FLASH_LIMIT = 150
JIN10_PAGE_LIMIT = 20

WALLSTREETCN_LIVE_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
WALLSTREETCN_PAGE_LIMIT = 5
WALLSTREETCN_PAGE_SIZE = 20
