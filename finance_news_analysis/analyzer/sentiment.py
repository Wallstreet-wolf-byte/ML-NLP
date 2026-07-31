# ============================================================
# 情绪分析器（增强版）
# 基于金融关键词词典 + 否定词处理
# 判断新闻情绪：利好/利空/中性
# ============================================================

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DICTS_DIR


# --- 词典 ---
_positive_words = set()
_negative_words = set()
_negation_words = set()

# 否定词前的检查窗口（往前看几个字符）
_NEGATION_WINDOW = 4


def _load_dict(filepath: str) -> set:
    """从文件加载词典，每行一个词"""
    words = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    words.add(word)
    except FileNotFoundError:
        print(f"  [警告] 词典文件不存在: {filepath}")
    return words


def init_dicts():
    """初始化情绪词典（首次调用时加载）"""
    global _positive_words, _negative_words, _negation_words
    if not _positive_words:
        _positive_words = _load_dict(os.path.join(DICTS_DIR, "positive.txt"))
        _negative_words = _load_dict(os.path.join(DICTS_DIR, "negative.txt"))
        _negation_words = _load_dict(os.path.join(DICTS_DIR, "negation.txt"))
        print(f"  [词典] 利好词: {len(_positive_words)} 个")
        print(f"  [词典] 利空词: {len(_negative_words)} 个")
        print(f"  [词典] 否定词: {len(_negation_words)} 个")


def _check_negation(text: str, pos: int) -> bool:
    """
    检查关键词前 _NEGATION_WINDOW 个字符内是否有否定词
    如 "不增长" "未盈利" "没有突破" → 否定
    """
    start = max(0, pos - _NEGATION_WINDOW)
    prefix = text[start:pos]
    for neg in _negation_words:
        if neg in prefix:
            return True
    return False


def analyze_sentiment(text: str) -> tuple:
    """
    分析文本情绪（增强版，支持否定词）
    返回: (情绪标签, 利好词数, 利空词数, 命中的关键词列表)
    """
    init_dicts()

    if not text:
        return ("中性", 0, 0, [])

    positive_hits = []
    negative_hits = []

    # 扫描利好词（考虑否定词翻转）
    for word in _positive_words:
        start = 0
        while True:
            pos = text.find(word, start)
            if pos == -1:
                break
            # 检查前面是否有否定词
            if _check_negation(text, pos):
                # 否定 + 利好 = 利空
                negative_hits.append(f"否定+{word}")
            else:
                positive_hits.append(word)
            start = pos + len(word)

    # 扫描利空词（考虑否定词翻转）
    for word in _negative_words:
        start = 0
        while True:
            pos = text.find(word, start)
            if pos == -1:
                break
            if _check_negation(text, pos):
                # 否定 + 利空 = 利好（如 "没有亏损"）
                positive_hits.append(f"否定+{word}")
            else:
                negative_hits.append(word)
            start = pos + len(word)

    pos_score = len(positive_hits)
    neg_score = len(negative_hits)

    # 判断情绪
    if pos_score > neg_score and pos_score > 0:
        sentiment = "利好"
    elif neg_score > pos_score and neg_score > 0:
        sentiment = "利空"
    elif pos_score > 0 and neg_score > 0 and pos_score == neg_score:
        sentiment = "中性"
    else:
        sentiment = "中性"

    all_hits = positive_hits + negative_hits
    return (sentiment, pos_score, neg_score, all_hits)