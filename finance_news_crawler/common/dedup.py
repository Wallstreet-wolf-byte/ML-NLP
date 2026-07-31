from __future__ import annotations

import hashlib
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from common.utils import clean_text
from config import DEDUP_SIMILARITY_THRESHOLD, DEDUP_TIME_WINDOW_MINUTES


_SOURCE_PREFIX_PATTERNS = (
    r"^金十数据\s*\d{1,2}月\d{1,2}日讯[，,、\s]*",
    r"^金十数据\s*\d{4}-\d{2}-\d{2}日讯[，,、\s]*",
    r"^财联社\s*\d{1,2}月\d{1,2}日电[，,、\s]*",
    r"^财联社\s*\d{4}-\d{2}-\d{2}日电[，,、\s]*",
    r"^人民财讯\s*\d{1,2}月\d{1,2}日电[，,、\s]*",
    r"^人民财讯\s*\d{4}-\d{2}-\d{2}日电[，,、\s]*",
    r"^新华社\s*\d{1,2}月\d{1,2}日电[，,、\s]*",
    r"^新华社\s*\d{4}-\d{2}-\d{2}日电[，,、\s]*",
)


def deduplicate_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped: List[Dict[str, str]] = []
    signatures: List[Tuple[str, str, str, Optional[datetime]]] = []

    for record in records:
        key = make_dedup_key(record)
        if key in seen:
            continue

        signature = make_similarity_signature(record)
        if any(is_near_duplicate(signature, existing) for existing in signatures):
            continue

        seen.add(key)
        deduped.append(record)
        signatures.append(signature)

    return deduped


def make_dedup_key(record: Dict[str, str]) -> str:
    title = normalize_news_text(record.get("title", ""))
    content = normalize_news_text(record.get("content", ""))
    publish_time = normalize_news_text(record.get("publish_time", ""))
    source = normalize_news_text(record.get("source", ""))

    if title and content:
        basis = f"{title}\n{content}"
    elif title:
        basis = title
    else:
        basis = content

    if not basis:
        basis = f"{source}\n{publish_time}"

    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def normalize_news_text(text: str) -> str:
    value = clean_text(str(text or ""))
    value = strip_common_prefixes(value)
    value = re.sub(r"^[【\[][^】\]]{2,120}[】\]]\s*", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    value = re.sub(r"\s+", "", value)
    return value.strip()


def strip_common_prefixes(text: str) -> str:
    value = text
    for pattern in _SOURCE_PREFIX_PATTERNS:
        value = re.sub(pattern, "", value)
    return clean_text(value)


def make_similarity_signature(record: Dict[str, str]) -> Tuple[str, str, str, Optional[datetime]]:
    title = normalize_news_text(record.get("title", ""))
    content = normalize_news_text(record.get("content", ""))
    combined = content if content == title else f"{title}{content}"
    return title, content, combined, parse_publish_time(record.get("publish_time", ""))


def is_near_duplicate(
    current: Tuple[str, str, str, Optional[datetime]],
    existing: Tuple[str, str, str, Optional[datetime]],
) -> bool:
    current_title, current_content, current_combined, current_time = current
    existing_title, existing_content, existing_combined, existing_time = existing

    if not within_time_window(current_time, existing_time):
        return False

    if min(len(current_combined), len(existing_combined)) < 16:
        return False

    combined_ratio = text_similarity(current_combined, existing_combined)
    if combined_ratio >= DEDUP_SIMILARITY_THRESHOLD:
        return True

    title_ratio = text_similarity(current_title, existing_title)
    content_ratio = text_similarity(current_content, existing_content)
    return title_ratio >= 0.92 and content_ratio >= 0.85


def within_time_window(current_time: Optional[datetime], existing_time: Optional[datetime]) -> bool:
    if not current_time or not existing_time:
        return True
    delta_minutes = abs((current_time - existing_time).total_seconds()) / 60
    return delta_minutes <= DEDUP_TIME_WINDOW_MINUTES


def text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def parse_publish_time(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(str(value or ""), fmt)
        except ValueError:
            pass
    return None
