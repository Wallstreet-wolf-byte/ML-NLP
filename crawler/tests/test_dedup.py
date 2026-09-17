"""
去重模块单元测试

覆盖场景：
1. 精确去重（完全相同的新闻）
2. 近似去重（标题/内容略有差异的同一新闻）
3. 时间窗口过滤（时间差超过窗口的不判为重复）
4. 边界case（空内容、极短文本、特殊字符）
5. SimHash 汉明距离计算
6. 大规模数据性能验证（1000条数据不卡死）

运行方式：
    cd crawler
    python -m pytest tests/test_dedup.py -v
    # 或直接运行
    python tests/test_dedup.py
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

# 确保能 import 到 common 模块
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from common.dedup import (  # noqa: E402
    deduplicate_records,
    make_dedup_key,
    compute_simhash,
    hamming_distance,
    normalize_news_text,
    within_time_window,
    text_similarity,
    parse_publish_time,
)


def _make_record(
    title: str = "",
    content: str = "",
    publish_time: str = "2026-09-15 10:00:00",
    source: str = "测试",
    news_id: str = "",
) -> dict:
    """构造测试用新闻记录"""
    return {
        "news_id": news_id or f"test_{title[:10]}",
        "title": title,
        "content": content,
        "publish_time": publish_time,
        "source": source,
    }


class TestExactDeduplication(unittest.TestCase):
    """精确去重测试"""

    def test_identical_records_are_deduped(self):
        """完全相同的两条新闻应该被去重为1条"""
        records = [
            _make_record(title="美联储加息25基点", content="美联储宣布加息25个基点"),
            _make_record(title="美联储加息25基点", content="美联储宣布加息25个基点"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 1)

    def test_different_titles_not_deduped(self):
        """标题完全不同的新闻不应被去重"""
        records = [
            _make_record(title="美联储加息25基点", content="美联储宣布加息"),
            _make_record(title="欧洲央行维持利率不变", content="欧央行宣布按兵不动"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 2)

    def test_same_title_different_source_not_deduped(self):
        """同标题不同来源，如果内容相同应去重"""
        records = [
            _make_record(title="金价上涨", content="黄金价格上涨1%", source="金十"),
            _make_record(title="金价上涨", content="黄金价格上涨1%", source="汇通"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 1)  # 内容相同 → 精确去重

    def test_empty_records_handled(self):
        """空记录也能正确处理"""
        records = [
            _make_record(title="", content=""),
            _make_record(title="", content=""),
        ]
        result = deduplicate_records(records)
        self.assertGreaterEqual(len(result), 1)  # 至少保留1条

    def test_single_record_passes_through(self):
        """单条记录直接返回"""
        records = [_make_record(title="测试新闻", content="测试内容")]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 1)

    def test_no_records_returns_empty(self):
        """空列表返回空列表"""
        result = deduplicate_records([])
        self.assertEqual(result, [])


class TestNearDeduplication(unittest.TestCase):
    """近似去重测试"""

    def test_highly_similar_are_deduped(self):
        """相似度很高的两条新闻应该被近似去重"""
        base_content = "美联储宣布加息25个基点，符合市场预期，黄金价格小幅下跌"
        records = [
            _make_record(title="美联储加息25基点", content=base_content,
                         publish_time="2026-09-15 10:00:00"),
            # 只改了几个字，相似度很高
            _make_record(title="美联储加息25基点", content=base_content + "。",
                         publish_time="2026-09-15 10:05:00"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 1)

    def test_different_content_not_deduped(self):
        """内容不同的新闻不应被去重"""
        records = [
            _make_record(title="金价上涨", content="黄金价格因避险情绪大幅上涨",
                         publish_time="2026-09-15 10:00:00"),
            _make_record(title="银价上涨", content="白银价格因工业需求强劲上涨",
                         publish_time="2026-09-15 10:01:00"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 2)

    def test_time_window_filters_out_distant_news(self):
        """时间差超过窗口的不应被判为近似重复"""
        # 内容相似但不完全相同（绕过精确去重，测试近似去重的时间窗口）
        records = [
            _make_record(title="美联储加息25基点",
                         content="美联储宣布加息25个基点，金价承压下跌",
                         publish_time="2026-09-15 10:00:00"),
            # 3小时后，超过默认2小时窗口，内容略不同
            _make_record(title="美联储加息25基点",
                         content="美联储宣布加息25个基点，黄金价格承压",
                         publish_time="2026-09-15 13:00:00"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 2)

    def test_same_time_similar_content_deduped(self):
        """同一时间相似内容应该被去重"""
        records = [
            _make_record(title="金价突破新高",
                         content="黄金价格突破历史新高，市场情绪乐观，投资者纷纷买入",
                         publish_time="2026-09-15 10:00:00"),
            _make_record(title="金价突破新高",
                         content="黄金价格突破历史新高，市场情绪乐观，投资者纷纷买入黄金",
                         publish_time="2026-09-15 10:02:00"),
        ]
        result = deduplicate_records(records)
        self.assertEqual(len(result), 1)


class TestSimHash(unittest.TestCase):
    """SimHash 测试"""

    def test_identical_texts_same_hash(self):
        """完全相同的文本 SimHash 应该相同"""
        text = "美联储宣布加息25个基点，金价承压下跌"
        h1 = compute_simhash(text)
        h2 = compute_simhash(text)
        self.assertEqual(h1, h2)

    def test_similar_texts_small_hamming_distance(self):
        """相似文本的汉明距离应该小"""
        text1 = "美联储宣布加息25个基点，金价下跌"
        text2 = "美联储宣布加息25个基点，黄金价格下跌"
        h1 = compute_simhash(text1)
        h2 = compute_simhash(text2)
        dist = hamming_distance(h1, h2)
        self.assertLess(dist, 15)  # 相似文本汉明距离应该较小

    def test_different_texts_large_hamming_distance(self):
        """完全不同的文本汉明距离应该大"""
        text1 = "美联储加息，金价下跌"
        text2 = "欧洲央行按兵不动，欧元上涨"
        h1 = compute_simhash(text1)
        h2 = compute_simhash(text2)
        dist = hamming_distance(h1, h2)
        self.assertGreater(dist, 10)  # 不同文本汉明距离应该较大

    def test_empty_text_hash(self):
        """空文本 SimHash 为 0"""
        self.assertEqual(compute_simhash(""), 0)


class TestNormalization(unittest.TestCase):
    """文本标准化测试"""

    def test_strip_source_prefix(self):
        """应该去除常见的新闻来源前缀"""
        text = "金十数据 9月15日讯 美联储宣布加息"
        normalized = normalize_news_text(text)
        self.assertNotIn("金十数据", normalized)
        self.assertIn("美联储", normalized)

    def test_remove_special_chars(self):
        """应该去除特殊字符"""
        text = "【快讯】金价上涨！"
        normalized = normalize_news_text(text)
        self.assertNotIn("【", normalized)
        self.assertNotIn("】", normalized)
        self.assertNotIn("！", normalized)

    def test_remove_whitespace(self):
        """应该去除所有空白字符"""
        text = "  金价  上涨  \n  "
        normalized = normalize_news_text(text)
        self.assertNotIn(" ", normalized)
        self.assertNotIn("\n", normalized)


class TestTimeWindow(unittest.TestCase):
    """时间窗口测试"""

    def test_within_window(self):
        """时间差在窗口内返回 True"""
        from datetime import datetime
        t1 = datetime(2026, 9, 15, 10, 0, 0)
        t2 = datetime(2026, 9, 15, 11, 0, 0)  # 1小时差
        self.assertTrue(within_time_window(t1, t2))

    def test_outside_window(self):
        """时间差超过窗口返回 False"""
        from datetime import datetime
        t1 = datetime(2026, 9, 15, 10, 0, 0)
        t2 = datetime(2026, 9, 15, 13, 0, 0)  # 3小时差
        self.assertFalse(within_time_window(t1, t2))

    def test_none_time_returns_true(self):
        """时间为 None 时返回 True（放宽条件）"""
        self.assertTrue(within_time_window(None, None))


class TestPerformance(unittest.TestCase):
    """性能测试"""

    def test_1000_records_completes_quickly(self):
        """1000条记录应该在合理时间内完成（不卡死）"""
        import random
        random.seed(42)

        base_phrases = [
            "美联储加息", "金价上涨", "美元走强", "通胀上升",
            "避险情绪升温", "央行购金", "ETF增持", "白银短缺",
        ]

        records = []
        for i in range(1000):
            phrase = random.choice(base_phrases)
            variation = random.randint(0, 100)
            title = f"{phrase}第{i}号新闻"
            content = f"这是关于{phrase}的报道，编号{variation}。"
            hour = random.randint(9, 17)
            minute = random.randint(0, 59)
            publish_time = f"2026-09-15 {hour:02d}:{minute:02d}:00"
            records.append(_make_record(title=title, content=content,
                                         publish_time=publish_time))

        start = time.time()
        result = deduplicate_records(records)
        elapsed = time.time() - start

        # 1000条数据应该在10秒内完成（实际应该远快于这个）
        self.assertLess(elapsed, 10.0, f"去重耗时过长: {elapsed:.2f}秒")
        self.assertGreater(len(result), 0)
        print(f"\n[性能测试] 1000条记录去重耗时: {elapsed:.3f}秒, "
              f"去重后: {len(result)} 条")


class TestMakeDedupKey(unittest.TestCase):
    """精确去重键测试"""

    def test_same_content_same_key(self):
        """相同内容生成相同的 key"""
        r1 = _make_record(title="测试", content="内容")
        r2 = _make_record(title="测试", content="内容")
        self.assertEqual(make_dedup_key(r1), make_dedup_key(r2))

    def test_different_content_different_key(self):
        """不同内容生成不同的 key"""
        r1 = _make_record(title="测试A", content="内容A")
        r2 = _make_record(title="测试B", content="内容B")
        self.assertNotEqual(make_dedup_key(r1), make_dedup_key(r2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
