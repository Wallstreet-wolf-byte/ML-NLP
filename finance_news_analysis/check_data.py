import json
import sys

filepath = r"C:\Users\Piper\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a6ab2675449499a1a78ff84\stock_news\data\news_20260730.json"

with open(filepath, "r", encoding="utf-8") as f:
    data = json.load(f)

print("采集时间:", data["collect_date"])
print("总条数:", data["total_count"])
print()

# 统计各来源条数
from collections import Counter
sources = Counter(n["source"] for n in data["news"])
print("各来源分布:")
for src, cnt in sources.items():
    print(f"  {src}: {cnt} 条")

print()
print("各来源前3条样本:")
print("-" * 60)
shown = {}
for n in data["news"]:
    src = n["source"]
    shown[src] = shown.get(src, 0) + 1
    if shown[src] <= 3:
        print(f"[{src}] {n['title'][:50]}")
        print(f"  时间: {n['publish_time']}")
        print(f"  内容: {n['content'][:80]}...")
        print()