"""
贵金属期货事件抽取器

功能：
将非结构化财经新闻转化为结构化事件数据，输出三级标注：
  - 事件类型（10类定价驱动因子）
  - 方向（利多/利空/中性）
  - 程度（强/中/弱/不确定）

核心思路：
  基于事件本体的触发词匹配 + 程度修饰词识别 + 否定词处理
  不依赖机器学习模型，纯规则驱动，可解释、速度快

用法：
    python event_extractor.py --text "美联储宣布加息25个基点，金价承压下跌"
    python event_extractor.py --input ./news_data --output ./events.json
"""

import os
import re
import json
import glob
import argparse
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
ONTOLOGY_PATH = BASE_DIR.parent / "event_ontology" / "event_ontology.json"
NEGATION_PATH = BASE_DIR.parent / "dicts" / "negation.txt"

# 品种实体识别（用于判断新闻涉及哪个品种）
COMMODITY_ENTITIES = {
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


class EventExtractor:
    """基于规则的事件抽取器"""

    def __init__(self, ontology_path=None, negation_path=None):
        """
        初始化事件抽取器
        Args:
            ontology_path: 事件本体JSON路径
            negation_path: 否定词表路径
        """
        ontology_path = ontology_path or ONTOLOGY_PATH
        negation_path = negation_path or NEGATION_PATH

        # 加载事件本体
        with open(ontology_path, "r", encoding="utf-8") as f:
            self.ontology = json.load(f)

        self.event_types = self.ontology["event_types"]
        self.degree_modifiers = self.ontology["degree_modifiers"]

        # 加载否定词
        self.negation_words = set()
        if negation_path.exists():
            with open(negation_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        self.negation_words.add(word)

        # 预计算：所有触发词按长度倒序，避免短词先匹配
        self._build_trigger_index()

        print(f"[事件抽取器] 事件类型: {len(self.event_types)} 类")
        print(f"  利多触发词: {sum(len(v['bullish_triggers']) for v in self.event_types.values())}")
        print(f"  利空触发词: {sum(len(v['bearish_triggers']) for v in self.event_types.values())}")
        print(f"  程度修饰词: 强{len(self.degree_modifiers['strong'])} / "
              f"中{len(self.degree_modifiers['moderate'])} / "
              f"不确定{len(self.degree_modifiers['uncertain'])}")
        print(f"  否定词: {len(self.negation_words)}")

    def _build_trigger_index(self):
        """构建触发词索引：{触发词: (事件类型, 方向)}"""
        self.trigger_index = {}
        for etype_id, etype_data in self.event_types.items():
            for word in etype_data["bullish_triggers"]:
                self.trigger_index[word] = (etype_id, "bullish")
            for word in etype_data["bearish_triggers"]:
                self.trigger_index[word] = (etype_id, "bearish")

        # 按词长倒序，优先匹配长词
        self.sorted_triggers = sorted(
            self.trigger_index.keys(), key=len, reverse=True
        )

    def _find_triggers(self, text):
        """在文本中查找所有触发词，返回 [(词, 位置, 事件类型, 方向), ...]"""
        found = []
        used_positions = set()  # 避免重叠匹配

        for trigger in self.sorted_triggers:
            start = 0
            while True:
                idx = text.find(trigger, start)
                if idx == -1:
                    break
                # 检查是否与已匹配的位置重叠
                end = idx + len(trigger)
                overlap = any(idx <= p < end for p in used_positions)
                if not overlap:
                    etype, direction = self.trigger_index[trigger]
                    found.append((trigger, idx, etype, direction))
                    for p in range(idx, end):
                        used_positions.add(p)
                start = end

        # 按位置排序
        found.sort(key=lambda x: x[1])
        return found

    def _detect_degree(self, text, trigger_pos):
        """检测触发词附近的程度修饰词"""
        # 在触发词前后各找（窗口约20个字符）
        window_start = max(0, trigger_pos - 20)
        window_end = min(len(text), trigger_pos + 20)
        window = text[window_start:window_end]

        for degree in ["strong", "uncertain", "moderate"]:  # 优先级：强 > 不确定 > 中
            for word in self.degree_modifiers[degree]:
                if word in window:
                    return degree

        return "moderate"  # 默认中等

    def _has_negation_nearby(self, text, trigger_pos):
        """检查触发词附近是否有否定词（窗口内）"""
        window_start = max(0, trigger_pos - 15)
        window_end = trigger_pos
        window = text[window_start:window_end]

        for neg_word in self.negation_words:
            if neg_word in window:
                return True
        return False

    def _detect_commodities(self, text):
        """检测新闻涉及的品种"""
        detected = []
        for commodity, keywords in COMMODITY_ENTITIES.items():
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
                        'degree': str,          # strong / moderate / uncertain
                        'trigger_word': str,    # 触发词
                        'negated': bool,        # 是否被否定
                    },
                    ...
                ],
                'summary': {                    # 汇总信息
                    'total_events': int,
                    'bullish_count': int,
                    'bearish_count': int,
                    'net_direction': str,       # bullish / bearish / neutral / mixed
                    'dominant_types': list,     # 主要事件类型
                }
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

        for trigger_word, pos, etype, direction in triggers:
            # 检测程度
            degree = self._detect_degree(text, pos)

            # 检测否定
            negated = self._has_negation_nearby(text, pos)

            # 否定翻转方向
            final_direction = "bearish" if direction == "bullish" and negated else \
                              "bullish" if direction == "bearish" and negated else \
                              direction

            events.append({
                "event_type": etype,
                "event_type_name": self.event_types[etype]["name"],
                "direction": final_direction,
                "direction_cn": "利多" if final_direction == "bullish" else "利空",
                "degree": degree,
                "degree_cn": {"strong": "强", "moderate": "中", "uncertain": "不确定"}[degree],
                "trigger_word": trigger_word,
                "negated": negated,
                "position": pos,
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
        dominant_types = sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)

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
                "dominant_type_names": [self.event_types[t]["name"] for t in dominant_types],
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
        results = []
        for item in news_list:
            text = item.get("content", "") or item.get("text", "") or item.get("title", "")
            extraction = self.extract(text)

            item_copy = dict(item)
            item_copy["extraction"] = extraction
            # 扁平化关键字段，方便后续处理
            item_copy["event_count"] = extraction["summary"]["total_events"]
            item_copy["net_direction"] = extraction["summary"]["net_direction"]
            item_copy["event_types"] = ",".join(extraction["summary"]["dominant_types"])
            item_copy["commodities"] = ",".join(extraction["commodities"])
            results.append(item_copy)

        with_events = sum(1 for r in results if r["event_count"] > 0)
        print(f"[事件抽取] 共 {len(results)} 条新闻")
        print(f"  抽中事件: {with_events} 条 ({with_events/len(results):.1%})")
        if results:
            bullish = sum(1 for r in results if r["net_direction"] == "bullish")
            bearish = sum(1 for r in results if r["net_direction"] == "bearish")
            mixed = sum(1 for r in results if r["net_direction"] == "mixed")
            print(f"  利多: {bullish}, 利空: {bearish}, 多空交织: {mixed}")

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
            time_str = item.get("time", "") or item.get("pub_time", "") or item.get("date", "")
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
                    except:
                        continue
            except:
                continue

        # 计算每日指数
        daily_index = []
        for date in sorted(daily_news.keys()):
            day_news = daily_news[date]
            n_total = len(day_news)

            # 按事件类型统计
            type_stats = defaultdict(lambda: {"bullish": 0, "bearish": 0, "total": 0})
            bullish_total = 0
            bearish_total = 0
            total_events = 0

            for item in day_news:
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

        print(f"\n[日度事件指数] 共 {len(daily_index)} 个交易日")
        return daily_index


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
    args = parser.parse_args()

    print("=" * 60)
    print("  贵金属期货事件抽取器")
    print("  非结构化新闻 → 结构化事件数据")
    print("=" * 60)

    extractor = EventExtractor()

    if args.text:
        print("\n--- 单条文本抽取 ---")
        print(f"输入: {args.text}")
        result = extractor.extract(args.text)

        print(f"\n涉及品种: {result['commodities']}")
        print(f"事件数量: {result['summary']['total_events']}")
        print(f"净方向: {result['summary']['net_direction_cn']}")
        print(f"主要类型: {result['summary']['dominant_type_names']}")

        if result["events"]:
            print("\n事件明细:")
            for i, evt in enumerate(result["events"], 1):
                neg_mark = " [被否定]" if evt["negated"] else ""
                print(f"  [{i}] {evt['event_type_name']} / {evt['direction_cn']} "
                      f"/ 程度:{evt['degree_cn']} / 触发词:{evt['trigger_word']}{neg_mark}")
        return

    if args.input:
        print("\n--- 批量事件抽取 ---")
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
                    print(f"  跳过 {filepath}: {e}")
        else:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                all_news.extend(data)
            else:
                all_news.append(data)

        print(f"[加载] 共 {len(all_news)} 条新闻")

        if len(all_news) == 0:
            print("[警告] 没有加载到新闻数据")
            return

        extracted = extractor.batch_extract(all_news)

        # 保存
        output_path = args.output or str(BASE_DIR / "output" / "extracted_events.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 事件抽取结果: {output_path}")

        # 日度指数
        if args.daily_index:
            daily_index = extractor.build_daily_index(extracted)
            import pandas as pd
            index_path = Path(output_path).parent / "daily_event_index.xlsx"
            pd.DataFrame(daily_index).to_excel(str(index_path), index=False)
            print(f"[保存] 日度事件指数: {index_path}")

        return

    parser.print_help()


if __name__ == "__main__":
    main()
