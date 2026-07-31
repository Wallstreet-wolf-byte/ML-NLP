# ============================================================
# 一键运行脚本 - 每日定时任务执行
# 完整流程：采集新闻 → 分析分类 → 保存结果
# 用法：python run_pipeline.py
# ============================================================

import os
import sys
import time
from datetime import datetime

# 设置项目目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)


def main():
    print("=" * 60)
    print(f"  股市新闻系统 - 每日自动运行")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # --- 第1步：采集新闻 ---
    print(">>> [1/2] 采集新闻...")
    from crawlers.collector import collect_all_news, save_news

    news = collect_all_news()

    if not news:
        print("\n  采集失败，未获取到新闻，程序退出。")
        return False

    save_news(news)
    print()

    # --- 第2步：分析新闻 ---
    print(">>> [2/2] 分析新闻...")
    from analyzer.analyzer import analyze_news, save_analyzed_news

    news = analyze_news(news)
    filepath = save_analyzed_news(news)

    print()
    print("=" * 60)
    print(f"  每日任务完成！")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  新闻总数: {len(news)} 条")
    print(f"  结果文件: {filepath}")
    print(f"  查看看板: 启动 start_web.bat 后访问 http://127.0.0.1:5000")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)