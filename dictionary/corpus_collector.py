"""
贵金属期货语料采集脚本

功能：
1. 从 akshare 拉取财经新闻（全球财经、新浪财经等）
2. 筛选黄金/白银/贵金属相关新闻
3. 保存为纯文本语料，供 Word2Vec 训练使用
4. 支持增量采集，避免重复

用法：
    python corpus_collector.py --output ./corpus
    python corpus_collector.py --days 30  # 拉取最近30天
"""

import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "corpus"

# 贵金属关键词（用于筛选相关新闻）
# 按精确度分级：high 表示非常确定是贵金属，low 表示可能有歧义
PRECIOUS_METALS_KEYWORDS_HIGH = [
    "金价", "银价", "贵金属", "铂金", "钯金",
    "黄金期货", "白银期货", "沪金", "沪银",
    "伦敦金", "现货黄金", "COMEX黄金", "COMEX白银",
    "黄金ETF", "白银ETF",
    "央行购金", "黄金储备",
    "贵金属价格", "贵金属市场",
    "黄金价格", "白银价格",
    "金十数据", "汇通财经",
]

PRECIOUS_METALS_KEYWORDS_LOW = [
    "黄金",  # 可能有"黄金窗口""黄金大通道"等假阳性
    "白银",  # 相对较少歧义，但也可能有特殊用法
]

# 排除模式：包含"黄金"但不是指贵金属
GOLD_FALSE_POSITIVE_PATTERNS = [
    "黄金窗口", "黄金大通道", "黄金时代", "黄金期", "黄金周",
    "黄金档", "黄金时段", "黄金年龄", "黄金法则", "黄金标准",
    "黄金搭档", "黄金分割", "黄金比例", "黄金水道", "黄金航道",
    "黄金线路", "黄金航线", "黄金赛道", "黄金发展", "黄金增长",
]


def is_precious_metals_news(text):
    """判断新闻是否与贵金属相关"""
    if not text:
        return False
    text = str(text)

    # 高置信度关键词：命中一个就算
    for kw in PRECIOUS_METALS_KEYWORDS_HIGH:
        if kw in text:
            return True

    # 低置信度关键词：需要排除假阳性
    for kw in PRECIOUS_METALS_KEYWORDS_LOW:
        if kw in text:
            # 检查是否是假阳性模式
            is_false_positive = any(pat in text for pat in GOLD_FALSE_POSITIVE_PATTERNS)
            if not is_false_positive:
                return True

    return False


def clean_text(text):
    """清洗文本"""
    if not text:
        return ""
    text = str(text).strip()
    # 去掉多余空白
    text = re.sub(r'\s+', ' ', text)
    # 去掉HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    return text


def load_akshare_global_news(max_pages=3):
    """从东方财富全球财经快讯拉取新闻"""
    texts = []
    try:
        import akshare as ak
        print("[东方财富全球财经] 正在拉取...")
        df = ak.stock_info_global_em()
        if df is not None and len(df) > 0:
            # 尝试找到内容列
            content_col = None
            for col in df.columns:
                if "内容" in str(col) or "text" in str(col).lower():
                    content_col = col
                    break
            if content_col is None:
                # 用最后一列当内容
                content_col = df.columns[-1]

            for _, row in df.iterrows():
                title = str(row.get("标题", "")) if "标题" in df.columns else ""
                content = str(row.get(content_col, ""))
                full_text = clean_text(title + " " + content)
                if len(full_text) > 10:
                    texts.append(full_text)

            print(f"  拉取 {len(df)} 条，筛选后 {len(texts)} 条贵金属相关")
    except ImportError:
        print("[东方财富全球财经] akshare 未安装")
    except Exception as e:
        print(f"[东方财富全球财经] 失败: {e}")
    return texts


def load_akshare_sina_global():
    """从新浪全球财经快讯拉取"""
    texts = []
    try:
        import akshare as ak
        print("[新浪全球财经] 正在拉取...")
        df = ak.stock_info_global_sina()
        if df is not None and len(df) > 0:
            # 新浪的列是 ['时间', '内容']
            content_col = "内容" if "内容" in df.columns else df.columns[-1]
            time_col = "时间" if "时间" in df.columns else df.columns[0]
            for _, row in df.iterrows():
                content = str(row.get(content_col, ""))
                time_str = str(row.get(time_col, ""))
                full_text = clean_text(content)
                if len(full_text) > 10:
                    texts.append(full_text)
            print(f"  拉取 {len(df)} 条")
    except Exception as e:
        print(f"[新浪全球财经] 失败: {e}")
    return texts


def load_akshare_cls_news():
    """从财联社拉取快讯"""
    texts = []
    try:
        import akshare as ak
        print("[财联社快讯] 正在拉取...")
        df = ak.stock_info_global_cls()
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                title = str(row.get("标题", ""))
                content = str(row.get("内容", ""))
                full_text = clean_text(title + " " + content)
                if len(full_text) > 10:
                    texts.append(full_text)
            print(f"  拉取 {len(df)} 条")
    except Exception as e:
        print(f"[财联社快讯] 失败: {e}")
    return texts


def load_akshare_shmet_news():
    """从上海金属网拉取期货新闻（金属相关度高）"""
    texts = []
    try:
        import akshare as ak
        print("[上海金属网] 正在拉取...")
        df = ak.futures_news_shmet()
        if df is not None and len(df) > 0:
            content_col = "内容" if "内容" in df.columns else df.columns[-1]
            for _, row in df.iterrows():
                content = str(row.get(content_col, ""))
                full_text = clean_text(content)
                if len(full_text) > 10:
                    texts.append(full_text)
            print(f"  拉取 {len(df)} 条")
    except Exception as e:
        print(f"[上海金属网] 失败: {e}")
    return texts


def load_akshare_cctv_news(days=7):
    """从CCTV新闻联播文字稿拉取（偏宏观但有参考价值）"""
    texts = []
    try:
        import akshare as ak
        print("[CCTV新闻联播] 正在拉取...")
        today = datetime.now()
        count = 0
        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y%m%d")
            try:
                df = ak.news_cctv(date=date_str)
                if df is not None and len(df) > 0:
                    content_col = "content" if "content" in df.columns else df.columns[-1]
                    for _, row in df.iterrows():
                        content = str(row.get(content_col, ""))
                        content = clean_text(content)
                        if len(content) > 10:
                            texts.append(content)
                    count += 1
            except:
                pass
        print(f"  拉取 {count} 天的新闻联播")
    except Exception as e:
        print(f"[CCTV新闻联播] 失败: {e}")
    return texts


def load_akshare_futures_news():
    """从期货新闻频道拉取"""
    texts = []
    try:
        import akshare as ak
        print("[期货新闻] 正在拉取...")
        # 尝试多个期货相关接口
        try:
            df = ak.futures_news_baidu(symbol="黄金")
            if df is not None and len(df) > 0:
                for _, row in df.iterrows():
                    title = str(row.get("title", row.iloc[0]))
                    content = str(row.get("content", ""))
                    full_text = clean_text(title + " " + content)
                    if len(full_text) > 10:
                        texts.append(full_text)
                print(f"  百度期货黄金: {len(df)} 条")
        except:
            pass
    except Exception as e:
        print(f"[期货新闻] 失败: {e}")
    return texts


def collect_all_corpus(output_dir, days=7, filter_precious=True):
    """采集所有语料并保存"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_texts = []

    # 1. 东方财富全球财经（可能SSL不稳定，失败则跳过）
    texts = load_akshare_global_news()
    all_texts.extend(texts)

    # 2. 新浪全球财经
    texts = load_akshare_sina_global()
    all_texts.extend(texts)

    # 3. 财联社快讯
    texts = load_akshare_cls_news()
    all_texts.extend(texts)

    # 4. 上海金属网（金属相关度最高）
    texts = load_akshare_shmet_news()
    all_texts.extend(texts)

    # 5. CCTV新闻联播（宏观背景，不筛选直接保留）
    texts = load_akshare_cctv_news(days=min(days, 3))
    if filter_precious:
        # 新闻联播不做贵金属筛选，作为宏观背景语料
        macro_texts = texts
    else:
        all_texts.extend(texts)
        macro_texts = []

    # 筛选贵金属相关
    if filter_precious:
        filtered = [t for t in all_texts if is_precious_metals_news(t)]
        print(f"\n[筛选] 全部: {len(all_texts)} 条 -> 贵金属相关: {len(filtered)} 条")
        print(f"[宏观] 新闻联播: {len(macro_texts)} 条（作为背景语料保留）")
        all_texts = filtered + macro_texts
    else:
        print(f"\n[全量] 共 {len(all_texts)} 条")

    # 去重
    unique_texts = list(set(all_texts))
    print(f"[去重] {len(all_texts)} -> {len(unique_texts)} 条")

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = output_dir / f"corpus_{timestamp}.txt"
    json_path = output_dir / f"corpus_{timestamp}.json"

    # 纯文本格式（一行一条，供Word2Vec训练）
    with open(txt_path, "w", encoding="utf-8") as f:
        for text in unique_texts:
            f.write(text + "\n")

    # JSON格式（带元信息）
    records = [{"text": t, "len": len(t)} for t in unique_texts]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n[保存] 纯文本: {txt_path}")
    print(f"[保存] JSON: {json_path}")
    print(f"[统计] 共 {len(unique_texts)} 条，总字数: {sum(len(t) for t in unique_texts)}")

    return unique_texts


def merge_corpus_files(corpus_dir, output_file="merged_corpus.txt"):
    """合并目录下所有语料文件，去重后输出一个大文件"""
    corpus_dir = Path(corpus_dir)
    all_texts = set()

    for txt_file in corpus_dir.glob("corpus_*.txt"):
        with open(txt_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and len(line) > 10:
                    all_texts.add(line)

    output_path = corpus_dir / output_file
    with open(output_path, "w", encoding="utf-8") as f:
        for text in sorted(all_texts):
            f.write(text + "\n")

    print(f"[合并] {len(all_texts)} 条去重后语料 -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="贵金属期货语料采集")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="语料输出目录")
    parser.add_argument("--days", type=int, default=7,
                        help="拉取最近几天的数据（CCTV新闻联播用）")
    parser.add_argument("--no-filter", action="store_true",
                        help="不过滤贵金属关键词，保留全部财经新闻")
    parser.add_argument("--merge", action="store_true",
                        help="只合并已有语料文件，不采集新数据")
    args = parser.parse_args()

    print("=" * 60)
    print("  贵金属期货语料采集工具")
    print("=" * 60)

    if args.merge:
        print("\n--- 合并已有语料 ---")
        merge_corpus_files(args.output)
        return

    print(f"\n输出目录: {args.output}")
    print(f"贵金属筛选: {'关闭' if args.no_filter else '开启'}")

    collect_all_corpus(
        output_dir=args.output,
        days=args.days,
        filter_precious=not args.no_filter,
    )

    # 顺便合并一下
    merge_corpus_files(args.output)

    print("\n" + "=" * 60)
    print("  采集完成！")
    print("  下一步：运行 expand_dictionary.py 训练 Word2Vec 并扩展词典")
    print("=" * 60)


if __name__ == "__main__":
    main()
