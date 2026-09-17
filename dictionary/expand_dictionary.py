"""
金融情绪词典 Word2Vec 种子词扩展脚本

流程：
1. 加载种子词（手工词典 + 姜富伟词典）
2. 获取财经新闻语料（akshare + 本地快讯）
3. 训练 Word2Vec skip-gram 模型
4. 对每个种子词召回相似候选词
5. 过滤方向矛盾的候选词
6. 人工抽检 + 保存最终词典

用法：
    python expand_dictionary.py --jiang-dict /path/to/中文金融情感词典.xlsx
    python expand_dictionary.py --skip-akshare  # 只用本地快讯
"""

import os
import json
import glob
import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
DICTS_DIR = BASE_DIR.parent / "dicts"
OUTPUT_DIR = BASE_DIR / "output"

# Word2Vec 参数
W2V_VECTOR_SIZE = 100
W2V_WINDOW = 5
W2V_MIN_COUNT = 3
W2V_EPOCHS = 10

# 扩展参数
EXPAND_TOPN = 20
EXPAND_THRESHOLD = 0.6


# ============================================================
# Step 1: 加载种子词
# ============================================================
def load_manual_dict():
    """加载手工构建的情绪词典"""
    pos_file = DICTS_DIR / "positive.txt"
    neg_file = DICTS_DIR / "negative.txt"

    pos_words = []
    neg_words = []

    if pos_file.exists():
        with open(pos_file, "r", encoding="utf-8") as f:
            pos_words = [
                line.strip() for line in f
                if line.strip() and not line.startswith("#")
            ]

    if neg_file.exists():
        with open(neg_file, "r", encoding="utf-8") as f:
            neg_words = [
                line.strip() for line in f
                if line.strip() and not line.startswith("#")
            ]

    print(f"[手工词典] 正面: {len(pos_words)} 词, 负面: {len(neg_words)} 词")
    return pos_words, neg_words


def load_jiang_dict(filepath):
    """加载姜富伟团队中文金融情感词典"""
    if not filepath or not os.path.exists(filepath):
        print("[姜富伟词典] 未提供或文件不存在，跳过")
        return [], []

    try:
        import pandas as pd
        df = pd.read_excel(filepath)
        print(f"[姜富伟词典] 总词数: {len(df)}")
        print(f"  列名: {df.columns.tolist()}")

        # 尝试自动识别列名
        word_col = None
        polarity_col = None
        for col in df.columns:
            if "词" in str(col).lower() or "word" in str(col).lower():
                word_col = col
            if "极" in str(col).lower() or "polar" in str(col).lower() or "情" in str(col).lower():
                polarity_col = col

        if word_col is None:
            word_col = df.columns[0]
        if polarity_col is None:
            print(f"  无法自动识别极性列，跳过姜富伟词典")
            return [], []

        print(f"  词列: {word_col}, 极性列: {polarity_col}")

        # 提取正负面词
        pos_mask = df[polarity_col].astype(str).str.contains("正|积极|pos", case=False, na=False)
        neg_mask = df[polarity_col].astype(str).str.contains("负|消极|neg", case=False, na=False)

        pos_words = df.loc[pos_mask, word_col].astype(str).str.strip().tolist()
        neg_words = df.loc[neg_mask, word_col].astype(str).str.strip().tolist()

        print(f"  正面: {len(pos_words)} 词, 负面: {len(neg_words)} 词")
        return pos_words, neg_words

    except Exception as e:
        print(f"[姜富伟词典] 加载失败: {e}")
        return [], []


def merge_seeds(manual_pos, manual_neg, jiang_pos, jiang_neg):
    """合并去重"""
    all_pos = list(set(manual_pos + jiang_pos))
    all_neg = list(set(manual_neg + jiang_neg))
    # 排除同时出现在正负列表里的模糊词
    ambiguous = set(all_pos) & set(all_neg)
    if ambiguous:
        print(f"[合并] 发现 {len(ambiguous)} 个方向模糊词，删除: {list(ambiguous)[:10]}...")
        all_pos = [w for w in all_pos if w not in ambiguous]
        all_neg = [w for w in all_neg if w not in ambiguous]
    print(f"[合并后种子词] 正面: {len(all_pos)}, 负面: {len(all_neg)}, 总计: {len(all_pos) + len(all_neg)}")
    return all_pos, all_neg


# ============================================================
# Step 2: 获取语料
# ============================================================
def load_local_news(crawler_data_dir=None):
    """加载本地爬虫采集的快讯"""
    if crawler_data_dir is None:
        crawler_data_dir = BASE_DIR.parent / "crawler" / "crawler_data"

    texts = []
    pattern = str(Path(crawler_data_dir) / "**" / "*.json")
    for filepath in glob.glob(pattern, recursive=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    content = item.get("content", "") or item.get("title", "")
                    if content and len(content) > 5:
                        texts.append(content)
        except Exception as e:
            print(f"  跳过 {filepath}: {e}")
    print(f"[本地快讯] 加载 {len(texts)} 条")
    return texts


def load_akshare_news():
    """通过 akshare 获取财经新闻"""
    texts = []
    try:
        import akshare as ak
        print("[akshare] 正在拉取财经新闻...")

        # 东方财富全球财经
        try:
            df = ak.stock_info_global_em()
            if df is not None and len(df) > 0:
                content_col = "内容" if "内容" in df.columns else df.columns[-1]
                texts.extend(df[content_col].astype(str).tolist())
                print(f"  东方财富全球财经: {len(df)} 条")
        except Exception as e:
            print(f"  东方财富全球财经失败: {e}")

        # CCTV 新闻联播文字稿
        try:
            df = ak.news_cctv(date="20260801")
            if df is not None and len(df) > 0:
                content_col = "content" if "content" in df.columns else df.columns[-1]
                texts.extend(df[content_col].astype(str).tolist())
                print(f"  CCTV新闻: {len(df)} 条")
        except Exception as e:
            print(f"  CCTV新闻失败: {e}")

        # 东方财富财经新闻
        try:
            df = ak.stock_info_global_em()
            if df is not None and len(df) > 0:
                title_col = "标题" if "标题" in df.columns else None
                if title_col:
                    texts.extend(df[title_col].astype(str).tolist())
        except:
            pass

    except ImportError:
        print("[akshare] 未安装，请运行 pip install akshare")
    except Exception as e:
        print(f"[akshare] 获取失败: {e}")

    print(f"[akshare] 共获取 {len(texts)} 条新闻")
    return texts


def preprocess_corpus(texts):
    """分词预处理"""
    import jieba

    corpus = []
    for text in texts:
        text = str(text).strip()
        if len(text) < 5:
            continue
        words = list(jieba.cut(text))
        words = [w.strip() for w in words if len(w.strip()) > 0]
        if len(words) >= 2:
            corpus.append(words)

    print(f"[预处理] 有效语料: {len(corpus)} 篇, 总词数: {sum(len(c) for c in corpus)}")
    return corpus


# ============================================================
# Step 3: 训练 Word2Vec + 扩展
# ============================================================
def train_word2vec(corpus):
    """训练 skip-gram 模型"""
    from gensim.models import Word2Vec

    model = Word2Vec(
        corpus,
        vector_size=W2V_VECTOR_SIZE,
        window=W2V_WINDOW,
        min_count=W2V_MIN_COUNT,
        workers=4,
        sg=1,
        epochs=W2V_EPOCHS,
    )

    model_path = OUTPUT_DIR / "word2vec_financial.model"
    model.save(str(model_path))
    print(f"[Word2Vec] 模型已保存: {model_path}")
    print(f"[Word2Vec] 词表大小: {len(model.wv)}")
    return model


def expand_candidates(seeds, model, polarity_label):
    """对种子词做相似词扩展"""
    candidates = []
    for word in seeds:
        if word not in model.wv:
            continue
        similar = model.wv.most_similar(word, topn=EXPAND_TOPN)
        for cand, score in similar:
            if score >= EXPAND_THRESHOLD:
                candidates.append({
                    "word": cand,
                    "source_seed": word,
                    "similarity": round(score, 4),
                    "polarity": polarity_label,
                })
    return candidates


def filter_candidates(pos_candidates, neg_candidates, existing_pos, existing_neg):
    """过滤方向矛盾和已存在的词"""
    pos_words = set(c["word"] for c in pos_candidates)
    neg_words = set(c["word"] for c in neg_candidates)
    all_existing = set(existing_pos) | set(existing_neg)

    # 方向矛盾：同时出现在正负扩展中
    ambiguous = pos_words & neg_words

    # 过滤
    filtered_pos = [
        c for c in pos_candidates
        if c["word"] not in ambiguous and c["word"] not in all_existing
    ]
    filtered_neg = [
        c for c in neg_candidates
        if c["word"] not in ambiguous and c["word"] not in all_existing
    ]

    # 去重：一个候选词可能被多个种子词扩展出来，保留相似度最高的
    def dedup_candidates(candidates):
        best = {}
        for c in candidates:
            w = c["word"]
            if w not in best or c["similarity"] > best[w]["similarity"]:
                best[w] = c
        return list(best.values())

    filtered_pos = dedup_candidates(filtered_pos)
    filtered_neg = dedup_candidates(filtered_neg)

    print(f"[过滤] 正面扩展: {len(pos_candidates)} -> {len(filtered_pos)}")
    print(f"[过滤] 负面扩展: {len(neg_candidates)} -> {len(filtered_neg)}")
    if ambiguous:
        print(f"[过滤] 删除方向矛盾词 {len(ambiguous)} 个: {list(ambiguous)[:10]}...")

    return filtered_pos, filtered_neg


# ============================================================
# Step 4: 组装最终词典
# ============================================================
def build_final_dict(seeds_pos, seeds_neg, expanded_pos, expanded_neg):
    """组装最终词典并保存"""
    import pandas as pd

    records = []

    for w in seeds_pos:
        records.append({
            "word": w, "polarity": "正面", "source": "种子词",
            "similarity": 1.0, "confidence": "人工确认"
        })
    for w in seeds_neg:
        records.append({
            "word": w, "polarity": "负面", "source": "种子词",
            "similarity": 1.0, "confidence": "人工确认"
        })
    for c in expanded_pos:
        records.append({
            "word": c["word"], "polarity": "正面",
            "source": f"Word2Vec扩展(种子:{c['source_seed']})",
            "similarity": c["similarity"], "confidence": f"相似度{c['similarity']}"
        })
    for c in expanded_neg:
        records.append({
            "word": c["word"], "polarity": "负面",
            "source": f"Word2Vec扩展(种子:{c['source_seed']})",
            "similarity": c["similarity"], "confidence": f"相似度{c['similarity']}"
        })

    df = pd.DataFrame(records).drop_duplicates(subset=["word"])
    df = df.sort_values(["polarity", "similarity"], ascending=[True, False])

    output_path = OUTPUT_DIR / "expanded_sentiment_dict.xlsx"
    df.to_excel(str(output_path), index=False)

    n_pos = len(df[df.polarity == "正面"])
    n_neg = len(df[df.polarity == "负面"])
    n_expanded = len(df[df.source != "种子词"])

    print(f"\n[最终词典] 共 {len(df)} 词")
    print(f"  正面: {n_pos} (种子 {n_pos - len(expanded_pos)} + 扩展 {len(expanded_pos)})")
    print(f"  负面: {n_neg} (种子 {n_neg - len(expanded_neg)} + 扩展 {len(expanded_neg)})")
    print(f"  扩展新增: {n_expanded} 词")
    print(f"  已保存: {output_path}")

    # 生成人工抽检样本
    expanded_only = df[df.source != "种子词"]
    if len(expanded_only) > 0:
        sample_size = min(50, len(expanded_only))
        sample = expanded_only.sample(sample_size, random_state=42)
        sample_path = OUTPUT_DIR / "sample_for_review.xlsx"
        sample.to_excel(str(sample_path), index=False)
        print(f"  人工抽检样本({sample_size}词): {sample_path}")

    return df


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="金融情绪词典 Word2Vec 扩展")
    parser.add_argument("--jiang-dict", type=str, default=None,
                        help="姜富伟词典 xlsx 路径")
    parser.add_argument("--skip-akshare", action="store_true",
                        help="不使用 akshare，只用本地快讯")
    parser.add_argument("--crawler-data", type=str, default=None,
                        help="本地快讯数据目录")
    args = parser.parse_args()

    print("=" * 60)
    print("  金融情绪词典 Word2Vec 扩展")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: 加载种子词
    print("\n--- Step 1: 加载种子词 ---")
    manual_pos, manual_neg = load_manual_dict()
    jiang_pos, jiang_neg = load_jiang_dict(args.jiang_dict)
    seeds_pos, seeds_neg = merge_seeds(manual_pos, manual_neg, jiang_pos, jiang_neg)

    # Step 2: 获取语料
    print("\n--- Step 2: 获取语料 ---")
    texts = []
    texts.extend(load_local_news(args.crawler_data))
    if not args.skip_akshare:
        texts.extend(load_akshare_news())
    print(f"[语料总计] {len(texts)} 条文本")

    if len(texts) < 100:
        print("[警告] 语料不足 100 条，Word2Vec 训练质量可能较差")
        print("  建议：1) 用 --skip-akshare 关闭 akshare，先用本地数据")
        print("        2) 或先积累更多爬虫数据再训练")

    # 预处理
    corpus = preprocess_corpus(texts)
    if len(corpus) < 50:
        print("[错误] 有效语料不足 50 篇，无法训练")
        return

    # Step 3: 训练 Word2Vec
    print("\n--- Step 3: 训练 Word2Vec ---")
    model = train_word2vec(corpus)

    # 扩展
    print("\n--- Step 4: 种子词扩展 ---")
    pos_candidates = expand_candidates(seeds_pos, model, "正面")
    neg_candidates = expand_candidates(seeds_neg, model, "负面")
    print(f"[扩展] 正面候选: {len(pos_candidates)} 词")
    print(f"[扩展] 负面候选: {len(neg_candidates)} 词")

    # Step 5: 过滤
    print("\n--- Step 5: 过滤 ---")
    filtered_pos, filtered_neg = filter_candidates(
        pos_candidates, neg_candidates, seeds_pos, seeds_neg
    )

    # Step 6: 组装
    print("\n--- Step 6: 组装最终词典 ---")
    df = build_final_dict(seeds_pos, seeds_neg, filtered_pos, filtered_neg)

    print("\n" + "=" * 60)
    print("  扩展完成！")
    print("  下一步：打开 output/sample_for_review.xlsx 人工抽检")
    print("=" * 60)


if __name__ == "__main__":
    main()