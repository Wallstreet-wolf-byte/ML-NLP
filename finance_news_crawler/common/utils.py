from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def parse_datetime(value: str, *, is_end: bool = False) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if is_end:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed
    except ValueError as exc:
        raise ValueError(f"Unsupported datetime format: {value}") from exc


def clean_text(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s*[\u00A0]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_fx678_content(content: str) -> str:
    content = clean_text(content)
    content = re.sub(r"^【.*?】", "", content).strip()
    content = re.sub(r"下载汇通财经APP，.*?$", "", content).strip()
    content = re.sub(r"^汇通财经(?:APP)?讯[—\-–\s]*(?:【.*?】)?\s*", "", content).strip()
    return content


def fetch_text(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    encoding: Optional[str] = "utf-8",
    retries: int = 2,
    delay: float = 0.5,
) -> Optional[str]:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            response.encoding = encoding or response.apparent_encoding
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)
    print(f"Request failed: {url} ({last_error})")
    return None


def save_json(records: Iterable[Dict[str, Any]], output_dir: Path, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{prefix}_{timestamp}.json"
    data: List[Dict[str, Any]] = list(records)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path


def sort_records_by_publish_time(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(records, key=_sort_publish_time_key, reverse=True)


def _sort_publish_time_key(record: Dict[str, Any]) -> tuple[bool, datetime]:
    publish_time = str(record.get("publish_time") or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return True, datetime.strptime(publish_time, fmt)
        except ValueError:
            pass
    return False, datetime.min


def env_value(name: str) -> str:
    return os.environ.get(name, "").strip()
