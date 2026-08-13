from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = BASE_DIR / "config.yaml"
_ENV_PREFIX = "NEWS_CRAWLER_"

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def _load_yaml() -> Dict[str, Any]:
    """从 config.yaml 加载原始配置字典。"""
    if yaml is None:
        raise ImportError(
            "PyYAML is required to load config.yaml. "
            "Run: pip install pyyaml"
        )
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {_CONFIG_PATH}")

    with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
        data: Dict[str, Any] = yaml.safe_load(fh) or {}
    return data


def _apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """应用环境变量覆盖：NEWS_CRAWLER_<SECTION>_<KEY>=<VALUE>"""
    result: Dict[str, Any] = dict(data)
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue
        # 解析：NEWS_CRAWLER_REQUEST_TIMEOUT -> section=request, key=timeout
        rest = env_key[len(_ENV_PREFIX):].lower()
        parts = rest.split("_", 1)
        if len(parts) != 2:
            continue
        section, key = parts
        if section not in result or not isinstance(result[section], dict):
            continue
        if key not in result[section]:
            continue
        # 类型转换
        original = result[section][key]
        result[section][key] = _coerce_env_value(env_val, type(original))
    return result


def _coerce_env_value(value: str, target_type: type) -> Any:
    """将环境变量字符串转为目标类型。"""
    if target_type is bool:
        return value.lower() in ("true", "1", "yes")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is list:
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


# ---------------------------------------------------------------------------
# 配置对象（加载时立即解析）
# ---------------------------------------------------------------------------

_conf_raw = _apply_env_overrides(_load_yaml())


def _get(section: str, key: str, default: Any = None) -> Any:
    """安全获取嵌套配置值。"""
    return _conf_raw.get(section, {}).get(key, default)


# --- 输出配置 ---
_output = _conf_raw.get("output", {})
NEWS_OUTPUT_DIR = BASE_DIR / str(_output.get("news_dir", "crawler_data/news"))
NEWS_OUTPUT_PREFIX = str(_output.get("news_prefix", "finance_news"))
CNINFO_OUTPUT_DIR = BASE_DIR / str(_output.get("cninfo_dir", "crawler_data/cninfo"))
CNINFO_OUTPUT_PREFIX = str(_output.get("cninfo_prefix", "cninfo"))

# --- 数据源开关 ---
_sources = _conf_raw.get("sources", {})
ENABLE_FLASH_NEWS = bool(_sources.get("enable_flash_news", True))
ENABLE_CNINFO = bool(_sources.get("enable_cninfo", False))
CNINFO_DATASETS: List[str] = list(_sources.get("cninfo_datasets", ["announcements", "stock_basic", "industry"]))

# --- 去重配置 ---
_dedup = _conf_raw.get("dedup", {})
DEDUP_SIMILARITY_THRESHOLD = float(_dedup.get("similarity_threshold", 0.9))
DEDUP_TIME_WINDOW_MINUTES = int(_dedup.get("time_window_minutes", 120))

# --- 请求配置 ---
_request = _conf_raw.get("request", {})
REQUEST_TIMEOUT = int(_request.get("timeout", 15))
CONCURRENT_WORKERS = int(_request.get("concurrent_workers", 6))

# --- 汇通财经 ---
_fx678 = _conf_raw.get("fx678", {})
FX678_PAGE_LIMIT = int(_fx678.get("page_limit", 40))

# --- 财联社 ---
_cls = _conf_raw.get("cls", {})
CLS_TELEGRAPH_URL = str(_cls.get("telegraph_url", "https://www.cls.cn/v1/roll/get_roll_list"))
CLS_PAGE_LIMIT = int(_cls.get("page_limit", 40))
CLS_PAGE_SIZE = int(_cls.get("page_size", 50))

# --- 证券时报-人民财讯 ---
_stcn = _conf_raw.get("stcn", {})
STCN_KX_URL = str(_stcn.get("kx_url", "https://www.stcn.com/article/list.html?type=kx"))
STCN_PAGE_LIMIT = int(_stcn.get("page_limit", 40))

# --- 金十数据 ---
_jin10 = _conf_raw.get("jin10", {})
JIN10_WEB_FLASH_URL = str(_jin10.get("web_flash_url", "https://www.jin10.com/news/"))
JIN10_WEB_FLASH_API_URL = str(_jin10.get("web_flash_api_url", "https://flash-api.jin10.com/get_flash_list"))
JIN10_FLASH_LIMIT = int(_jin10.get("flash_limit", 1000))
JIN10_PAGE_LIMIT = int(_jin10.get("page_limit", 80))

# --- 华尔街见闻 ---
_wallstreetcn = _conf_raw.get("wallstreetcn", {})
WALLSTREETCN_LIVE_URL = str(_wallstreetcn.get("live_url", "https://api-one-wscn.awtmt.com/apiv1/content/lives"))
WALLSTREETCN_PAGE_LIMIT = int(_wallstreetcn.get("page_limit", 40))
WALLSTREETCN_PAGE_SIZE = int(_wallstreetcn.get("page_size", 20))

# --- 默认运行参数 ---
_default = _conf_raw.get("default", {})
START_DATE = str(_default.get("start_date", "2026-08-08 00:00:00"))
END_DATE = str(_default.get("end_date", "2026-08-10 09:59:59"))
DEFAULT_SOURCE = str(_default.get("source", "all"))
SOURCE_CONCURRENT_WORKERS = int(_default.get("source_concurrent_workers", 5))

# --- 增量爬取配置 ---
_incremental = _conf_raw.get("incremental", {})
INCREMENTAL_ENABLED = bool(_incremental.get("enabled", False))
STATE_DB_PATH = BASE_DIR / str(_incremental.get("state_db", "crawler_data/crawl_state.db"))
ITEM_RETENTION_DAYS = int(_incremental.get("item_retention_days", 30))

# ---------------------------------------------------------------------------
# 新增配置段: API Keys / Pipelines / Filter / 行情 / 资金 / 宏观 / 技术
# ---------------------------------------------------------------------------

# --- API Keys ---
_api_keys = _conf_raw.get("api_keys", {})
TUSHARE_TOKEN = str(_api_keys.get("tushare_token", ""))
TDX_API_KEY = str(_api_keys.get("tdx_api_key", ""))
IFIND_API_KEY = str(_api_keys.get("ifind_api_key", ""))
FINNHUB_API_KEY = str(_api_keys.get("finnhub_api_key", ""))
ALPHAVANTAGE_API_KEY = str(_api_keys.get("alphavantage_api_key", ""))
LLM_API_KEY = str(_api_keys.get("llm_api_key", ""))

# --- Pipeline 开关 ---
_pipelines = _conf_raw.get("pipelines", {})
PIPELINE_FLASH_NEWS = bool(_pipelines.get("flash_news", True))
PIPELINE_CNINFO = bool(_pipelines.get("cninfo", False))
PIPELINE_MARKET_DATA = bool(_pipelines.get("market_data", True))
PIPELINE_FUND_FLOW = bool(_pipelines.get("fund_flow", True))
PIPELINE_MACRO_CALENDAR = bool(_pipelines.get("macro_calendar", True))
PIPELINE_TECHNICAL = bool(_pipelines.get("technical", True))

# --- 分类筛选默认值 ---
_filter_cfg = _conf_raw.get("filter", {})
FILTER_DEFAULT_MARKET = str(_filter_cfg.get("default_market", "all"))
FILTER_DEFAULT_ASSET_CLASS = str(_filter_cfg.get("default_asset_class", "all"))
FILTER_DEFAULT_IMPORTANCE = str(_filter_cfg.get("default_importance", "all"))
# 指定品种 symbol 列表（如 ["GC", "SI", "HSI"]），空列表表示不按品种过滤
FILTER_SYMBOLS: List[str] = list(_filter_cfg.get("symbols", []))

# --- 行情采集配置 ---
MARKET_DATA_CONFIG = _conf_raw.get("market_data", {})
MARKET_DATA_ENABLED = bool(MARKET_DATA_CONFIG.get("enabled", True))
MARKET_DATA_SOURCES = list(MARKET_DATA_CONFIG.get("sources", ["eastmoney", "sina"]))
MARKET_DATA_INTERVAL = int(MARKET_DATA_CONFIG.get("fetch_interval_seconds", 60))
MARKET_DATA_CATEGORIES = MARKET_DATA_CONFIG.get("categories", {})

# --- 资金流向配置 ---
FUND_FLOW_CONFIG = _conf_raw.get("fund_flow", {})
FUND_FLOW_ENABLED = bool(FUND_FLOW_CONFIG.get("enabled", True))
FUND_FLOW_INTERVAL = int(FUND_FLOW_CONFIG.get("fetch_interval_seconds", 300))

# --- 宏观日历配置 ---
MACRO_CALENDAR_CONFIG = _conf_raw.get("macro_calendar", {})
MACRO_CALENDAR_ENABLED = bool(MACRO_CALENDAR_CONFIG.get("enabled", True))
MACRO_IMPORTANCE_FILTER = list(MACRO_CALENDAR_CONFIG.get("importance_filter", ["高", "中"]))
MACRO_COUNTRIES = list(MACRO_CALENDAR_CONFIG.get("countries", ["美国", "中国", "欧元区", "日本"]))

# --- 技术指标配置 ---
TECHNICAL_CONFIG = _conf_raw.get("technical", {})
TECHNICAL_ENABLED = bool(TECHNICAL_CONFIG.get("enabled", True))

# --- 向后兼容别名 ---
OUTPUT_DIR = NEWS_OUTPUT_DIR
OUTPUT_PREFIX = NEWS_OUTPUT_PREFIX


# ---------------------------------------------------------------------------
# 运行时覆盖 API
# ---------------------------------------------------------------------------

def apply_cli_overrides(**kwargs: Any) -> None:
    """用命令行参数动态覆盖模块级配置变量。

    用法:
        config.apply_cli_overrides(
            start_date="2026-08-10 00:00:00",
            fx678_page_limit=20,
            pipeline="market_data",
            market="港股",
            asset_class="贵金属",
        )
    """
    global START_DATE, END_DATE, DEFAULT_SOURCE
    global FX678_PAGE_LIMIT, CLS_PAGE_LIMIT, CLS_PAGE_SIZE
    global STCN_PAGE_LIMIT, JIN10_FLASH_LIMIT, JIN10_PAGE_LIMIT
    global WALLSTREETCN_PAGE_LIMIT, WALLSTREETCN_PAGE_SIZE
    global CONCURRENT_WORKERS, SOURCE_CONCURRENT_WORKERS
    global NEWS_OUTPUT_PREFIX, REQUEST_TIMEOUT
    global ENABLE_FLASH_NEWS, ENABLE_CNINFO, INCREMENTAL_ENABLED
    global PIPELINE_MARKET_DATA, PIPELINE_FUND_FLOW, PIPELINE_MACRO_CALENDAR, PIPELINE_TECHNICAL
    global FILTER_DEFAULT_MARKET, FILTER_DEFAULT_ASSET_CLASS, FILTER_DEFAULT_IMPORTANCE, FILTER_SYMBOLS

    if "start_date" in kwargs:
        START_DATE = str(kwargs["start_date"])
    if "end_date" in kwargs:
        END_DATE = str(kwargs["end_date"])
    if "source" in kwargs:
        DEFAULT_SOURCE = str(kwargs["source"])
    if "fx678_page_limit" in kwargs:
        FX678_PAGE_LIMIT = int(kwargs["fx678_page_limit"])
    if "cls_page_limit" in kwargs:
        CLS_PAGE_LIMIT = int(kwargs["cls_page_limit"])
    if "cls_page_size" in kwargs:
        CLS_PAGE_SIZE = int(kwargs["cls_page_size"])
    if "stcn_page_limit" in kwargs:
        STCN_PAGE_LIMIT = int(kwargs["stcn_page_limit"])
    if "jin10_flash_limit" in kwargs:
        JIN10_FLASH_LIMIT = int(kwargs["jin10_flash_limit"])
    if "jin10_page_limit" in kwargs:
        JIN10_PAGE_LIMIT = int(kwargs["jin10_page_limit"])
    if "wallstreetcn_page_limit" in kwargs:
        WALLSTREETCN_PAGE_LIMIT = int(kwargs["wallstreetcn_page_limit"])
    if "wallstreetcn_page_size" in kwargs:
        WALLSTREETCN_PAGE_SIZE = int(kwargs["wallstreetcn_page_size"])
    if "concurrent_workers" in kwargs:
        CONCURRENT_WORKERS = int(kwargs["concurrent_workers"])
    if "source_concurrent_workers" in kwargs:
        SOURCE_CONCURRENT_WORKERS = int(kwargs["source_concurrent_workers"])
    if "output_prefix" in kwargs:
        NEWS_OUTPUT_PREFIX = str(kwargs["output_prefix"])
    if "request_timeout" in kwargs:
        REQUEST_TIMEOUT = int(kwargs["request_timeout"])
    if "enable_flash_news" in kwargs:
        ENABLE_FLASH_NEWS = bool(kwargs["enable_flash_news"])
    if "enable_cninfo" in kwargs:
        ENABLE_CNINFO = bool(kwargs["enable_cninfo"])
    if "incremental" in kwargs:
        INCREMENTAL_ENABLED = bool(kwargs["incremental"])

    # --- Pipeline 运行时覆盖 ---
    pipeline = kwargs.get("pipeline")
    if pipeline:
        if pipeline == "all":
            PIPELINE_MARKET_DATA = True
            PIPELINE_FUND_FLOW = True
            PIPELINE_MACRO_CALENDAR = True
            PIPELINE_TECHNICAL = True
        elif pipeline == "market":
            PIPELINE_MARKET_DATA = True
            PIPELINE_FUND_FLOW = False
            PIPELINE_MACRO_CALENDAR = False
            PIPELINE_TECHNICAL = False
        elif pipeline == "fundflow":
            PIPELINE_MARKET_DATA = False
            PIPELINE_FUND_FLOW = True
            PIPELINE_MACRO_CALENDAR = False
            PIPELINE_TECHNICAL = False
        elif pipeline == "macro":
            PIPELINE_MARKET_DATA = False
            PIPELINE_FUND_FLOW = False
            PIPELINE_MACRO_CALENDAR = True
            PIPELINE_TECHNICAL = False
        elif pipeline == "technical":
            PIPELINE_MARKET_DATA = False
            PIPELINE_FUND_FLOW = False
            PIPELINE_MACRO_CALENDAR = False
            PIPELINE_TECHNICAL = True

    # --- 筛选条件覆盖 ---
    if "market" in kwargs:
        FILTER_DEFAULT_MARKET = str(kwargs["market"])
    if "asset_class" in kwargs:
        FILTER_DEFAULT_ASSET_CLASS = str(kwargs["asset_class"])
    if "importance" in kwargs:
        FILTER_DEFAULT_IMPORTANCE = str(kwargs["importance"])
    if "symbols" in kwargs and kwargs["symbols"]:
        # 支持字符串（逗号分隔）或列表
        raw = kwargs["symbols"]
        if isinstance(raw, str):
            FILTER_SYMBOLS = [s.strip() for s in raw.split(",") if s.strip()]
        else:
            FILTER_SYMBOLS = list(raw)
