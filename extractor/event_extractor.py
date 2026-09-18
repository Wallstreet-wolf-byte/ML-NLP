"""
贵金属期货事件抽取器

功能：
将非结构化财经新闻转化为结构化事件数据，输出三级标注：
  - 事件类型（10类定价驱动因子）
  - 方向（利多/利空/中性）
  - 程度（强/中/弱/不确定）

核心思路：
  基于事件本体的触发词匹配 + 程度修饰词识别 + 否定词/反转词处理
  不依赖机器学习模型，纯规则驱动，可解释、速度快

关键改进：
  1. 长词优先匹配（短语级触发词优先级高于单词）
  2. 程度修饰词分前置/后置两类处理
  3. 反转词规则：匹配到触发词后检查前后是否有反转模式
  4. 否定词窗口检测（支持"不加息"等前缀否定）

用法：
    python event_extractor.py --text "美联储宣布加息25个基点，金价承压下跌"
    python event_extractor.py --input ./news_data --output ./events.json
"""

import logging
import json
import glob
import argparse
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
ONTOLOGY_PATH = BASE_DIR / "ontology.json"
NEGATION_PATH = BASE_DIR.parent / "dicts" / "negation.txt"

# 日志配置
logger = logging.getLogger("event_extractor")


class EventExtractor:
    """基于规则的事件抽取器"""

    def __init__(self, ontology_path=None, negation_path=None):
        """
        初始化事件抽取器
        Args:
            ontology_path: 事件本体JSON路径
            negation_path: 否定词表路径（兼容旧版，新本体已包含反转词）
        """
        ontology_path = ontology_path or ONTOLOGY_PATH
        negation_path = negation_path or NEGATION_PATH

        # 加载事件本体
        with open(ontology_path, "r", encoding="utf-8") as f:
            self.ontology = json.load(f)

        self.event_types = self.ontology["event_types"]
        self.degree_config = self.ontology.get("degree_modifiers", {})
        self.reversal_config = self.ontology.get("reversal_patterns", {})

        # 从本体读取品种实体（如果有）
        self.commodity_entities = self.ontology.get(
            "commodity_entities",
            self._default_commodity_entities()
        )

        # 加载否定词（从本体 + 旧文件补充）
        self.negation_words = set()
        if negation_path.exists():
            with open(negation_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        self.negation_words.add(word)
        # 本体中的否定词优先级更高
        for w in self.reversal_config.get("negation_words", []):
            self.negation_words.add(w)

        # 预计算触发词索引
        self._build_trigger_index()

        # 预计算反转词列表（按长度倒序，长词优先）
        self._build_reversal_index()

        # 预计算程度词列表（前置/后置分开，按长度倒序）
        self._build_degree_index()

        bullish_count = sum(len(v["bullish_triggers"]) for v in self.event_types.values())
        bearish_count = sum(len(v["bearish_triggers"]) for v in self.event_types.values())
        logger.info(
            f"事件抽取器初始化完成: {len(self.event_types)}类事件, "
            f"利多触发词{bullish_count}个, 利空触发词{bearish_count}个"
        )

    @staticmethod
    def _default_commodity_entities():
        """默认品种实体（向后兼容）"""
        return {
            "gold": [
                "黄金", "金价", "沪金", "伦敦金", "现货黄金", "COMEX黄金",
                "COMEX金", "AU", "Au", "黄金期货", "黄金ETF", "金条",
                "金币", "金饰", "金市", "贵金属"
            ],
            "silver": [
                "白银", "银价", "沪银", "现货白银", "COMEX白银", "COMEX银",
                "AG", "Ag", "白银期货", "白银ETF", "银饰", "银市"
            ],
        }

    def _build_trigger_index(self):
        """构建触发词索引：{触发词: (事件类型, 方向)}，按词长倒序"""
        self.trigger_index = {}
        for etype_id, etype_data in self.event_types.items():
            for word in etype_data["bullish_triggers"]:
                if word not in self.trigger_index:
                    self.trigger_index[word] = (etype_id, "bullish")
            for word in etype_data["bearish_triggers"]:
                if word not in self.trigger_index:
                    self.trigger_index[word] = (etype_id, "bearish")

        # 按词长倒序，优先匹配长词（短语级触发词优先于单词）
        self.sorted_triggers = sorted(
            self.trigger_index.keys(), key=len, reverse=True
        )

    def _build_reversal_index(self):
        """构建反转词索引：前置反转词、后置反转词，均按长度倒序"""
        self.prefix_reversals = sorted(
            self.reversal_config.get("prefix_reversals", []),
            key=len, reverse=True
        )
        self.suffix_reversals = sorted(
            self.reversal_config.get("suffix_reversals", []),
            key=len, reverse=True
        )
        # 按长度倒序的否定词
        self.sorted_negations = sorted(list(self.negation_words), key=len, reverse=True)

    def _build_degree_index(self):
        """
        构建程度词索引：
        - prefix_degree: {degree_level: [words_sorted_by_length]}
        - suffix_degree: {degree_level: [words_sorted_by_length]}

        程度等级优先级：strong > uncertain > weakening > moderate
        """
        self.prefix_degree = {}
        self.suffix_degree = {}

        for level in ["strong", "uncertain", "weakening", "moderate"]:
            level_data = self.degree_config.get(level, {})
            if isinstance(level_data, dict):
                prefix_words = level_data.get("prefix", [])
                suffix_words = level_data.get("suffix", [])
            else:
                # 兼容旧格式（平铺列表）
                prefix_words = level_data
                suffix_words = []

            self.prefix_degree[level] = sorted(prefix_words, key=len, reverse=True)
            self.suffix_degree[level] = sorted(suffix_words, key=len, reverse=True)

    def _find_triggers(self, text):
        """
        在文本中查找所有触发词，返回 [(词, 起始位置, 结束位置, 事件类型, 方向), ...]

        匹配规则：
        1. 长词优先（已通过sorted_triggers保证）
        2. 不重叠匹配（used_positions记录已用字符位置）
        """
        found = []
        used_positions = set()  # 避免重叠匹配

        for trigger in self.sorted_triggers:
            start = 0
            while True:
                idx = text.find(trigger, start)
                if idx == -1:
                    break
                end = idx + len(trigger)
                # 检查是否与已匹配的位置重叠
                overlap = any(idx <= p < end for p in used_positions)
                if not overlap:
                    etype, direction = self.trigger_index[trigger]
                    found.append((trigger, idx, end, etype, direction))
                    for p in range(idx, end):
                        used_positions.add(p)
                start = end

        # 按位置排序
        found.sort(key=lambda x: x[1])
        return found

    def _check_reversal(self, text, trigger_start, trigger_end):
        """
        检查触发词前后是否有反转模式，返回 (是否反转, 反转词)

        检查顺序：
        1. 前缀反转短语（如"暂停加息"、"不加息"）
        2. 后缀反转短语（如"加息暂停"、"加息预期降温"）
        3. 紧邻的否定词（如"不"、"未" + 触发词）
        """
        trigger_len = trigger_end - trigger_start

        # ---- 1. 前缀反转短语 ----
        # 检查触发词前面是否能匹配前缀反转短语
        prefix_window_start = max(0, trigger_start - 12)
        prefix_window = text[prefix_window_start:trigger_end]

        for rev_word in self.prefix_reversals:
            if rev_word in prefix_window:
                rev_pos = prefix_window.rfind(rev_word)
                rev_abs_start = prefix_window_start + rev_pos
                rev_abs_end = rev_abs_start + len(rev_word)
                # 判断反转词是否修饰这个触发词：
                # 情况A：反转词在触发词前面，紧邻（距离 <= 4字符）
                # 情况B：反转词包含触发词（如"暂停加息"包含"加息"）
                dist = trigger_start - rev_abs_end
                overlaps = (rev_abs_start <= trigger_start and rev_abs_end >= trigger_start)
                if (0 <= dist <= 4) or overlaps:
                    return True, rev_word

        # ---- 2. 后缀反转短语 ----
        suffix_window_end = min(len(text), trigger_end + 12)
        suffix_window = text[trigger_start:suffix_window_end]

        for rev_word in self.suffix_reversals:
            if rev_word in suffix_window:
                rev_pos = suffix_window.find(rev_word)
                rev_abs_start = trigger_start + rev_pos
                rev_abs_end = rev_abs_start + len(rev_word)
                # 判断反转词是否修饰这个触发词：
                # 情况A：反转词在触发词后面，紧邻（距离 <= 4字符）
                # 情况B：反转词包含触发词
                dist = rev_abs_start - trigger_end
                overlaps = (rev_abs_start <= trigger_end and rev_abs_end >= trigger_end)
                if (0 <= dist <= 4) or overlaps:
                    return True, rev_word

        # ---- 3. 紧邻否定词（触发词前面） ----
        neg_window_start = max(0, trigger_start - 3)
        neg_window = text[neg_window_start:trigger_start]

        for neg_word in self.sorted_negations:
            if neg_word in neg_window:
                return True, neg_word

        return False, ""

    def _detect_degree(self, text, trigger_start, trigger_end):
        """
        检测触发词的程度修饰（前置 + 后置）

        规则：
        1. 先查前置程度词（触发词前15字符窗口）
        2. 再查后置程度词（触发词后15字符窗口）
        3. 程度优先级：strong > uncertain > weakening > moderate
        4. 前置程度词权重略高于后置（前置修饰更直接）
        """
        prefix_window_start = max(0, trigger_start - 15)
        prefix_window = text[prefix_window_start:trigger_start]

        suffix_window_end = min(len(text), trigger_end + 15)
        suffix_window = text[trigger_end:suffix_window_end]

        # 按优先级检查程度级别
        for level in ["strong", "uncertain", "weakening", "moderate"]:
            # 先查前置
            for word in self.prefix_degree.get(level, []):
                if word in prefix_window:
                    return level, "prefix", word
            # 再查后置
            for word in self.suffix_degree.get(level, []):
                if word in suffix_window:
                    return level, "suffix", word

        return "moderate", "none", ""  # 默认中等

    def _detect_commodities(self, text):
        """检测新闻涉及的品种"""
        detected = []
        for commodity, keywords in self.commodity_entities.items():
            for kw in keywords:
                if kw in text:
                    detected.append(commodity)
                    break
        return list(set(detected)) if detected else ["precious_metals_general"]

    def extract(self, text):
        """
        从单条文本中抽取事件

        Args:
            text: 输入新闻文本

        Returns:
            dict: {
                'text': str,                    # 原始文本
                'commodities': list,            # 涉及品种
                'events': [                     # 抽取到的事件列表
                    {
                        'event_type': str,      # 事件类型ID
                        'event_type_name': str, # 事件类型中文名
                        'direction': str,       # bullish / bearish
                        'direction_cn': str,    # 利多 / 利空
                        'degree': str,          # strong / moderate / uncertain / weakening
                        'degree_cn': str,       # 强 / 中 / 不确定 / 减弱
                        'trigger_word': str,    # 触发词
                        'reversed': bool,       # 是否被反转
                        'reversal_word': str,   # 反转词
                        'degree_word': str,     # 程度修饰词
                    },
                    ...
                ],
                'summary': { ... }
            }
        """
        if not text or not str(text).strip():
            return {
                "text": text,
                "commodities": [],
                "events": [],
                "summary": {
                    "total_events": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "net_direction": "neutral",
                    "dominant_types": [],
                },
            }

        text = str(text).strip()

        # 1. 识别品种
        commodities = self._detect_commodities(text)

        # 2. 查找所有触发词
        triggers = self._find_triggers(text)

        # 3. 逐个事件分析
        events = []
        type_counts = defaultdict(int)

        for trigger_word, start_pos, end_pos, etype, direction in triggers:
            # 检测程度
            degree, degree_pos, degree_word = self._detect_degree(
                text, start_pos, end_pos
            )

            # 检测反转
            reversed_flag, reversal_word = self._check_reversal(
                text, start_pos, end_pos
            )

            # 反转后翻转方向
            # 注意：程度减弱(weakening)不改变方向，只改变程度级别
            if reversed_flag:
                final_direction = (
                    "bearish" if direction == "bullish" else "bullish"
                )
            else:
                final_direction = direction

            # 程度映射：weakening 统一降级为 moderate 展示
            display_degree = degree if degree != "weakening" else "moderate"
            degree_cn_map = {
                "strong": "强",
                "moderate": "中",
                "uncertain": "不确定",
                "weakening": "减弱",
            }

            events.append({
                "event_type": etype,
                "event_type_name": self.event_types[etype]["name"],
                "direction": final_direction,
                "direction_cn": "利多" if final_direction == "bullish" else "利空",
                "degree": display_degree,
                "degree_cn": degree_cn_map.get(display_degree, "中"),
                "trigger_word": trigger_word,
                "reversed": reversed_flag,
                "reversal_word": reversal_word,
                "degree_word": degree_word,
                "position": start_pos,
            })

            type_counts[etype] += 1

        # 4. 汇总
        bullish_count = sum(1 for e in events if e["direction"] == "bullish")
        bearish_count = sum(1 for e in events if e["direction"] == "bearish")

        if bullish_count > 0 and bearish_count == 0:
            net_direction = "bullish"
        elif bearish_count > 0 and bullish_count == 0:
            net_direction = "bearish"
        elif bullish_count > 0 and bearish_count > 0:
            net_direction = "mixed"
        else:
            net_direction = "neutral"

        # 主要事件类型（按出现次数排序）
        dominant_types = sorted(
            type_counts.keys(), key=lambda x: type_counts[x], reverse=True
        )

        return {
            "text": text,
            "commodities": commodities,
            "events": events,
            "summary": {
                "total_events": len(events),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "net_direction": net_direction,
                "net_direction_cn": {
                    "bullish": "利多",
                    "bearish": "利空",
                    "mixed": "多空交织",
                    "neutral": "中性"
                }[net_direction],
                "dominant_types": dominant_types,
                "dominant_type_names": [
                    self.event_types[t]["name"] for t in dominant_types
                ],
            },
        }

    def batch_extract(self, news_list):
        """
        批量抽取事件

        Args:
            news_list: [{'text': '...', 'time': '...', ...}, ...]

        Returns:
            list: 每条新闻增加了事件抽取结果
        """
        if not news_list:
            return []

        results = []
        for item in news_list:
            text = (
                item.get("content", "")
                or item.get("text", "")
                or item.get("title", "")
            )
            extraction = self.extract(text)

            item_copy = dict(item)
            item_copy["extraction"] = extraction
            # 扁平化关键字段，方便后续处理
            item_copy["event_count"] = extraction["summary"]["total_events"]
            item_copy["net_direction"] = extraction["summary"]["net_direction"]
            item_copy["event_types"] = ",".join(
                extraction["summary"]["dominant_types"]
            )
            item_copy["commodities"] = ",".join(extraction["commodities"])
            results.append(item_copy)

        with_events = sum(1 for r in results if r["event_count"] > 0)
        logger.info(
            f"批量抽取完成: {len(results)}条新闻, "
            f"抽中事件{with_events}条 ({with_events / len(results):.1%})"
        )
        if results:
            bullish = sum(1 for r in results if r["net_direction"] == "bullish")
            bearish = sum(1 for r in results if r["net_direction"] == "bearish")
            mixed = sum(1 for r in results if r["net_direction"] == "mixed")
            logger.info(f"  利多:{bullish}, 利空:{bearish}, 多空交织:{mixed}")

        return results

    def build_daily_index(self, extracted_news):
        """
        按交易日聚合事件，生成日度事件指数

        Args:
            extracted_news: 批量抽取后的新闻列表

        Returns:
            list: 每日事件指数
        """
        from datetime import datetime

        # 按日期分组
        daily_news = defaultdict(list)
        for item in extracted_news:
            time_str = (
                item.get("publish_time", "")
                or item.get("time", "")
                or item.get("pub_time", "")
                or item.get("date", "")
            )
            if not time_str:
                continue
            try:
                if " " in time_str:
                    date_part = time_str.split(" ")[0]
                else:
                    date_part = time_str[:10]
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                    try:
                        date_obj = datetime.strptime(date_part, fmt)
                        date_key = date_obj.strftime("%Y-%m-%d")
                        daily_news[date_key].append(item)
                        break
                    except Exception:
                        continue
            except Exception:
                continue

        # 计算每日指数
        daily_index = []
        for date in sorted(daily_news.keys()):
            day_news = daily_news[date]
            n_total = len(day_news)

            # 按事件类型统计
            type_stats = defaultdict(
                lambda: {"bullish": 0, "bearish": 0, "total": 0}
            )
            bullish_total = 0
            bearish_total = 0
            total_events = 0

            for item in day_news:
                if "extraction" not in item:
                    continue
                for event in item["extraction"]["events"]:
                    etype = event["event_type"]
                    direction = event["direction"]
                    type_stats[etype][direction] += 1
                    type_stats[etype]["total"] += 1
                    total_events += 1
                    if direction == "bullish":
                        bullish_total += 1
                    else:
                        bearish_total += 1

            # 净事件方向指数（范围 [-1, 1]）
            if total_events > 0:
                net_index = (bullish_total - bearish_total) / total_events
            else:
                net_index = 0.0

            # 各类型分别的净值
            type_net = {}
            for etype, stats in type_stats.items():
                if stats["total"] > 0:
                    type_net[etype] = round(
                        (stats["bullish"] - stats["bearish"]) / stats["total"], 4
                    )
                else:
                    type_net[etype] = 0.0

            daily_index.append({
                "date": date,
                "news_count": n_total,
                "event_count": total_events,
                "bullish_events": bullish_total,
                "bearish_events": bearish_total,
                "net_event_index": round(net_index, 4),
                "type_count": len(type_stats),
                "type_breakdown": json.dumps(type_stats, ensure_ascii=False),
                "type_net_index": json.dumps(type_net, ensure_ascii=False),
            })

        logger.info(f"日度事件指数生成完成: {len(daily_index)}个交易日")
        return daily_index


def _setup_logging(verbose=False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="贵金属期货事件抽取器")
    parser.add_argument("--text", type=str, default=None,
                        help="单条文本快速测试")
    parser.add_argument("--input", type=str, default=None,
                        help="输入新闻数据目录（JSON格式）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出事件数据路径")
    parser.add_argument("--daily-index", action="store_true",
                        help="同时生成日度事件指数")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="输出详细日志")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    logger.info("=" * 50)
    logger.info("  贵金属期货事件抽取器")
    logger.info("  非结构化新闻 → 结构化事件数据")
    logger.info("=" * 50)

    extractor = EventExtractor()

    if args.text:
        logger.info("单条文本抽取模式")
        logger.info(f"输入: {args.text}")
        result = extractor.extract(args.text)

        print(f"\n涉及品种: {result['commodities']}")
        print(f"事件数量: {result['summary']['total_events']}")
        print(f"净方向: {result['summary']['net_direction_cn']}")
        print(f"主要类型: {result['summary']['dominant_type_names']}")

        if result["events"]:
            print("\n事件明细:")
            for i, evt in enumerate(result["events"], 1):
                rev_mark = " [反转]" if evt["reversed"] else ""
                deg_mark = f" / 程度词:{evt['degree_word']}" if evt["degree_word"] else ""
                print(
                    f"  [{i}] {evt['event_type_name']} / {evt['direction_cn']} "
                    f"/ 程度:{evt['degree_cn']} / 触发词:{evt['trigger_word']}"
                    f"{rev_mark}{deg_mark}"
                )
        return

    if args.input:
        logger.info("批量事件抽取模式")
        input_path = Path(args.input)
        all_news = []

        if input_path.is_dir():
            pattern = str(input_path / "**" / "*.json")
            for filepath in glob.glob(pattern, recursive=True):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        all_news.extend(data)
                    elif isinstance(data, dict):
                        all_news.append(data)
                except Exception as e:
                    logger.warning(f"跳过 {filepath}: {e}")
        else:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                all_news.extend(data)
            else:
                all_news.append(data)

        logger.info(f"加载新闻: {len(all_news)} 条")

        if len(all_news) == 0:
            logger.warning("没有加载到新闻数据")
            return

        extracted = extractor.batch_extract(all_news)

        # 保存
        output_path = args.output or str(BASE_DIR / "output" / "extracted_events.json")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)
        logger.info(f"事件抽取结果已保存: {output_path}")

        # 日度指数
        if args.daily_index:
            daily_index = extractor.build_daily_index(extracted)
            try:
                import pandas as pd
                index_path = Path(output_path).parent / "daily_event_index.xlsx"
                pd.DataFrame(daily_index).to_excel(str(index_path), index=False)
                logger.info(f"日度事件指数已保存: {index_path}")
            except ImportError:
                logger.warning("未安装pandas，跳过Excel导出")
                index_path = Path(output_path).parent / "daily_event_index.json"
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump(daily_index, f, ensure_ascii=False, indent=2)
                logger.info(f"日度事件指数已保存(JSON): {index_path}")

        return

    parser.print_help()


if __name__ == "__main__":
    main()
