# ============================================================
# 大盘指数模块
# 获取 A股、美股、韩股主要指数的实时行情
# 数据源：东方财富 push2 API（免费，无需API Key）
#
# 指数列表：
#   A股大盘：上证50、沪深300、中证500、中证1000
#   美股大盘：道琼斯、纳斯达克、标普500
#   韩股：KOSPI
# ============================================================

import requests
import random
from datetime import datetime
from typing import List, Dict, Optional


# ============================================================
# 指数配置
# ============================================================

# 东方财富 secid 格式：市场.代码
# 1 = 上交所, 0 = 深交所, 100 = 国际指数, 116 = 韩国市场
INDEX_CONFIG = [
    # --- A股大盘 ---
    {"secid": "1.000016", "code": "000016", "name": "上证50", "market": "A股", "group": "A股大盘",
     "desc": "上海市场规模最大、流动性最好的50只蓝筹股"},
    {"secid": "1.000300", "code": "000300", "name": "沪深300", "market": "A股", "group": "A股大盘",
     "desc": "沪深两市规模最大、流动性最好的300只股票"},
    {"secid": "1.000905", "code": "000905", "name": "中证500", "market": "A股", "group": "A股大盘",
     "desc": "排除沪深300后，市值中等的500只股票"},
    {"secid": "1.000852", "code": "000852", "name": "中证1000", "market": "A股", "group": "A股大盘",
     "desc": "市值较小的1000只股票，反映小盘股走势"},
    # --- 美股大盘 ---
    {"secid": "100.DJIA", "code": "DJIA", "name": "道琼斯", "market": "美股", "group": "美股大盘",
     "desc": "美国30家最大上市公司的股价加权指数"},
    {"secid": "100.NDX", "code": "NDX", "name": "纳斯达克", "market": "美股", "group": "美股大盘",
     "desc": "纳斯达克交易所上市公司综合指数"},
    {"secid": "100.SPX", "code": "SPX", "name": "标普500", "market": "美股", "group": "美股大盘",
     "desc": "美国500家最大上市公司的市值加权指数"},
    # --- 韩股 ---
    {"secid": "116.KOSPI", "code": "KOSPI", "name": "KOSPI", "market": "韩股", "group": "韩股",
     "sina_code": "b_KOSPI",
     "desc": "韩国证券交易所综合股价指数"},
]


# ============================================================
# 获取指数实时行情
# ============================================================

def fetch_index_data() -> Dict:
    """
    从东方财富获取所有指数的实时行情
    返回: {"indices": [...], "fetch_time": "...", "source": "..."}
    """
    base_url = "http://push2.eastmoney.com/api/qt/stock/get"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }

    # 需要的字段: f43=最新价, f44=最高, f45=最低, f46=开盘,
    #            f47=成交量, f48=成交额, f57=代码, f58=名称,
    #            f60=昨收, f169=涨跌额, f170=涨跌幅
    fields = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"

    indices_result = []

    for cfg in INDEX_CONFIG:
        secid = cfg["secid"]
        params = {
            "secid": secid,
            "fields": fields,
            "fltt": "2",  # 2=保留小数
        }

        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=8)
            resp.raise_for_status()
            body = resp.json()
            d = body.get("data", {})

            if not d or d.get("f43") is None or d.get("f43") == "-":
                # 东方财富无数据，尝试新浪备用源
                sina_code = cfg.get("sina_code")
                if sina_code:
                    sina_data = _fetch_from_sina(sina_code, cfg)
                    if sina_data:
                        indices_result.append(sina_data)
                        continue
                # 新浪也失败，用模拟数据
                idx_data = _generate_mock_index(cfg)
                idx_data["data_source"] = "模拟数据"
            else:
                latest = _safe_float(d.get("f43"))
                prev_close = _safe_float(d.get("f60"))
                change = _safe_float(d.get("f169"))
                change_pct = _safe_float(d.get("f170"))
                high = _safe_float(d.get("f44"))
                low = _safe_float(d.get("f45"))
                open_price = _safe_float(d.get("f46"))
                volume = _safe_float(d.get("f47"))
                amount = _safe_float(d.get("f48"))

                # 如果涨跌额为0或异常，用最新价-昨收计算
                if change == 0 and latest > 0 and prev_close > 0:
                    change = latest - prev_close
                if change_pct == 0 and prev_close > 0:
                    change_pct = round((change / prev_close) * 100, 2)

                idx_data = {
                    **cfg,
                    "latest": latest,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "high": high,
                    "low": low,
                    "open": open_price,
                    "volume": volume,
                    "amount": amount,
                    "data_source": "东方财富实时",
                }

        except Exception as e:
            print(f"  [大盘指数] 东方财富获取 {cfg['name']} 失败: {e}")
            # 尝试新浪备用源
            sina_code = cfg.get("sina_code")
            if sina_code:
                sina_data = _fetch_from_sina(sina_code, cfg)
                if sina_data:
                    indices_result.append(sina_data)
                    continue
            idx_data = _generate_mock_index(cfg)
            idx_data["data_source"] = "模拟数据"

        indices_result.append(idx_data)

    # 按分组排序
    group_order = {"A股大盘": 0, "美股大盘": 1, "韩股": 2}
    indices_result.sort(key=lambda x: group_order.get(x.get("group", ""), 3))

    return {
        "indices": indices_result,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "东方财富",
        "total": len(indices_result),
    }


def _safe_float(val) -> float:
    """安全转换为 float，无效值返回 0"""
    if val is None or val == "-" or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _fetch_from_sina(sina_code: str, cfg: dict) -> Optional[dict]:
    """
    从新浪财经获取指数行情（东方财富不可用时的备用源）
    新浪返回格式: var hq_str_b_KOSPI="韩国KOSPI指数,5593.56,-69.68,-1.23,..."
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        }
        url = f"http://hq.sinajs.cn/list={sina_code}"
        resp = requests.get(url, headers=headers, timeout=8)
        resp.encoding = "gbk"
        text = resp.text.strip()

        # 解析: var hq_str_xxx="field1,field2,..."
        if '="' not in text:
            return None

        content = text.split('="')[1].rstrip('";')
        fields = content.split(",")
        if len(fields) < 4:
            return None

        # 新浪国际指数字段: 名称,最新价,涨跌额,涨跌幅,...,昨收,今开,最高,最低
        latest = _safe_float(fields[1])
        change = _safe_float(fields[2])
        change_pct = _safe_float(fields[3])
        prev_close = _safe_float(fields[8]) if len(fields) > 8 else (latest - change)
        open_price = _safe_float(fields[9]) if len(fields) > 9 else 0
        high = _safe_float(fields[10]) if len(fields) > 10 else 0
        low = _safe_float(fields[11]) if len(fields) > 11 else 0

        if latest == 0:
            return None

        return {
            **cfg,
            "latest": latest,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "high": high,
            "low": low,
            "open": open_price,
            "volume": 0,
            "amount": 0,
            "data_source": "新浪财经实时",
        }
    except Exception as e:
        print(f"  [大盘指数] 新浪获取 {cfg['name']} 失败: {e}")
        return None


def _generate_mock_index(cfg: dict) -> dict:
    """
    生成模拟指数数据（当 API 不可用时使用）
    基于真实指数的大致价格范围生成
    """
    base_prices = {
        "上证50": 2600, "沪深300": 3900, "中证500": 5500, "中证1000": 5500,
        "道琼斯": 40000, "纳斯达克": 18000, "标普500": 5500, "KOSPI": 2700,
    }

    base = base_prices.get(cfg["name"], 3000)
    change_pct = round(random.uniform(-2.5, 2.5), 2)
    change = round(base * change_pct / 100, 2)
    latest = round(base + change, 2)
    high = round(latest * random.uniform(1.0, 1.01), 2)
    low = round(latest * random.uniform(0.99, 1.0), 2)
    open_price = round(base * random.uniform(0.995, 1.005), 2)

    return {
        **cfg,
        "latest": latest,
        "prev_close": base,
        "change": change,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "open": open_price,
        "volume": 0,
        "amount": 0,
    }


# ============================================================
# 生成大盘综合研判
# ============================================================

def generate_market_summary(indices: List[dict]) -> dict:
    """
    根据指数涨跌情况生成大盘综合研判
    """
    if not indices:
        return {"summary": "暂无指数数据", "a_share_trend": "未知", "us_trend": "未知"}

    # A股趋势
    a_share = [i for i in indices if i.get("market") == "A股"]
    us_share = [i for i in indices if i.get("market") == "美股"]
    kr_share = [i for i in indices if i.get("market") == "韩股"]

    def _trend(group):
        if not group:
            return "未知"
        up = sum(1 for i in group if i.get("change_pct", 0) > 0)
        down = sum(1 for i in group if i.get("change_pct", 0) < 0)
        avg_pct = sum(i.get("change_pct", 0) for i in group) / len(group)
        if up > down and avg_pct > 0.5:
            return "偏强"
        elif down > up and avg_pct < -0.5:
            return "偏弱"
        else:
            return "震荡"

    a_trend = _trend(a_share)
    us_trend = _trend(us_share)
    kr_trend = _trend(kr_share)

    # 综合研判
    parts = []
    if a_share:
        a_pct = [f"{i['name']}{i['change_pct']:+.2f}%" for i in a_share]
        parts.append(f"A股方面：{', '.join(a_pct)}，整体{a_trend}")
    if us_share:
        u_pct = [f"{i['name']}{i['change_pct']:+.2f}%" for i in us_share]
        parts.append(f"美股方面：{', '.join(u_pct)}，整体{us_trend}")
    if kr_share:
        k = kr_share[0]
        parts.append(f"韩股方面：{k['name']}{k['change_pct']:+.2f}%，{kr_trend}")

    summary = "；".join(parts) + "。"

    return {
        "summary": summary,
        "a_share_trend": a_trend,
        "us_trend": us_trend,
        "kr_trend": kr_trend,
    }


if __name__ == "__main__":
    print("  测试大盘指数模块...")
    result = fetch_index_data()
    print(f"\n  获取时间: {result['fetch_time']}")
    print(f"  数据源: {result['source']}")
    print(f"  指数数量: {result['total']}")
    print()

    for idx in result["indices"]:
        arrow = "🔴" if idx["change_pct"] > 0 else "🟢" if idx["change_pct"] < 0 else "⚪"
        print(f"  {arrow} [{idx['group']}] {idx['name']}: {idx['latest']:.2f} "
              f"({idx['change_pct']:+.2f}%) [{idx['data_source']}]")

    print()
    summary = generate_market_summary(result["indices"])
    print(f"  大盘综合研判: {summary['summary']}")
    print(f"  A股趋势: {summary['a_share_trend']} | 美股趋势: {summary['us_trend']} | 韩股趋势: {summary['kr_trend']}")
