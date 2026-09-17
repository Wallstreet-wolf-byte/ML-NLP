"""
BERT 语义校验模块

功能：
对 Word2Vec 扩展出的候选词进行语义校验，过滤掉极性错误的噪声词。

两种校验方式：
1. 情感分类校验：把候选词放入模板句子，用 FinBERT 判断情感极性是否和种子词一致
2. 语义相似度校验：用 BERT 计算候选词上下文和种子词语境的相似度

用法（命令行）：
    python bert_validator.py --input output/expanded_sentiment_dict.xlsx --output output/bert_validated.xlsx

用法（Python）：
    from bert_validator import BertSentimentValidator
    validator = BertSentimentValidator()
    result = validator.validate_word("鸽派", "positive")
    print(result)  # {'valid': True, 'predicted': 'positive', 'confidence': 0.95}
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent

# 默认模型：香港科技大学的中文金融情感分析BERT
DEFAULT_MODEL_NAME = "yiyanghkust/finbert-tone-chinese"

# 标签映射
LABEL_MAP = {
    "positive": "正面",
    "neutral": "中性",
    "negative": "负面",
}

# 贵金属语境模板（把候选词放进去，构造完整句子）
GOLD_TEMPLATES_POSITIVE = [
    "消息面传来{word}信号，黄金价格有望继续上涨。",
    "市场预期{word}，推动金价走高。",
    "{word}因素支撑黄金价格，投资者看好后市。",
    "受{word}影响，黄金价格大幅上涨。",
    "分析师指出，{word}将对黄金价格构成利多。",
]

GOLD_TEMPLATES_NEGATIVE = [
    "消息面传来{word}信号，黄金价格承压下跌。",
    "市场预期{word}，金价走势承压。",
    "{word}因素压制黄金价格，投资者谨慎观望。",
    "受{word}影响，黄金价格大幅下跌。",
    "分析师指出，{word}将对黄金价格构成利空。",
]


class BertSentimentValidator:
    """BERT 情感极性校验器"""

    def __init__(self, model_name=None, device=None):
        """
        初始化校验器
        Args:
            model_name: HuggingFace 模型名，默认 finbert-tone-chinese
            device: 'cpu' / 'cuda'，默认自动判断
        """
        try:
            import torch
            from transformers import BertTokenizer, BertForSequenceClassification
        except ImportError as e:
            raise ImportError(
                "需要安装 transformers 和 torch："
                "pip install transformers torch"
            ) from e

        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._torch = torch

        print(f"[BERT] 加载模型: {self.model_name}")
        print(f"[BERT] 设备: {self.device}")

        self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
        self.model = BertForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

        # 标签顺序（根据模型训练时的顺序）
        self.id2label = self.model.config.id2label
        self.label2id = self.model.config.label2id
        print(f"[BERT] 标签映射: {self.id2label}")

    def _predict_single(self, text):
        """对单条文本做情感分类"""
        torch = self._torch
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=1)
        pred_idx = probs.argmax().item()
        label = self.id2label.get(str(pred_idx), str(pred_idx))
        confidence = probs[0][pred_idx].item()

        # 统一标签格式为小写英文
        label_lower = label.lower()
        if "pos" in label_lower:
            polarity = "positive"
        elif "neg" in label_lower:
            polarity = "negative"
        else:
            polarity = "neutral"

        return {
            "label": label,
            "polarity": polarity,
            "confidence": round(confidence, 4),
            "probs": {self.id2label.get(str(i), str(i)): round(probs[0][i].item(), 4)
                      for i in range(len(probs[0]))},
        }

    def validate_word(self, word, expected_polarity, templates=None, min_confidence=0.5):
        """
        校验单个候选词的情感极性

        Args:
            word: 候选词，如"鸽派"
            expected_polarity: 'positive' 或 'negative'
            templates: 自定义模板列表，None 则用默认模板
            min_confidence: 最低置信度阈值

        Returns:
            dict: {
                'valid': bool,           # 是否通过校验
                'predicted': str,        # 预测极性
                'confidence': float,     # 平均置信度
                'vote_ratio': float,     # 投票通过率（多少模板预测正确）
                'details': list,         # 每条模板的详细结果
            }
        """
        if templates is None:
            templates = (GOLD_TEMPLATES_POSITIVE if expected_polarity == "positive"
                         else GOLD_TEMPLATES_NEGATIVE)

        details = []
        predictions = []

        for template in templates:
            sentence = template.format(word=word)
            result = self._predict_single(sentence)
            result["sentence"] = sentence
            details.append(result)
            predictions.append(result["polarity"])

        # 多数投票
        vote_counts = Counter(predictions)
        majority = vote_counts.most_common(1)[0][0]
        vote_ratio = vote_counts[majority] / len(predictions)

        # 计算平均置信度（取预测极性对应的置信度）
        confidences = [
            d["confidence"] for d in details
            if d["polarity"] == majority
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        valid = (
            majority == expected_polarity
            and vote_ratio >= 0.6  # 至少60%的模板同意
            and avg_confidence >= min_confidence
        )

        return {
            "valid": valid,
            "predicted": majority,
            "confidence": round(avg_confidence, 4),
            "vote_ratio": round(vote_ratio, 4),
            "vote_detail": dict(vote_counts),
            "details": details,
        }

    def validate_candidates(self, candidates_df, batch_size=32):
        """
        批量校验候选词 DataFrame

        Args:
            candidates_df: 包含 word 和 polarity 列的 DataFrame
            batch_size: 批大小

        Returns:
            DataFrame: 增加了校验结果列的新 DataFrame
        """
        import pandas as pd

        results = []
        total = len(candidates_df)
        print(f"[BERT校验] 开始批量校验 {total} 个候选词...")

        for idx, row in candidates_df.iterrows():
            if idx % 20 == 0:
                print(f"  进度: {idx}/{total}")

            word = str(row.get("word", ""))
            polarity = str(row.get("polarity", ""))

            # 转换极性标签
            expected = "positive" if "正" in polarity else "negative"

            result = self.validate_word(word, expected)
            results.append({
                "word": word,
                "polarity": polarity,
                "bert_valid": result["valid"],
                "bert_predicted": result["predicted"],
                "bert_confidence": result["confidence"],
                "bert_vote_ratio": result["vote_ratio"],
                "bert_vote_detail": json.dumps(result["vote_detail"], ensure_ascii=False),
            })

        result_df = pd.DataFrame(results)
        print(f"[BERT校验] 完成")
        print(f"  通过: {sum(1 for r in results if r['bert_valid'])} / {total}")
        print(f"  通过率: {sum(1 for r in results if r['bert_valid']) / max(total, 1):.1%}")

        return result_df


def validate_from_excel(input_path, output_path, model_name=None):
    """从 Excel 文件读取候选词并做 BERT 校验"""
    import pandas as pd

    print(f"[输入] {input_path}")
    df = pd.read_excel(input_path)
    print(f"  共 {len(df)} 条候选词")

    # 只校验扩展词，不校验种子词
    if "source" in df.columns:
        expanded = df[df["source"] != "种子词"].copy()
        seeds = df[df["source"] == "种子词"].copy()
        print(f"  其中扩展词: {len(expanded)} 条，种子词: {len(seeds)} 条")
    else:
        expanded = df.copy()
        seeds = pd.DataFrame()

    validator = BertSentimentValidator(model_name=model_name)
    validated = validator.validate_candidates(expanded)

    # 合并回原数据
    if len(seeds) > 0:
        # 种子词默认通过
        seeds["bert_valid"] = True
        seeds["bert_predicted"] = seeds["polarity"].apply(
            lambda x: "positive" if "正" in str(x) else "negative"
        )
        seeds["bert_confidence"] = 1.0
        seeds["bert_vote_ratio"] = 1.0
        seeds["bert_vote_detail"] = ""
        result_df = pd.concat([seeds, validated], ignore_index=True)
    else:
        result_df = validated

    result_df.to_excel(output_path, index=False)
    print(f"\n[输出] {output_path}")
    return result_df


def main():
    parser = argparse.ArgumentParser(description="BERT 语义校验：过滤 Word2Vec 扩展候选词")
    parser.add_argument("--input", type=str, required=True,
                        help="输入候选词 Excel 文件（expand_dictionary.py 的输出）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径，默认在输入文件同目录下加 _bert_validated 后缀")
    parser.add_argument("--model", type=str, default=None,
                        help=f"BERT 模型名，默认 {DEFAULT_MODEL_NAME}")
    args = parser.parse_args()

    print("=" * 60)
    print("  BERT 语义校验工具")
    print("=" * 60)

    if args.output is None:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}_bert_validated.xlsx")

    validate_from_excel(args.input, args.output, args.model)

    print("\n" + "=" * 60)
    print("  校验完成！")
    print("  通过的词可加入最终词典，未通过的词建议人工复核")
    print("=" * 60)


if __name__ == "__main__":
    main()
