"""
贵金属期货情绪指数构建脚本

功能：
1. 单条新闻情绪打分（基于词典的词频法 + 否定词处理）
2. 按交易日聚合生成日度情绪指数
3. 计算多维度情绪特征：
   - 情绪强度（sentiment intensity）：正面词数 - 负面词数
   - 情绪一致系数（sentiment consistency）：当日新闻情绪方向的一致性
   - 情绪波动率（sentiment volatility）：一段时间内情绪指数的标准差

用法：
    # 对单条新闻打分
    python sentiment_scorer.py --text "美联储降息，黄金大涨"

    # 对一批JSON新闻数据构建日度情绪指数
    python sentiment_scorer.py --input ./news_data --output ./sentiment_index.xlsx

    # 指定词典目录
    python sentiment_scorer.py --dict ../dicts --input ./news.json
"""

import os
import re
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
DICTS_DIR = BASE_DIR.parent / "dicts"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 否定词窗口：否定词出现在情绪词前 N 个词范围内时，翻转极性
NEGATION_WINDOW = 3


class SentimentScorer:
    """基于词典的情绪打分器"""

    def __init__(self, dict_dir=None):
        """
        初始化打分器
        Args:
            dict_dir: 词典目录，需包含 positive.txt, negative.txt, negation.txt
        """
        dict_dir = Path(dict_dir) if dict_dir else DICTS_DIR

        self.positive_words = self._load_dict(dict_dir / "positive.txt")
        self.negative_words = self._load_dict(dict_dir / "negative.txt")
        self.negation_words = self._load_dict(dict_dir / "negation.txt")

        # 按词长倒序排列，避免短词先匹配了长词的一部分
        self.positive_sorted = sorted(self.positive_words, key=len, reverse=True)
        self.negative_sorted = sorted(self.negative_words, key=len, reverse=True)
        self.negation_sorted = sorted(self.negation_words, key=len, reverse=True)

        print(f"[词典] 正面: {len(self.positive_words)} 词")
        print(f"[词典] 负面: {len(self.negative_words)} 词")
        print(f"[词典] 否定词: {len(self.negation_words)} 词")

    @staticmethod
    def _load_dict(filepath):
        """加载词典文件"""
        words = set()
        if not filepath.exists():
            return words
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    words.add(word)
        return words

    def _find_emotion_words(self, text, word_list):
        """在文本中查找情绪词，返回 [(词, 起始位置), ...]"""
        found = []
        for word in word_list:
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                found.append((word, idx))
                start = idx + len(word)
        # 按位置排序
        found.sort(key=lambda x: x[1])
        return found

    def _has_negation_before(self, text, pos, window=NEGATION_WINDOW):
        """
        检查情绪词前面 window 个词范围内是否有否定词
        简化处理：取情绪词前 window*2 个字符，看是否包含否定词
        """
        prefix = text[max(0, pos - window * 4): pos]
        for neg_word in self.negation_words:
            if neg_word in prefix:
                return True
        return False

    def score_text(self, text):
        """
        对单条文本做情绪打分

        Args:
            text: 输入文本

        Returns:
            dict: {
                'score': float,           # 净情绪得分（-1到1之间）
                'positive_count': int,    # 正面词数量（含否定翻转后）
                'negative_count': int,    # 负面词数量（含否定翻转后）
                'positive_words': list,   # 命中的正面词
                'negative_words': list,   # 命中的负面词
                'negated_positive': list, # 被否定的正面词（实际算负面）
                'negated_negative': list, # 被否定的负面词（实际算正面）
                'total_words': int,       # 文本总字数
            }
        """
        if not text or len(text.strip()) == 0:
            return {
                "score": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "positive_words": [],
                "negative_words": [],
                "negated_positive": [],
                "negated_negative": [],
                "total_words": 0,
            }

        text = str(text).strip()

        # 找正面词
        pos_matches = self._find_emotion_words(text, self.positive_sorted)
        # 找负面词
        neg_matches = self._find_emotion_words(text, self.negative_sorted)

        positive_words = []
        negative_words = []
        negated_positive = []  # 被否定的正面词 → 算负面
        negated_negative = []  # 被否定的负面词 → 算正面

        for word, pos in pos_matches:
            if self._has_negation_before(text, pos):
                negated_positive.append(word)
                negative_words.append(f"[否定]{word}")
            else:
                positive_words.append(word)

        for word, pos in neg_matches:
            if self._has_negation_before(text, pos):
                negated_negative.append(word)
                positive_words.append(f"[否定]{word}")
            else:
                negative_words.append(word)

        pos_count = len(positive_words)
        neg_count = len(negative_words)
        total = pos_count + neg_count

        # 标准化得分：(正面-负面)/(正面+负面)，范围 [-1, 1]
        if total == 0:
            score = 0.0
        else:
            score = (pos_count - neg_count) / total

        return {
            "score": round(score, 4),
            "positive_count": pos_count,
            "negative_count": neg_count,
            "positive_words": positive_words,
            "negative_words": negative_words,
            "negated_positive": negated_positive,
            "negated_negative": negated_negative,
            "total_words": len(text),
        }


class SentimentIndexBuilder:
    """情绪指数构建器：从新闻数据构建日度情绪指数"""

    def __init__(self, scorer=None, dict_dir=None):
        self.scorer = scorer or SentimentScorer(dict_dir)

    def score_news_list(self, news_list):
        """
        对一批新闻打分

        Args:
            news_list: [{'text': '...', 'time': '2026-08-01 10:30', ...}, ...]

        Returns:
            list: 每条新闻增加了情绪分字段
        """
        scored = []
        for item in news_list:
            text = item.get("content", "") or item.get("text", "") or item.get("title", "")
            result = self.scorer.score_text(text)
            item_copy = dict(item)
            item_copy.update(result)
            scored.append(item_copy)

        pos_count = sum(1 for s in scored if s["score"] > 0)
        neg_count = sum(1 for s in scored if s["score"] < 0)
        neu_count = sum(1 for s in scored if s["score"] == 0)

        print(f"[打分] 共 {len(scored)} 条新闻")
        print(f"  正面: {pos_count}, 负面: {neg_count}, 中性: {neu_count}")
        if scored:
            avg_score = sum(s["score"] for s in scored) / len(scored)
            print(f"  平均情绪得分: {avg_score:.4f}")

        return scored

    def build_daily_index(self, scored_news):
        """
        按交易日聚合成日度情绪指数

        计算三个特征：
        1. 情绪强度 (sentiment_intensity): 日度平均情绪得分
        2. 情绪一致系数 (sentiment_consistency): 当日新闻情绪方向的一致性比例
           = max(正面占比, 负面占比) / (正面占比 + 负面占比)，范围 [0.5, 1]
        3. 情绪波动率 (sentiment_volatility): 当日各条新闻情绪得分的标准差

        Args:
            scored_news: 带有 score 和 time 字段的新闻列表

        Returns:
            list: 每日的情绪指数记录
        """
        # 按日期分组
        daily_news = defaultdict(list)
        for item in scored_news:
            time_str = item.get("time", "") or item.get("pub_time", "") or item.get("date", "")
            if not time_str:
                continue
            # 尝试解析日期
            try:
                if " " in time_str:
                    date_part = time_str.split(" ")[0]
                else:
                    date_part = time_str[:10]
                # 标准化为 YYYY-MM-DD
                date_obj = None
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                    try:
                        date_obj = datetime.strptime(date_part, fmt)
                        break
                    except:
                        continue
                if date_obj:
                    date_key = date_obj.strftime("%Y-%m-%d")
                    daily_news[date_key].append(item)
            except:
                continue

        # 计算每日指数
        daily_index = []
        for date in sorted(daily_news.keys()):
            day_news = daily_news[date]
            scores = [n["score"] for n in day_news]
            n_total = len(scores)
            n_positive = sum(1 for s in scores if s > 0.01)
            n_negative = sum(1 for s in scores if s < -0.01)
            n_neutral = n_total - n_positive - n_negative

            # 1. 情绪强度
            intensity = sum(scores) / n_total if n_total > 0 else 0.0

            # 2. 情绪一致系数
            if n_positive + n_negative == 0:
                consistency = 0.5  # 全中性，一致性最低
            else:
                consistency = max(n_positive, n_negative) / (n_positive + n_negative)

            # 3. 情绪波动率（标准差）
            if n_total > 1:
                mean_score = intensity
                variance = sum((s - mean_score) ** 2 for s in scores) / (n_total - 1)
                volatility = variance ** 0.5
            else:
                volatility = 0.0

            daily_index.append({
                "date": date,
                "news_count": n_total,
                "positive_count": n_positive,
                "negative_count": n_negative,
                "neutral_count": n_neutral,
                "sentiment_intensity": round(intensity, 6),
                "sentiment_consistency": round(consistency, 4),
                "sentiment_volatility": round(volatility, 6),
            })

        print(f"\n[日度指数] 共 {len(daily_index)} 个交易日")
        return daily_index

    def build_from_json_dir(self, input_dir, output_path=None):
        """
        从 JSON 新闻数据目录构建情绪指数

        Args:
            input_dir: 包含 JSON 新闻文件的目录
            output_path: 输出 Excel 路径
        """
        input_dir = Path(input_dir)
        all_news = []

        # 加载所有 JSON 文件
        pattern = str(input_dir / "**" / "*.json")
        for filepath in glob.glob(pattern, recursive=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    all_news.extend(data)
                elif isinstance(data, dict):
                    all_news.append(data)
            except Exception as e:
                print(f"  跳过 {filepath}: {e}")

        print(f"[加载] 共 {len(all_news)} 条新闻")

        if len(all_news) == 0:
            print("[警告] 没有加载到新闻数据")
            return []

        # 打分
        scored = self.score_news_list(all_news)

        # 构建日度指数
        daily_index = self.build_daily_index(scored)

        # 保存
        if output_path is None:
            output_path = OUTPUT_DIR / "sentiment_index.xlsx"

        import pandas as pd
        df = pd.DataFrame(daily_index)
        df.to_excel(str(output_path), index=False)
        print(f"\n[保存] 日度情绪指数: {output_path}")

        # 同时保存打分后的新闻明细
        detail_path = Path(output_path).parent / f"{Path(output_path).stem}_detail.xlsx"
        df_detail = pd.DataFrame(scored)
        # 只保留关键字段
        keep_cols = ["time", "score", "positive_count", "negative_count",
                     "positive_words", "negative_words", "total_words"]
        if "content" in df_detail.columns:
            keep_cols.insert(0, "content")
        if "title" in df_detail.columns:
            keep_cols.insert(0, "title")
        df_detail[keep_cols].to_excel(str(detail_path), index=False)
        print(f"[保存] 新闻打分明细: {detail_path}")

        return daily_index


def main():
    parser = argparse.ArgumentParser(description="贵金属期货情绪指数构建")
    parser.add_argument("--text", type=str, default=None,
                        help="单条文本打分（快速测试）")
    parser.add_argument("--input", type=str, default=None,
                        help="输入新闻数据目录（JSON格式）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出情绪指数 Excel 路径")
    parser.add_argument("--dict", type=str, default=None,
                        help="词典目录，默认 ../dicts")
    args = parser.parse_args()

    print("=" * 60)
    print("  贵金属期货情绪指数构建工具")
    print("=" * 60)

    # 初始化打分器
    scorer = SentimentScorer(args.dict)

    if args.text:
        # 单条文本打分模式
        print("\n--- 单条文本打分 ---")
        print(f"输入: {args.text}")
        result = scorer.score_text(args.text)
        print(f"\n情绪得分: {result['score']}")
        print(f"正面词 ({result['positive_count']}): {result['positive_words']}")
        print(f"负面词 ({result['negative_count']}): {result['negative_words']}")
        print(f"被否定正面词: {result['negated_positive']}")
        print(f"被否定负面词: {result['negated_negative']}")
        return

    if args.input:
        # 批量构建指数模式
        print("\n--- 构建日度情绪指数 ---")
        builder = SentimentIndexBuilder(scorer)
        builder.build_from_json_dir(args.input, args.output)
        return

    # 没有参数，打印帮助
    parser.print_help()


if __name__ == "__main__":
    main()
