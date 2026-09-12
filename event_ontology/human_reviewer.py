"""
人工抽检工具

功能：
对事件抽取结果进行人工抽检，计算精确率，生成抽检报告。

三种抽检模式：
1. 随机抽检：随机抽取N条人工复核
2. 按事件类型抽检：每种类型各抽几条
3. 按置信度抽检：只抽检边界case（程度=不确定、或多空交织）

用法：
    # 生成抽检样本
    python human_reviewer.py --input extracted_events.json --sample 50

    # 抽检完成后，计算精确率
    python human_reviewer.py --input extracted_events.json --review reviewed.json --report
"""

import os
import re
import json
import random
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_events(input_path):
    """加载事件抽取结果"""
    input_path = Path(input_path)
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def generate_sample(events, sample_size=50, mode="random"):
    """
    生成抽检样本

    Args:
        events: 事件抽取结果列表
        sample_size: 样本数量
        mode: 抽样模式
            - random: 完全随机
            - by_type: 按事件类型分层抽样
            - edge: 抽检边界case（多空交织、不确定程度）
    """
    if mode == "random":
        if len(events) <= sample_size:
            return list(events)
        return random.sample(events, sample_size)

    elif mode == "by_type":
        # 按事件类型分层，每种类型抽同等数量
        type_buckets = defaultdict(list)
        for event in events:
            for etype in event.get("event_types", "").split(","):
                if etype:
                    type_buckets[etype].append(event)

        samples = []
        n_types = len(type_buckets)
        per_type = max(1, sample_size // n_types)

        for etype, bucket in type_buckets.items():
            if len(bucket) <= per_type:
                samples.extend(bucket)
            else:
                samples.extend(random.sample(bucket, per_type))

        # 打乱顺序
        random.shuffle(samples)
        return samples[:sample_size]

    elif mode == "edge":
        # 抽检边界case
        edge_cases = []
        for event in events:
            extraction = event.get("extraction", {})
            summary = extraction.get("summary", {})

            # 多空交织
            if summary.get("net_direction") == "mixed":
                edge_cases.append(event)
                continue

            # 有不确定程度的事件
            has_uncertain = any(
                e.get("degree") == "uncertain"
                for e in extraction.get("events", [])
            )
            if has_uncertain:
                edge_cases.append(event)
                continue

            # 事件数量很多（>=5）
            if summary.get("total_events", 0) >= 5:
                edge_cases.append(event)

        if len(edge_cases) <= sample_size:
            return edge_cases
        return random.sample(edge_cases, sample_size)

    else:
        raise ValueError(f"Unknown mode: {mode}")


def save_sample_for_review(samples, output_path):
    """保存待抽检样本，增加review字段"""
    review_items = []
    for idx, item in enumerate(samples):
        extraction = item.get("extraction", {})
        review_item = {
            "sample_id": idx,
            "text": item.get("content", item.get("text", "")),
            "time": item.get("time", ""),
            "source": item.get("source", ""),
            "predicted_events": extraction.get("events", []),
            "predicted_summary": extraction.get("summary", {}),
            "predicted_commodities": extraction.get("commodities", []),
            # 人工标注字段
            "reviewed": False,
            "correct_events": [],        # 正确的事件列表
            "missed_events": [],         # 漏掉的事件
            "wrong_events": [],          # 错误的事件
            "overall_correct": None,     # 整体是否正确（True/False/Partial）
            "comment": "",               # 备注
        }
        review_items.append(review_item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(review_items, f, ensure_ascii=False, indent=2)

    print(f"[抽检] 生成 {len(review_items)} 条抽检样本 -> {output_path}")
    print(f"       请人工标注后，用 --review 模式计算精确率")
    return review_items


def calculate_metrics(reviewed_items):
    """
    计算抽检指标

    Returns:
        dict: 各项评估指标
    """
    reviewed = [item for item in reviewed_items if item.get("reviewed")]
    total = len(reviewed)

    if total == 0:
        return {"error": "没有已标注的样本"}

    # 整体准确率
    fully_correct = sum(
        1 for item in reviewed if item.get("overall_correct") == True
    )
    partial_correct = sum(
        1 for item in reviewed if item.get("overall_correct") == "Partial"
    )
    wrong = sum(
        1 for item in reviewed if item.get("overall_correct") == False
    )

    # 事件级别统计
    total_predicted = 0
    total_correct_events = 0
    total_missed = 0
    total_wrong = 0

    # 按事件类型统计
    type_stats = defaultdict(lambda: {
        "predicted": 0,
        "correct": 0,
        "missed": 0,
        "wrong": 0,
    })

    for item in reviewed:
        predicted = item.get("predicted_events", [])
        correct = item.get("correct_events", [])
        missed = item.get("missed_events", [])
        wrong = item.get("wrong_events", [])

        total_predicted += len(predicted)
        total_correct_events += len(correct)
        total_missed += len(missed)
        total_wrong += len(wrong)

        for evt in predicted:
            etype = evt.get("event_type", "unknown")
            type_stats[etype]["predicted"] += 1

        for evt in correct:
            etype = evt.get("event_type", "unknown")
            type_stats[etype]["correct"] += 1

        for evt in missed:
            etype = evt.get("event_type", "unknown")
            type_stats[etype]["missed"] += 1

        for evt in wrong:
            etype = evt.get("event_type", "unknown")
            type_stats[etype]["wrong"] += 1

    # 精确率 = 正确的 / 预测的
    precision = total_correct_events / total_predicted if total_predicted > 0 else 0
    # 召回率 = 正确的 / (正确的 + 漏掉的)
    recall = total_correct_events / (total_correct_events + total_missed) if (total_correct_events + total_missed) > 0 else 0
    # F1
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_samples": total,
        "fully_correct": fully_correct,
        "partial_correct": partial_correct,
        "wrong": wrong,
        "sample_accuracy": fully_correct / total,
        "predicted_events": total_predicted,
        "correct_events": total_correct_events,
        "missed_events": total_missed,
        "wrong_events": total_wrong,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "type_breakdown": {
            etype: {
                "predicted": stats["predicted"],
                "correct": stats["correct"],
                "missed": stats["missed"],
                "wrong": stats["wrong"],
                "precision": round(stats["correct"] / stats["predicted"], 4) if stats["predicted"] > 0 else 0,
                "recall": round(stats["correct"] / (stats["correct"] + stats["missed"]), 4) if (stats["correct"] + stats["missed"]) > 0 else 0,
            }
            for etype, stats in type_stats.items()
        }
    }


def print_report(metrics):
    """打印抽检报告"""
    print("\n" + "=" * 60)
    print("  人工抽检报告")
    print("=" * 60)

    print(f"\n【样本级指标】")
    print(f"  总样本数: {metrics['total_samples']}")
    print(f"  完全正确: {metrics['fully_correct']}")
    print(f"  部分正确: {metrics['partial_correct']}")
    print(f"  完全错误: {metrics['wrong']}")
    print(f"  样本准确率: {metrics['sample_accuracy']:.1%}")

    print(f"\n【事件级指标】")
    print(f"  预测事件数: {metrics['predicted_events']}")
    print(f"  正确事件数: {metrics['correct_events']}")
    print(f"  漏掉事件数: {metrics['missed_events']}")
    print(f"  错误事件数: {metrics['wrong_events']}")
    print(f"  精确率 (Precision): {metrics['precision']:.1%}")
    print(f"  召回率 (Recall): {metrics['recall']:.1%}")
    print(f"  F1 分数: {metrics['f1']:.1%}")

    print(f"\n【各事件类型明细】")
    for etype, stats in sorted(
        metrics["type_breakdown"].items(),
        key=lambda x: x[1]["predicted"],
        reverse=True,
    ):
        print(f"  {etype}:")
        print(f"    预测:{stats['predicted']} 正确:{stats['correct']} "
              f"漏:{stats['missed']} 错:{stats['wrong']}")
        print(f"    精确率:{stats['precision']:.1%} 召回率:{stats['recall']:.1%}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="人工抽检工具")
    parser.add_argument("--input", type=str, required=True,
                        help="事件抽取结果 JSON 文件")
    parser.add_argument("--sample", type=int, default=0,
                        help="生成抽检样本的数量")
    parser.add_argument("--mode", type=str, default="random",
                        choices=["random", "by_type", "edge"],
                        help="抽样模式：random(随机) / by_type(按类型) / edge(边界case)")
    parser.add_argument("--review", type=str, default=None,
                        help="已标注的抽检结果文件，传入后计算指标")
    parser.add_argument("--report", action="store_true",
                        help="生成并打印抽检报告")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子，保证可复现")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 60)
    print("  人工抽检工具")
    print("=" * 60)

    # 模式1：生成抽检样本
    if args.sample > 0:
        print(f"\n--- 生成抽检样本（模式: {args.mode}, 数量: {args.sample}）---")
        events = load_events(args.input)
        print(f"[加载] 共 {len(events)} 条事件")

        samples = generate_sample(events, args.sample, args.mode)

        output_path = args.output or str(
            OUTPUT_DIR / f"review_sample_{args.mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        save_sample_for_review(samples, output_path)
        return

    # 模式2：计算抽检结果
    if args.review:
        print(f"\n--- 计算抽检指标 ---")
        with open(args.review, "r", encoding="utf-8") as f:
            reviewed = json.load(f)

        metrics = calculate_metrics(reviewed)

        if args.report:
            print_report(metrics)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            print(f"\n[保存] 抽检报告: {args.output}")

        return

    parser.print_help()


if __name__ == "__main__":
    main()
