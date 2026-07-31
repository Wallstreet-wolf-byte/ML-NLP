# ============================================================
# 大模型深度分析模块
# 支持DeepSeek / OpenAI兼容接口 / 通义千问
# 对高影响新闻进行深度分析：走势预测、影响解读、操作建议
# ============================================================

import os
import sys
import json
import requests
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LLM_CONFIG
from models import NewsItem


# --- 系统提示词 ---
SYSTEM_PROMPT = """你是一位资深的金融分析师，擅长分析财经新闻对股市的影响。

请对以下新闻进行深度分析，返回JSON格式结果：

{
    "sentiment": "利好/利空/中性",
    "impact_level": "高/中/低",
    "affected_markets": ["A股", "恒指期货主连", "美股", "黄金期货", "白银期货", "其他期货"],
    "affected_sectors": ["半导体", "新能源", ...],
    "impact_analysis": "简要分析这条新闻对市场的具体影响（50-100字）",
    "trend_prediction": "预测短期走势方向和可能幅度（如：短期利空A股科技板块，预计回调2-3%）",
    "action_suggestion": "操作建议（如：持有观望/适当减仓/关注反弹机会）",
    "confidence": 0.8
}

注意：
- sentiment 和 impact_level 必须是上述指定值之一
- confidence 为 0-1 之间的浮点数，表示你对分析的把握程度
- 分析要简洁有力，不要冗长
- 只返回JSON，不要其他文字"""


def _call_llm(messages: List[Dict]) -> Optional[str]:
    """
    调用大模型API
    支持 DeepSeek / OpenAI兼容接口
    """
    if not LLM_CONFIG.get("api_key"):
        print("  [大模型] 未配置API Key，跳过大模型分析")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
    }

    payload = {
        "model": LLM_CONFIG.get("model", "deepseek-chat"),
        "messages": messages,
        "temperature": LLM_CONFIG.get("temperature", 0.3),
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    base_url = LLM_CONFIG.get("base_url", "https://api.deepseek.com/v1")
    url = f"{base_url}/chat/completions"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except requests.exceptions.HTTPError as e:
        print(f"  [大模型] API请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  [大模型] 响应: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  [大模型] 请求异常: {e}")
        return None


def _parse_llm_response(response_text: str) -> Optional[dict]:
    """解析大模型返回的JSON"""
    if not response_text:
        return None

    try:
        # 尝试直接解析JSON
        result = json.loads(response_text)
        return result
    except json.JSONDecodeError:
        # 尝试提取JSON部分
        import re
        match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"  [大模型] JSON解析失败，原始响应: {response_text[:100]}...")
        return None


def analyze_single_news(news: NewsItem) -> Optional[dict]:
    """
    用大模型分析单条新闻
    返回分析结果字典，失败返回None
    """
    user_message = f"新闻标题：{news.title}\n新闻内容：{news.content}\n来源：{news.source}\n时间：{news.publish_time}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    response = _call_llm(messages)
    if response:
        return _parse_llm_response(response)
    return None


def analyze_news_batch(news_list: List[NewsItem]) -> List[NewsItem]:
    """
    批量用大模型分析新闻
    只分析高影响新闻（控制API成本）
    返回更新后的新闻列表（添加了深度分析字段）
    """
    if not LLM_CONFIG.get("enabled"):
        print("  [大模型] 大模型分析未启用（在config.py中设置LLM_CONFIG.enabled=True）")
        return news_list

    if not LLM_CONFIG.get("api_key"):
        print("  [大模型] 未配置API Key，请在config.py中填入")
        return news_list

    # 只分析高影响新闻，且限制数量
    max_count = LLM_CONFIG.get("max_news_to_analyze", 20)
    high_impact_news = [n for n in news_list if n.impact_level == "高"][:max_count]

    print(f"  [大模型] 开始深度分析 {len(high_impact_news)} 条高影响新闻...")
    print(f"  [大模型] 模型: {LLM_CONFIG.get('model', 'deepseek-chat')}")

    success_count = 0
    for i, news in enumerate(high_impact_news, 1):
        print(f"  [大模型] ({i}/{len(high_impact_news)}) 分析: {news.title[:30]}...")

        result = analyze_single_news(news)

        if result:
            # 更新新闻的深度分析字段
            news.sentiment = result.get("sentiment", news.sentiment)
            news.impact_level = result.get("impact_level", news.impact_level)
            news.llm_analysis = result.get("impact_analysis", "")
            news.llm_prediction = result.get("trend_prediction", "")
            news.llm_suggestion = result.get("action_suggestion", "")
            news.llm_confidence = result.get("confidence", 0)
            success_count += 1

    print(f"  [大模型] 分析完成: {success_count}/{len(high_impact_news)} 条成功")

    return news_list


def generate_daily_summary(news_list: List[NewsItem]) -> Optional[str]:
    """
    让大模型生成当日市场总结
    """
    if not LLM_CONFIG.get("enabled") or not LLM_CONFIG.get("api_key"):
        return None

    # 准备高影响新闻摘要
    high_impact = [n for n in news_list if n.impact_level == "高"][:15]
    if not high_impact:
        return None

    news_summary = "\n".join([
        f"{i+1}. [{n.source}] {n.title} (情绪:{n.sentiment})"
        for i, n in enumerate(high_impact)
    ])

    summary_prompt = f"""请根据以下今日重要财经新闻，生成一份简短的市场分析总结（200-300字）：

{news_summary}

请包含：
1. 今日市场整体情绪（偏多/偏空/震荡）
2. 需要重点关注的板块和方向
3. 明日操作建议"""

    messages = [
        {"role": "system", "content": "你是资深金融分析师，请简洁有力地分析。"},
        {"role": "user", "content": summary_prompt},
    ]

    response = _call_llm(messages)
    return response if response else None