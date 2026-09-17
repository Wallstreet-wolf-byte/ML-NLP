"""
事件抽取器单元测试

覆盖场景：
1. 基础事件抽取（利多/利空各类型）
2. 程度词检测（前置程度词 / 后置程度词）
3. 否定词处理（不加息、未降息等）
4. 反转词规则（加息暂停、降息预期降温等）
5. 短语级触发词优先匹配
6. 多事件抽取
7. 边界case（空文本、无匹配、品种识别）

运行方式：
    cd extractor
    python -m pytest tests/test_event_extractor.py -v
    # 或直接运行
    python tests/test_event_extractor.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 确保能 import 到抽取器模块
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志（测试时只输出 warning 以上）
import logging
logging.basicConfig(level=logging.WARNING)

from event_extractor import EventExtractor  # noqa: E402


class TestEventExtractorBase(unittest.TestCase):
    """基础抽取测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_empty_text_returns_empty(self):
        """空文本返回空结果"""
        result = self.extractor.extract("")
        self.assertEqual(result["summary"]["total_events"], 0)
        self.assertEqual(result["events"], [])

    def test_whitespace_text_returns_empty(self):
        """纯空白文本返回空结果"""
        result = self.extractor.extract("   \n  ")
        self.assertEqual(result["summary"]["total_events"], 0)

    def test_no_trigger_words_returns_empty(self):
        """没有触发词的文本返回空事件"""
        result = self.extractor.extract("今天天气真好，适合出去玩")
        self.assertEqual(result["summary"]["total_events"], 0)
        self.assertEqual(result["summary"]["net_direction"], "neutral")


class TestBullishEvents(unittest.TestCase):
    """利多事件测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_rate_cut_bullish(self):
        """降息 → 货币政策利多"""
        result = self.extractor.extract("美联储宣布降息，黄金价格上涨")
        events = result["events"]
        monetary_events = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bullish" for e in monetary_events)
        )

    def test_dollar_drop_bullish(self):
        """美元下跌 → 美元汇率利多（对黄金）"""
        result = self.extractor.extract("美元指数下跌，提振金价")
        events = result["events"]
        dollar_events = [e for e in events if e["event_type"] == "dollar_exchange"]
        self.assertTrue(len(dollar_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bullish" for e in dollar_events)
        )

    def test_risk_aversion_bullish(self):
        """避险情绪升温 → 利多黄金"""
        result = self.extractor.extract("地缘冲突加剧，避险情绪升温，金价上涨")
        events = result["events"]
        risk_events = [e for e in events if e["event_type"] == "risk_aversion"]
        self.assertTrue(len(risk_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bullish" for e in risk_events)
        )

    def test_central_bank_buying_bullish(self):
        """央行购金 → 利多"""
        result = self.extractor.extract("多国央行继续购金，黄金储备创新高")
        events = result["events"]
        cb_events = [e for e in events if e["event_type"] == "central_bank"]
        self.assertTrue(len(cb_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bullish" for e in cb_events)
        )


class TestBearishEvents(unittest.TestCase):
    """利空事件测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_rate_hike_bearish(self):
        """加息 → 货币政策利空"""
        result = self.extractor.extract("美联储宣布加息，黄金价格承压")
        events = result["events"]
        monetary_events = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bearish" for e in monetary_events)
        )

    def test_dollar_rise_bearish(self):
        """美元上涨 → 美元汇率利空（对黄金）"""
        result = self.extractor.extract("美元指数走强，金价回落")
        events = result["events"]
        dollar_events = [e for e in events if e["event_type"] == "dollar_exchange"]
        self.assertTrue(len(dollar_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bearish" for e in dollar_events)
        )

    def test_inflation_drop_bearish(self):
        """通胀回落 → 通胀预期利空（对黄金抗通胀逻辑）"""
        result = self.extractor.extract("CPI数据不及预期，通胀降温，金价下跌")
        events = result["events"]
        inflation_events = [e for e in events if e["event_type"] == "inflation"]
        self.assertTrue(len(inflation_events) > 0)
        self.assertTrue(
            any(e["direction"] == "bearish" for e in inflation_events)
        )


class TestDegreeDetection(unittest.TestCase):
    """程度词检测测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_prefix_strong_degree(self):
        """前置程度词：大幅加息 → 程度强"""
        result = self.extractor.extract("美联储大幅加息")
        events = result["events"]
        # 找到货币政策事件
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        # "大幅"是强程度前置词
        rate_hike_events = [e for e in monetary if e["trigger_word"] == "加息"]
        if rate_hike_events:
            self.assertEqual(rate_hike_events[0]["degree"], "strong")
            self.assertIn("大幅", rate_hike_events[0]["degree_word"])

    def test_prefix_uncertain_degree(self):
        """前置不确定程度词：预期加息 → 不确定"""
        result = self.extractor.extract("市场预期美联储加息")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        rate_hike_events = [e for e in monetary if e["trigger_word"] == "加息"]
        if rate_hike_events:
            self.assertEqual(rate_hike_events[0]["degree"], "uncertain")

    def test_suffix_strong_degree(self):
        """后置程度词：加息超预期 → 程度强"""
        result = self.extractor.extract("美联储加息超预期")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        # "超预期"是强程度后置词
        rate_hike_events = [e for e in monetary if e["trigger_word"] == "加息"]
        if rate_hike_events:
            self.assertEqual(rate_hike_events[0]["degree"], "strong")

    def test_default_moderate_degree(self):
        """无程度词 → 默认中等"""
        result = self.extractor.extract("美联储加息")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        rate_hike_events = [e for e in monetary if e["trigger_word"] == "加息"]
        if rate_hike_events:
            self.assertEqual(rate_hike_events[0]["degree"], "moderate")


class TestReversalPatterns(unittest.TestCase):
    """反转词规则测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_prefix_reversal_suspend_hike(self):
        """前缀反转：暂停加息 → 加息被反转 → 利多"""
        result = self.extractor.extract("美联储暂停加息")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        # "加息" 本身是利空，被"暂停"反转后应变利多
        reversed_events = [e for e in monetary if e["reversed"]]
        self.assertTrue(len(reversed_events) > 0,
                        "暂停加息应该触发反转")
        self.assertEqual(reversed_events[0]["direction"], "bullish")

    def test_prefix_reversal_not_hike(self):
        """前缀否定：不加息 → 加息被反转 → 利多"""
        result = self.extractor.extract("美联储不加息")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        reversed_events = [e for e in monetary if e["reversed"]]
        self.assertTrue(len(reversed_events) > 0,
                        "不加息应该触发反转")
        self.assertEqual(reversed_events[0]["direction"], "bullish")

    def test_suffix_reversal_hike_pause(self):
        """后缀反转：加息暂停 → 加息被反转 → 利多"""
        result = self.extractor.extract("市场认为加息暂停")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        reversed_events = [e for e in monetary if e["reversed"]]
        self.assertTrue(len(reversed_events) > 0,
                        "加息暂停应该触发反转")
        self.assertEqual(reversed_events[0]["direction"], "bullish")

    def test_hike_without_reversal_stays_bearish(self):
        """没有反转词时，加息保持利空"""
        result = self.extractor.extract("美联储宣布加息25基点")
        events = result["events"]
        monetary = [e for e in events if e["event_type"] == "monetary_policy"]
        self.assertTrue(len(monetary) > 0)
        # 应该有非反转的加息事件
        normal_events = [e for e in monetary if not e["reversed"]
                         and e["trigger_word"] == "加息"]
        self.assertTrue(len(normal_events) > 0)
        self.assertEqual(normal_events[0]["direction"], "bearish")


class TestPhraseTriggerPriority(unittest.TestCase):
    """短语级触发词优先匹配测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_long_phrase_matched_first(self):
        """长词优先匹配：加息预期升温 应该匹配短语，而不是单独的 加息"""
        result = self.extractor.extract("加息预期升温，金价下跌")
        events = result["events"]
        # 应该匹配到"加息预期升温"这个短语（利空）
        # 而不是"加息"和"升温"分开匹配
        long_phrase_events = [
            e for e in events
            if e["trigger_word"] == "加息预期升温"
        ]
        self.assertTrue(len(long_phrase_events) > 0,
                        "应该优先匹配短语级触发词'加息预期升温'")


class TestCommodityDetection(unittest.TestCase):
    """品种识别测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_gold_detection(self):
        """识别黄金相关新闻"""
        result = self.extractor.extract("黄金价格上涨")
        self.assertIn("gold", result["commodities"])

    def test_silver_detection(self):
        """识别白银相关新闻"""
        result = self.extractor.extract("白银价格下跌")
        self.assertIn("silver", result["commodities"])

    def test_both_commodities(self):
        """同时识别黄金和白银"""
        result = self.extractor.extract("黄金和白银价格双双上涨")
        self.assertIn("gold", result["commodities"])
        self.assertIn("silver", result["commodities"])

    def test_no_commodity_fallback(self):
        """没有品种词时返回通用贵金属"""
        result = self.extractor.extract("美联储加息")
        self.assertIn("precious_metals_general", result["commodities"])


class TestMultipleEvents(unittest.TestCase):
    """多事件抽取测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_mixed_directions(self):
        """同时有利多和利空事件 → net_direction=mixed"""
        text = "美联储加息利空金价，但避险情绪升温支撑金价"
        result = self.extractor.extract(text)
        self.assertEqual(result["summary"]["net_direction"], "mixed")
        self.assertGreater(result["summary"]["bullish_count"], 0)
        self.assertGreater(result["summary"]["bearish_count"], 0)

    def test_all_bullish(self):
        """全部利多 → net_direction=bullish"""
        text = "美元下跌，避险升温，央行购金，金价大涨"
        result = self.extractor.extract(text)
        self.assertEqual(result["summary"]["net_direction"], "bullish")
        self.assertGreater(result["summary"]["bullish_count"], 0)
        self.assertEqual(result["summary"]["bearish_count"], 0)

    def test_multiple_same_type(self):
        """同类型多个触发词都能被抽取"""
        text = "金价突破新高，创出历史新高，多头排列"
        result = self.extractor.extract(text)
        tech_events = [e for e in result["events"]
                       if e["event_type"] == "technical"]
        self.assertGreaterEqual(len(tech_events), 2)


class TestSummaryFields(unittest.TestCase):
    """汇总字段测试"""

    @classmethod
    def setUpClass(cls):
        cls.extractor = EventExtractor()

    def test_summary_counts_match(self):
        """汇总计数应该和事件列表一致"""
        result = self.extractor.extract(
            "美联储加息，美元上涨，金价下跌，避险情绪消退"
        )
        events = result["events"]
        summary = result["summary"]

        self.assertEqual(summary["total_events"], len(events))
        bullish = sum(1 for e in events if e["direction"] == "bullish")
        bearish = sum(1 for e in events if e["direction"] == "bearish")
        self.assertEqual(summary["bullish_count"], bullish)
        self.assertEqual(summary["bearish_count"], bearish)

    def test_dominant_types_ordered(self):
        """主要事件类型应该按出现次数排序"""
        result = self.extractor.extract(
            "美联储加息，美联储鹰派，美元上涨，美元走强"
        )
        dominant = result["summary"]["dominant_types"]
        # 货币政策出现2次，美元汇率出现2次，顺序不一定，但都应该在前
        self.assertIn("monetary_policy", dominant[:2])
        self.assertIn("dollar_exchange", dominant[:2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
