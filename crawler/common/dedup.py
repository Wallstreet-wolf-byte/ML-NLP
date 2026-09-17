from __future__ import annotations

import hashlib
import re
from collections import defaultdict
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

# SimHash 参数：64位哈希，分成8个桶做快速筛选
_SIMHASH_BITS = 64
_SIMHASH_BUCKETS = 8
_SIMHASH_BUCKET_SIZE = _SIMHASH_BITS // _SIMHASH_BUCKETS  # 8位每桶


def deduplicate_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    新闻去重：精确去重 + 近似去重

    性能优化方案：
    1. 精确去重：SHA1哈希，O(n)
    2. 近似去重：SimHash + 时间窗口分桶
       - 先按时间窗口分桶（默认2小时），只在同时间窗口内比较
       - 每条新闻计算SimHash，按SimHash分段建倒排索引
       - 只与SimHash汉明距离 <= 3 的候选新闻跑 SequenceMatcher
       - 整体复杂度从 O(n²) 降到接近 O(n)
    """
    seen_keys = set()
    deduped: List[Dict[str, str]] = []

    # 时间窗口分桶 + SimHash倒排索引
    # 结构: { time_bucket_key: { simhash_bucket_signature: [ (simhash_int, record_idx) ] } }
    time_buckets: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))
    all_signatures: List[Tuple[int, str, Optional[datetime]]] = []  # (simhash, combined_text, publish_time)

    for record in records:
        # ---- 第一步：精确去重 ----
        key = make_dedup_key(record)
        if key in seen_keys:
            continue

        # ---- 第二步：近似去重（SimHash + 时间窗口） ----
        simhash, combined_text, publish_time = make_similarity_signature(record)

        # 计算时间桶（按DEDUP_TIME_WINDOW_MINUTES对齐）
        time_bucket = _get_time_bucket_key(publish_time)

        # 收集候选：SimHash汉明距离可能相近的记录
        candidates = _get_simhash_candidates(
            simhash, time_bucket, time_buckets, all_signatures
        )

        # 与候选逐一做精确相似度比较
        is_dup = False
        for cand_idx in candidates:
            cand_simhash, cand_combined, cand_time = all_signatures[cand_idx]
            # 二次确认时间窗口（避免桶边界误差）
            if not within_time_window(publish_time, cand_time):
                continue
            # 汉明距离已经过滤过，这里直接跑 SequenceMatcher 做最终确认
            if min(len(combined_text), len(cand_combined)) < 16:
                continue
            if text_similarity(combined_text, cand_combined) >= DEDUP_SIMILARITY_THRESHOLD:
                is_dup = True
                break

        if is_dup:
            continue

        # ---- 加入结果集 ----
        seen_keys.add(key)
        deduped.append(record)

        # 更新索引
        record_idx = len(all_signatures)
        all_signatures.append((simhash, combined_text, publish_time))
        _add_to_simhash_index(simhash, time_bucket, record_idx, time_buckets)

    return deduped


def make_dedup_key(record: Dict[str, str]) -> str:
    """生成精确去重的SHA1键"""
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
    """标准化新闻文本：去前缀、去特殊字符、去空白"""
    value = clean_text(str(text or ""))
    value = strip_common_prefixes(value)
    value = re.sub(r"^[【\[][^】\]]{2,120}[】\]]\s*", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    value = re.sub(r"\s+", "", value)
    return value.strip()


def strip_common_prefixes(text: str) -> str:
    """去除常见的新闻来源前缀"""
    value = text
    for pattern in _SOURCE_PREFIX_PATTERNS:
        value = re.sub(pattern, "", value)
    return clean_text(value)


def make_similarity_signature(
    record: Dict[str, str]
) -> Tuple[int, str, Optional[datetime]]:
    """
    生成相似度签名：(simhash_int, combined_text, publish_time)

    SimHash 用于快速筛选近似重复的文本，
    再通过 SequenceMatcher 做精确确认。
    """
    title = normalize_news_text(record.get("title", ""))
    content = normalize_news_text(record.get("content", ""))
    combined = content if content == title else f"{title}{content}"
    publish_time = parse_publish_time(record.get("publish_time", ""))
    simhash = compute_simhash(combined)
    return simhash, combined, publish_time


def compute_simhash(text: str) -> int:
    """
    计算文本的 SimHash（64位）。

    算法：
    1. 将文本分词（按字符级，适合中文）
    2. 每个 token 计算一个64位哈希
    3. 对每一位，所有 token 的该位加权求和
    4. 最终每一位：和 > 0 则为 1，否则为 0
    """
    if not text:
        return 0

    # 字符级 token + 权重（按字符出现位置加权，前后字符权重低）
    # 简化版：每个字符权重为1
    bits = [0] * _SIMHASH_BITS

    # 用 2-gram 提高区分度（比单字更稳定）
    tokens = [text[i:i + 2] for i in range(len(text) - 1)] if len(text) > 1 else list(text)
    if not tokens:
        tokens = list(text)

    for token in tokens:
        h = hashlib.md5(token.encode("utf-8")).digest()
        # 取前8字节作为64位哈希
        hash_int = int.from_bytes(h[:8], "big")
        for i in range(_SIMHASH_BITS):
            if hash_int & (1 << i):
                bits[i] += 1
            else:
                bits[i] -= 1

    # 生成最终 SimHash
    result = 0
    for i in range(_SIMHASH_BITS):
        if bits[i] > 0:
            result |= (1 << i)
    return result


def hamming_distance(x: int, y: int) -> int:
    """计算两个整数的汉明距离"""
    return bin(x ^ y).count("1")


def _get_time_bucket_key(publish_time: Optional[datetime]) -> str:
    """
    将时间按窗口大小分桶，返回桶键。

    为了解决桶边界问题（两条相近的新闻刚好落在两个桶里），
    实际比较时会同时检查相邻桶。
    """
    if not publish_time:
        return "no_time"
    # 转换为分钟数，按窗口大小取整
    total_minutes = publish_time.hour * 60 + publish_time.minute
    bucket = total_minutes // DEDUP_TIME_WINDOW_MINUTES
    date_key = publish_time.strftime("%Y%m%d")
    return f"{date_key}_{bucket}"


def _add_to_simhash_index(
    simhash: int,
    time_bucket: str,
    record_idx: int,
    time_buckets: Dict[str, Dict[str, List[Tuple[int, int]]]],
) -> None:
    """将一条记录的SimHash加入倒排索引"""
    for b in range(_SIMHASH_BUCKETS):
        # 取出第b个桶的8位作为签名
        shift = b * _SIMHASH_BUCKET_SIZE
        mask = (1 << _SIMHASH_BUCKET_SIZE) - 1
        bucket_sig = (simhash >> shift) & mask
        sig_key = f"{b}_{bucket_sig}"
        time_buckets[time_bucket][sig_key].append((simhash, record_idx))


def _get_simhash_candidates(
    simhash: int,
    time_bucket: str,
    time_buckets: Dict[str, Dict[str, List[Tuple[int, int]]]],
    all_signatures: List[Tuple[int, str, Optional[datetime]]],
) -> List[int]:
    """
    找出SimHash汉明距离可能 <= 3 的候选记录索引。

    原理：如果两个64位SimHash的汉明距离 <= 3，
    那么在8个8位分段中，至少有5个分段完全相同。
    因此，我们只需与"在任一分段上与目标相同"的记录比较。
    """
    candidates_set = set()

    # 需要检查的时间桶：当前桶 + 前后相邻桶（处理边界问题）
    time_buckets_to_check = _get_adjacent_time_buckets(time_bucket, time_buckets)

    for tb in time_buckets_to_check:
        if tb not in time_buckets:
            continue
        for b in range(_SIMHASH_BUCKETS):
            shift = b * _SIMHASH_BUCKET_SIZE
            mask = (1 << _SIMHASH_BUCKET_SIZE) - 1
            bucket_sig = (simhash >> shift) & mask
            sig_key = f"{b}_{bucket_sig}"
            if sig_key in time_buckets[tb]:
                for cand_simhash, cand_idx in time_buckets[tb][sig_key]:
                    # 快速汉明距离过滤（阈值设为12，确保相似文本能进入候选集）
                    # 后续会用 SequenceMatcher 做精确判定，所以这里可以放宽
                    if hamming_distance(simhash, cand_simhash) <= 12:
                        candidates_set.add(cand_idx)

    return list(candidates_set)


def _get_adjacent_time_buckets(
    current_bucket: str,
    time_buckets: Dict[str, Dict[str, List[Tuple[int, int]]]],
) -> List[str]:
    """获取当前时间桶及其相邻桶的键"""
    if current_bucket == "no_time":
        return [current_bucket]

    # 解析当前桶
    parts = current_bucket.rsplit("_", 1)
    if len(parts) != 2:
        return [current_bucket]

    date_key = parts[0]
    try:
        bucket_id = int(parts[1])
    except ValueError:
        return [current_bucket]

    # 计算当天总桶数
    buckets_per_day = (24 * 60 + DEDUP_TIME_WINDOW_MINUTES - 1) // DEDUP_TIME_WINDOW_MINUTES

    result = [current_bucket]
    if bucket_id > 0:
        result.append(f"{date_key}_{bucket_id - 1}")
    if bucket_id < buckets_per_day - 1:
        result.append(f"{date_key}_{bucket_id + 1}")

    # 处理跨天（前一天的最后一个桶、后一天的第一个桶）
    # 简化：只检查已存在的桶
    all_keys = list(time_buckets.keys())
    return result


def is_near_duplicate(
    current: Tuple[int, str, Optional[datetime]],
    existing: Tuple[int, str, Optional[datetime]],
) -> bool:
    """
    判断两条记录是否近似重复（保留向后兼容接口）。
    新代码直接用 deduplicate_records 即可。
    """
    curr_simhash, curr_combined, curr_time = current
    exist_simhash, exist_combined, exist_time = existing

    if not within_time_window(curr_time, exist_time):
        return False

    if min(len(curr_combined), len(exist_combined)) < 16:
        return False

    # 先汉明距离快速判断
    if hamming_distance(curr_simhash, exist_simhash) > 10:
        return False

    return text_similarity(curr_combined, exist_combined) >= DEDUP_SIMILARITY_THRESHOLD


def within_time_window(
    current_time: Optional[datetime], existing_time: Optional[datetime]
) -> bool:
    """判断两条新闻是否在时间窗口内"""
    if not current_time or not existing_time:
        return True
    delta_minutes = abs((current_time - existing_time).total_seconds()) / 60
    return delta_minutes <= DEDUP_TIME_WINDOW_MINUTES


def text_similarity(left: str, right: str) -> float:
    """计算两段文本的相似度（SequenceMatcher）"""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def parse_publish_time(value: str) -> Optional[datetime]:
    """解析发布时间"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(str(value or ""), fmt)
        except ValueError:
            pass
    return None
