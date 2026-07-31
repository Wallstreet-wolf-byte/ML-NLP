# ============================================================
# 股市新闻推送与分析系统 - 配置文件
# 第1关：项目骨架
# ============================================================

import os

# --- 项目根目录 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 数据存储路径 ---
DATA_DIR = os.path.join(BASE_DIR, "data")
DICTS_DIR = os.path.join(BASE_DIR, "dicts")

# --- 新闻数据源配置 ---
NEWS_SOURCES = {
    "eastmoney": {
        "name": "东方财富",
        "enabled": True,
        "url": "https://finance.eastmoney.com/a/czqyw.html",
    },
    "cls": {
        "name": "财联社",
        "enabled": True,
        "url": "https://www.cls.cn/telegraph",
    },
    "jinshi": {
        "name": "金十数据",
        "enabled": True,
        "url": "https://www.jin10.com/",
    },
    "sina": {
        "name": "新浪财经",
        "enabled": True,
        "url": "https://finance.sina.com.cn/",
    },
    "wallstreet": {
        "name": "华尔街见闻",
        "enabled": True,
        "url": "https://wallstreetcn.com/",
    },
}

# --- 市场分类关键词 ---
MARKET_KEYWORDS = {
    "A股": ["A股", "上证", "深证", "沪深", "北交所", "科创板", "创业板", "主板"],
    "恒指期货主连": ["港股", "恒生", "港交所", "H股", "港股通", "恒指", "恒生指数", "HSI"],
    "美股": ["美股", "纳斯达克", "标普", "道琼斯", "美联储", "华尔街"],
    "黄金期货": ["黄金", "黄金期货", "COMEX黄金", "贵金属", "沪金", "现货黄金", "金价"],
    "白银期货": ["白银", "白银期货", "COMEX白银", "沪银", "现货白银", "银价"],
    "其他期货": ["原油", "铜", "铝", "铁矿石", "螺纹钢", "大豆", "期货"],
}

# --- 情绪词典配置 ---
# 词典文件路径（后续关卡会填充）
POSITIVE_DICT = os.path.join(DICTS_DIR, "positive.txt")
NEGATIVE_DICT = os.path.join(DICTS_DIR, "negative.txt")

# --- 影响程度阈值 ---
IMPACT_HIGH = 3    # 关键词出现 >= 3 次且来源为高权重
IMPACT_MEDIUM = 1  # 关键词出现 >= 1 次

# --- 网页服务器配置 ---
WEB_HOST = "0.0.0.0"  # 改为 0.0.0.0 可让局域网内其他人访问
WEB_PORT = 5000
WEB_DEBUG = True

# --- 大模型深度分析配置 ---
# 支持 DeepSeek / OpenAI兼容接口 / 阿里通义千问
# 获取API Key: https://platform.deepseek.com/ (注册送500万token)
LLM_CONFIG = {
    "enabled": False,               # 设为True启用大模型分析
    "provider": "deepseek",          # deepseek / openai / qwen
    "api_key": "",                   # 在此填入你的API Key
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "max_news_to_analyze": 20,       # 每次最多让大模型分析多少条（控制成本）
    "temperature": 0.3,              # 低温度=更稳定
}

# --- 国际金融API配置 ---
# Finnhub: 美股新闻、公司动态、市场数据 (免费60次/分钟)
# 注册地址: https://finnhub.io/register
FINNHUB_CONFIG = {
    "enabled": False,               # 设为True启用
    "api_key": "",                   # 在此填入你的Finnhub API Key
    "base_url": "https://finnhub.io/api/v1",
    # 关注的股票代码（美股）
    "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META"],
    # 关注的指数/期货符号
    "indices": ["^GSPC", "^IXIC", "^DJI", "^HSI"],
}

# Alpha Vantage: 全球市场新闻+情绪分析 (免费25次/天)
# 注册地址: https://www.alphavantage.co/support/#api-key
ALPHAVANTAGE_CONFIG = {
    "enabled": False,               # 设为True启用
    "api_key": "",                   # 在此填入你的Alpha Vantage API Key
    "base_url": "https://www.alphavantage.co/api",
    # 关注的话题
    "topics": "financial_markets,technology,economy_fiscal,economy_monetary",
}

# --- 炒股大师Agent配置 ---
# 每位大师以独特的投资理念分析当日市场
MASTER_AGENTS_CONFIG = {
    "enabled": True,                 # 大师Agent总开关（即使没有LLM也能用规则分析）
    # 启用的大师列表
    "masters": [
        "buffett",      # 巴菲特 - 价值投资
        "munger",       # 芒格 - 多元思维
        "lynch",        # 彼得·林奇 - 成长股
        "soros",        # 索罗斯 - 宏观对冲
        "dalio",        # 达利欧 - 全天候
        "graham",       # 格雷厄姆 - 安全边际
    ],
    # 每位大师分析的新闻数量（取影响最大的N条）
    "news_per_master": 15,
    # 是否用大模型生成深度分析（需要LLM_CONFIG.enabled=True）
    "use_llm": True,
}

# --- 定时任务配置 ---
# 每日运行时间（24小时制）
SCHEDULE_TIME = "08:00"