from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
NEWS_OUTPUT_DIR = BASE_DIR / "crawler_data" / "news"
NEWS_OUTPUT_PREFIX = "finance_news"

ENABLE_FLASH_NEWS = True

DEDUP_SIMILARITY_THRESHOLD = 0.9
DEDUP_TIME_WINDOW_MINUTES = 120

START_DATE = "2026-09-15 00:00:00"
END_DATE = "2026-09-15 23:59:59"

REQUEST_TIMEOUT = 15
FX678_PAGE_LIMIT = 40
CONCURRENT_WORKERS = 6

CLS_TELEGRAPH_URL = "https://www.cls.cn/v1/roll/get_roll_list"
CLS_PAGE_LIMIT = 40
CLS_PAGE_SIZE = 50

STCN_KX_URL = "https://www.stcn.com/article/list.html?type=kx"
STCN_PAGE_LIMIT = 40

JIN10_WEB_FLASH_URL = "https://www.jin10.com/news/"
JIN10_WEB_FLASH_API_URL = "https://flash-api.jin10.com/get_flash_list"
JIN10_FLASH_LIMIT = 1000
JIN10_PAGE_LIMIT = 80

WALLSTREETCN_LIVE_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
WALLSTREETCN_PAGE_LIMIT = 40
WALLSTREETCN_PAGE_SIZE = 20

# Backward-compatible aliases for older code paths.
OUTPUT_DIR = NEWS_OUTPUT_DIR
OUTPUT_PREFIX = NEWS_OUTPUT_PREFIX
DEFAULT_SOURCE = "all"
SOURCE_CONCURRENT_WORKERS = 5
