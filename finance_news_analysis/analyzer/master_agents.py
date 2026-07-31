# ============================================================
# 炒股大师 Agent 模块
# 模拟6位投资大师的投资理念，分析当日新闻并给出市场观点
# 支持：大模型深度分析 + 规则分析（无LLM时自动降级）
#
# 大师列表：
#   巴菲特   - 价值投资、护城河、长期持有
#   芒格     - 多元思维、理性分析、品质优先
#   彼得林奇  - 成长股、生活中发现机会、PEG
#   索罗斯   - 宏观对冲、反身性、趋势交易
#   达利欧   - 全天候策略、经济周期、风险平价
#   格雷厄姆  - 安全边际、深度价值、市场先生
# ============================================================

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MASTER_AGENTS_CONFIG, LLM_CONFIG
from models import NewsItem


# ============================================================
# 大师档案定义
# ============================================================

MASTER_PROFILES = {
    "buffett": {
        "name": "沃伦·巴菲特",
        "name_en": "Warren Buffett",
        "emoji": "👴",
        "tagline": "以合理价格买入伟大公司",
        "school": "价值投资",
        "color": "#e53e3e",
        "focus_sectors": ["消费", "银行", "能源", "保险"],
        "focus_keywords": [
            "估值", "护城河", "现金流", "股息", "ROE", "品牌",
            "消费", "垄断", "竞争优势", "长期", "内在价值",
            "茅台", "可口可乐", "苹果", "伯克希尔",
        ],
        "philosophy": (
            "我寻找有持久竞争优势（护城河）的伟大企业。"
            "市场短期是投票机，长期是称重机。"
            "别人贪婪时我恐惧，别人恐惧时我贪婪。"
            "我最喜欢的持股时间是——永远。"
        ),
        "system_prompt": (
            "你是沃伦·巴菲特，价值投资的代表人物。你的分析风格：\n"
            "1. 关注企业的护城河、内在价值和长期竞争力\n"
            "2. 评估新闻对企业长期价值的影响，而非短期波动\n"
            "3. 市场恐慌时看到机会，市场狂热时保持谨慎\n"
            "4. 偏好消费、金融、能源等现金流稳定的行业\n"
            "5. 回复风格：朴实、幽默、用通俗比喻，像在给股东写信\n\n"
            "请根据当日新闻，以巴菲特的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作（如：逢低布局优质消费股/持有观望/减持高估值品种）",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },

    "munger": {
        "name": "查理·芒格",
        "name_en": "Charlie Munger",
        "emoji": "🧠",
        "tagline": "反过来想，总是反过来想",
        "school": "多元思维",
        "color": "#805ad5",
        "focus_sectors": ["科技", "消费", "银行", "医药"],
        "focus_keywords": [
            "理性", "品质", "能力圈", "多元思维", "好公司",
            "常识", "逻辑", "避免愚蠢", "卓越", "安全",
            "比亚迪", "Costco", "喜诗糖果",
        ],
        "philosophy": (
            "如果我知道自己会死在哪里，我就永远不去那个地方。"
            "投资的关键不在于做对的事，而在于避免犯错。"
            "要有多元思维模型，用不同学科的角度看问题。"
            "以合理价格买入好公司，远胜于以好价格买入普通公司。"
        ),
        "system_prompt": (
            "你是查理·芒格，以多元思维和理性分析著称。你的分析风格：\n"
            "1. 用多学科视角分析问题（心理学、经济学、物理学等）\n"
            "2. 先想什么会出错，再考虑如何避免\n"
            "3. 关注企业品质和管理层诚信\n"
            "4. 强调能力圈——不投资看不懂的东西\n"
            "5. 回复风格：犀利、直接、引用智慧格言、偶尔幽默\n\n"
            "请根据当日新闻，以芒格的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },

    "lynch": {
        "name": "彼得·林奇",
        "name_en": "Peter Lynch",
        "emoji": "🏃",
        "tagline": "投资你所了解的",
        "school": "成长投资",
        "color": "#3182ce",
        "focus_sectors": ["消费", "科技", "汽车", "医药"],
        "focus_keywords": [
            "成长", "PEG", "消费", "连锁", "扩张", "故事",
            "盈利增长", "小公司", "十倍股", "生活中发现",
            "新品", "市场份额", "翻倍",
        ],
        "philosophy": (
            "投资你所了解的东西。你在商场里看到的热销产品，"
            "可能就是下一个十倍股的线索。"
            "PEG低于1的公司值得关注。"
            "给公司分类：快速增长型、稳定增长型、周期型、困境反转型。"
        ),
        "system_prompt": (
            "你是彼得·林奇，以成长股投资著称。你的分析风格：\n"
            "1. 从日常生活和消费趋势中发现投资机会\n"
            "2. 关注盈利增长率和PEG比率\n"
            "3. 区分快速增长型、稳定增长型、周期型公司\n"
            "4. 喜欢有故事、有催化剂的成长股\n"
            "5. 回复风格：生动、接地气、用生活中的例子\n\n"
            "请根据当日新闻，以林奇的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },

    "soros": {
        "name": "乔治·索罗斯",
        "name_en": "George Soros",
        "emoji": "🐺",
        "tagline": "先存活，再盈利",
        "school": "宏观对冲",
        "color": "#2f855a",
        "focus_sectors": ["银行", "贵金属", "其他期货", "证券"],
        "focus_keywords": [
            "宏观", "汇率", "货币", "反身性", "泡沫", "趋势",
            "对冲", "做空", "流动性", "央行", "利率",
            "美元", "欧元", "日元", "新兴市场",
        ],
        "philosophy": (
            "市场总是错的，市场价格总是扭曲的。"
            "反身性——参与者的偏见会改变基本面。"
            "先求存活，再求盈利。当你看准时，要敢于重仓。"
            "寻找流行偏见中的漏洞，那是机会所在。"
        ),
        "system_prompt": (
            "你是乔治·索罗斯，以宏观对冲和反身性理论著称。你的分析风格：\n"
            "1. 从宏观经济、货币政策、汇率角度分析\n"
            "2. 寻找市场共识中的错误和偏见\n"
            "3. 关注反身性循环——预期如何影响基本面\n"
            "4. 重视风险管理和头寸规模\n"
            "5. 回复风格：深邃、哲学化、关注宏观趋势\n\n"
            "请根据当日新闻，以索罗斯的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },

    "dalio": {
        "name": "瑞·达利欧",
        "name_en": "Ray Dalio",
        "emoji": "⚙️",
        "tagline": "理解经济机器的运行方式",
        "school": "全天候策略",
        "color": "#d69e2e",
        "focus_sectors": ["贵金属", "能源", "债券", "银行"],
        "focus_keywords": [
            "经济周期", "债务", "通胀", "利率", "多元化",
            "全天候", "原则", "风险平价", "通缩", "繁荣",
            "衰退", "去杠杆", "生产力",
        ],
        "philosophy": (
            "经济是一台机器，由人性、信贷周期和生产力驱动。"
            "理解经济机器的运行方式，才能预判未来。"
            "全天候策略——在任何经济环境下都能表现良好。"
            "痛苦+反思=进步。原则是决策的基础。"
        ),
        "system_prompt": (
            "你是瑞·达利欧，桥水基金创始人，以全天候策略著称。你的分析风格：\n"
            "1. 从经济周期、债务周期和生产力角度分析\n"
            "2. 关注通胀、利率和货币政策对各类资产的影响\n"
            "3. 强调投资组合的平衡和分散\n"
            "4. 用原则驱动的决策框架\n"
            "5. 回复风格：系统性、有条理、像在解释经济原理\n\n"
            "请根据当日新闻，以达利欧的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },

    "graham": {
        "name": "本杰明·格雷厄姆",
        "name_en": "Benjamin Graham",
        "emoji": "📚",
        "tagline": "用安全边际保护自己",
        "school": "深度价值",
        "color": "#718096",
        "focus_sectors": ["银行", "地产建材", "能源", "农业"],
        "focus_keywords": [
            "安全边际", "低估", "净资产", "股息率", "内在价值",
            "市场先生", "清算价值", "净流动资产", "便宜",
            "低市盈率", "低市净率",
        ],
        "philosophy": (
            "市场先生每天都会给你报价，但你不必交易。"
            "当市场先生恐惧时买入，贪婪时卖出。"
            "安全边际是投资的核心——用低于内在价值的价格买入。"
            "分散投资是防范未知风险的最佳方式。"
        ),
        "system_prompt": (
            "你是本杰明·格雷厄姆，价值投资之父。你的分析风格：\n"
            "1. 严格关注安全边际和内在价值\n"
            "2. 寻找市场价格低于内在价值的机会\n"
            "3. 视市场波动为机会而非风险\n"
            "4. 强调分散投资和定量分析\n"
            "5. 回复风格：严谨、学院派、引用投资原则\n\n"
            "请根据当日新闻，以格雷厄姆的视角分析市场，返回JSON：\n"
            "{\n"
            '  "market_view": "对当前市场的总体看法（2-3句）",\n'
            '  "opportunity_sectors": ["看好的板块/方向"],\n'
            '  "risk_sectors": ["需要回避的板块"],\n'
            '  "action": "建议操作",\n'
            '  "key_insight": "一句话核心洞见",\n'
            '  "sentiment": "乐观/谨慎/中性",\n'
            '  "confidence": 0.8\n'
            "}\n只返回JSON，不要其他文字。"
        ),
    },
}


# ============================================================
# 大师择时配置 —— 什么时候要注意
# 每位大师在不同市场环境下的买入信号、卖出信号、关注条件
# ============================================================

MASTER_TIMING_CONFIG = {
    "buffett": {
        "buy_signals": [
            "沪深300市盈率低于12倍、市场恐慌情绪蔓延时",
            "优质消费龙头因系统性风险被错杀、跌幅超20%时",
            "银行/保险股跌破净资产、股息率超5%时",
        ],
        "sell_signals": [
            "市场整体市盈率突破历史90%分位、人人谈论股票时",
            "持有的伟大公司护城河被破坏、长期竞争力逆转时",
            "找不到符合安全边际的新标的、现金无处可投时",
        ],
        "watch_conditions": [
            "关注美联储利率决议及央行货币政策走向",
            "关注消费龙头的季报营收与ROE变化",
            "关注市场整体估值分位（沪深300 PE/PB历史百分位）",
        ],
        "position_range": "5-7成（恐慌时可加至8成以上）",
    },
    "munger": {
        "buy_signals": [
            "优秀管理层的公司因短期利被错杀、品质未变时",
            "能力圈内出现常识性错误定价（如行业被非理性抛售）时",
            "科技龙头估值回归合理、商业模式依然强大时",
        ],
        "sell_signals": [
            "管理层出现诚信问题或战略方向重大失误时",
            "行业格局发生不可逆恶化、原有逻辑被推翻时",
            "市场集体非理性繁荣、好公司被炒到荒谬估值时",
        ],
        "watch_conditions": [
            "关注管理层变动及公司治理质量",
            "关注行业竞争格局变化（集中度提升/恶化）",
            "关注心理偏差导致的群体性错误（追涨杀跌）",
        ],
        "position_range": "4-6成（集中持有少数高品质标的）",
    },
    "lynch": {
        "buy_signals": [
            "PEG低于1的快速增长型公司出现催化剂时",
            "生活中观察到的新品爆卖/连锁扩张趋势初现时",
            "困境反转型公司基本面出现拐点信号时",
        ],
        "sell_signals": [
            "公司故事讲完了、增长逻辑见顶时",
            "PEG超过2、估值透支未来2-3年增长时",
            "快速扩张型公司增速放缓、故事变为周期股时",
        ],
        "watch_conditions": [
            "关注消费新品销量、线下门店扩张数据",
            "关注公司盈利增速与估值匹配度（PEG）",
            "关注行业催化剂（政策、技术突破、新品发布）",
        ],
        "position_range": "6-8成（成长期可适度激进）",
    },
    "soros": {
        "buy_signals": [
            "发现市场共识存在系统性偏差、反身性循环启动时",
            "宏观政策出现重大转向（如央行意外降息/加息）时",
            "汇率/利率出现趋势性突破、流动性环境剧变时",
        ],
        "sell_signals": [
            "反身性循环接近顶点、市场偏见开始纠正时",
            "趋势出现衰竭信号、动量明显减弱时",
            "风险敞口超过预设止损线时（先存活再盈利）",
        ],
        "watch_conditions": [
            "关注美元指数、人民币汇率走势及央行干预",
            "关注市场流动性指标（SHIBOR、逆回购规模）",
            "关注地缘政治风险与宏观政策预期差",
        ],
        "position_range": "3-7成（高确信时敢于重仓，设好止损）",
    },
    "dalio": {
        "buy_signals": [
            "经济处于衰退末期、央行开始宽松时加风险资产",
            "通胀上行周期中配置黄金等抗通胀资产",
            "经济增长超预期时增配股票、风险平价再平衡",
        ],
        "sell_signals": [
            "经济过热、央行开始收紧时降低风险敞口",
            "通缩风险上升时减配商品、增配债券",
            "投资组合偏离风险平价目标时进行再平衡",
        ],
        "watch_conditions": [
            "关注经济周期所处阶段（繁荣/衰退/萧条/复苏）",
            "关注CPI、PPI、PMI等经济先行指标",
            "关注全球央行资产负债表变化及利率路径",
        ],
        "position_range": "全天候均衡配置（股票30%/债券55%/商品15%）",
    },
    "graham": {
        "buy_signals": [
            "个股股价低于净流动资产（NCAV）的2/3时",
            "市盈率低于10倍、市净率低于1倍且股息率超4%时",
            "市场整体大幅下跌、恐惧贪婪指数进入极端恐惧区时",
        ],
        "sell_signals": [
            "股价回升至内在价值附近、安全边际消失时",
            "基本面恶化、净资产价值下降时",
            "市场整体估值过高、找不到低价标的时",
        ],
        "watch_conditions": [
            "关注低估值策略组合（低PE/PB/高股息率篮子）",
            "关注市场整体估值水平与历史均值偏离度",
            "关注净流动资产价值（NCAV）筛选标的",
        ],
        "position_range": "5-7成（严格分散，持有20-30只标的）",
    },
}


# ============================================================
# 具体品种配置 —— 分析黄金、白银、恒指期货、原油、A股/美股大盘
# ============================================================

INSTRUMENT_CONFIG = {
    "黄金期货": {
        "keywords": ["黄金", "金价", "COMEX黄金", "沪金", "现货黄金", "贵金属", "伦敦金", "金矿", "黄金ETF"],
        "category": "商品期货",
        "icon": "🥇",
    },
    "白银期货": {
        "keywords": ["白银", "银价", "COMEX白银", "沪银", "现货白银", "银矿", "金银比"],
        "category": "商品期货",
        "icon": "🥈",
    },
    "恒指期货主连": {
        "keywords": ["恒生", "恒指", "港股", "HSI", "恒生指数", "港交所", "H股", "港股通", "恒生科技"],
        "category": "股指期货",
        "icon": "🇭🇰",
    },
    "原油": {
        "keywords": ["原油", "油价", "WTI", "布伦特", "OPEC", "减产", "石油", "炼油"],
        "category": "商品期货",
        "icon": "🛢️",
    },
    "A股大盘": {
        "keywords": ["上证", "沪深", "A股", "创业板", "科创板", "北交所", "中证", "两市"],
        "category": "股指",
        "icon": "🇨🇳",
    },
    "美股大盘": {
        "keywords": ["美股", "纳斯达克", "标普", "道琼斯", "美联储", "华尔街", "纳指"],
        "category": "股指",
        "icon": "🇺🇸",
    },
}

# 每位大师对各品种的专属观点
MASTER_INSTRUMENT_VIEWS = {
    "soros": {
        "黄金期货": "黄金是对冲法币信用的终极工具，关注实际利率和美元走势。央行大放水时，黄金的反身性循环最强——价格上涨吸引更多买盘，强化上涨趋势。",
        "白银期货": "白银兼具贵金属和工业属性，波动比黄金更大。金银比扩大到80以上是白银的买入信号，均值回归时弹性极强。",
        "恒指期货主连": "港股受中美博弈和外资流向双重影响，是宏观对冲的重要工具。关注南下资金动向和美元周期，恒指期货的反身性特征明显。",
        "原油": "原油价格反映全球需求温度，OPEC减产和地缘冲突是主要催化剂。关注趋势突破和持仓变化，趋势交易者要敢于在突破时加仓。",
        "A股大盘": "A股受政策和流动性驱动，反身性表现尤为明显。信贷脉冲和政策转向是关键信号，关注市场共识中的系统性偏差。",
        "美股大盘": "美股是全球风险偏好风向标，美联储政策和科技股盈利是核心驱动。注意反身性循环是否接近顶点——乐观情绪本身会推动价格。",
    },
    "dalio": {
        "黄金期货": "黄金是全天候组合的核心配置，在通胀周期和债务危机中提供保护。建议长期持有15%左右黄金敞口，它是穿越经济周期的压舱石。",
        "白银期货": "白银波动较大，适合在经济繁荣期增配。金银比回归均值时可做轮动，但在风险平价框架中白银占比不宜过高。",
        "恒指期货主连": "港股反映中国经济和全球资金的交汇，在风险平价框架中作为新兴市场配置的一部分。关注中国经济周期定位。",
        "原油": "原油是经济温度计，繁荣期涨、衰退期跌。在全天候组合中通过商品配置平滑波动，关注供需平衡和库存周期。",
        "A股大盘": "A股代表中国经济基本面，从经济周期角度配置。衰退末期加仓、繁荣期减仓，关注信贷条件和PMI等先行指标。",
        "美股大盘": "美股是全球最大股票市场，在全天候组合中占股票配置核心。关键判断经济处于繁荣/衰退/萧条/复苏哪个阶段。",
    },
    "buffett": {
        "黄金期货": "黄金不产生现金流，我不会买黄金。但金价上涨反映的通胀预期值得关注——它告诉你法币在贬值。与其买金条，不如买能随通胀涨价的伟大企业。",
        "白银期货": "白银和黄金一样不产生收益。如果看好白银，我宁愿买生产白银的优质矿业公司——至少它们有利润和分红。",
        "恒指期货主连": "港股中有不少低估的优质蓝筹值得关注。但关键看企业护城河，而非指数点位。好公司跌了反而该高兴。",
        "原油": "原油是典型周期行业，我偏好买入优质能源公司而非炒作油价。低油价时反而是捡便宜的好时机——伟大企业在寒冬中更强大。",
        "A股大盘": "A股整体估值不高时值得关注，重点找有持久竞争优势的伟大公司。市场恐慌时正是好时机。",
        "美股大盘": "美股估值偏高时需谨慎，但伟大的美国企业长期依然有竞争力。别因市场狂热而追高，等好价格。",
    },
    "graham": {
        "黄金期货": "黄金是防御性资产，在市场恐慌和货币贬值时提供保护。从安全边际角度，黄金ETF可占组合5-10%，作为分散风险的工具。",
        "白银期货": "白银波动剧烈、投机性强。价值投资者应谨慎参与，除非出现极端低估的情况。严格控制在组合的5%以内。",
        "恒指期货主连": "港股有不少低市盈率、低市净率的标的，符合安全边际原则。恒指整体低估时是分散买入的好时机。",
        "原油": "原油价格波动大，难以用内在价值衡量。关注低估值能源股而非油价本身，用定量方法筛选低PE/PB组合。",
        "A股大盘": "A股整体市盈率低于历史均值时，是分散买入的好时机。用定量方法筛选低PE/PB、高股息率的篮子，持有20-30只分散风险。",
        "美股大盘": "美股估值偏高时需格外谨慎。寻找市净率低于1、股息率高于4%的深度价值标的，严格遵循安全边际原则。",
    },
    "lynch": {
        "黄金期货": "金价上涨时，黄金矿业股是典型的周期型机会。关注产量增长、成本控制好的金矿公司——它们在金价上涨时利润弹性巨大。",
        "白银期货": "白银有工业属性，新能源和光伏需求增长是长期催化剂。关注银矿股的成长故事，但PEG要合理。",
        "恒指期货主连": "港股中有不少被低估的成长股，南下资金流入是重要催化剂。关注科技和消费成长股的扩张故事。",
        "原油": "油价低迷时，困境反转的能源公司值得关注。但故事要讲得通——是周期底部而非基本面恶化。区分周期股和成长股。",
        "A股大盘": "A股市场里PEG低于1的快速增长型公司不少。去生活中发现线索——热销产品、新店扩张都是十倍股的种子。",
        "美股大盘": "美股科技巨头增长依然强劲，但要看PEG是否合理。关注新品发布、市场份额变化和盈利加速的催化剂。",
    },
    "munger": {
        "黄金期货": "黄金不是好的投资标的——它不产生任何东西。但作为通胀对冲，少量配置可以理解。反过来想：为什么这么多人炒金亏钱？因为追涨杀跌。",
        "白银期货": "白银投机性太强，不在我的能力圈内。反过来想，大多数人亏钱的原因是情绪化交易，与其冒险不如守住能力圈。",
        "恒指期货主连": "港股有好的科技公司，但要在能力圈内投资。关注商业模式的持久竞争优势，而非短期指数波动。",
        "原油": "原油行业资本密集、周期性强，不是好生意。但低油价时优质能源公司值得关注——好生意+好价格才是机会。",
        "A股大盘": "A股波动大、情绪驱动明显。利用市场的非理性，在恐慌时买入好公司。避免愚蠢比追求聪明更重要。",
        "美股大盘": "美股好公司多，但估值要合理。宁可错过也不做蠢事——以合理价格买入好公司，远胜于以好价格买入普通公司。",
    },
}


# ============================================================
# 规则分析（无LLM时自动降级使用）
# ============================================================

def _rule_based_analysis(master_key: str, news_list: List[dict]) -> dict:
    """
    基于规则的大师分析（当LLM不可用时使用）
    根据每位大师关注的领域和关键词，筛选相关新闻并生成详细观点
    包含：具体板块分析、择时提示、关注要点、风险等级、仓位建议
    """
    profile = MASTER_PROFILES[master_key]
    timing = MASTER_TIMING_CONFIG.get(master_key, {})
    focus_keywords = profile["focus_keywords"]
    focus_sectors = profile["focus_sectors"]

    # ---- 1. 筛选与大师关注领域相关的新闻 ----
    relevant_news = []
    for n in news_list:
        text = f"{n.get('title', '')} {n.get('content', '')}"
        sectors = n.get("affected_sectors", [])
        sentiment = n.get("sentiment", "中性")

        relevance_score = 0
        for kw in focus_keywords:
            if kw in text:
                relevance_score += 1
        for s in sectors:
            if s in focus_sectors:
                relevance_score += 2

        if relevance_score > 0:
            relevant_news.append({
                "news": n,
                "relevance": relevance_score,
                "sentiment": sentiment,
            })

    relevant_news.sort(key=lambda x: x["relevance"], reverse=True)
    top_relevant = relevant_news[:10]

    # ---- 2. 统计情绪分布 ----
    pos_count = sum(1 for r in top_relevant if r["sentiment"] == "利好")
    neg_count = sum(1 for r in top_relevant if r["sentiment"] == "利空")
    neu_count = sum(1 for r in top_relevant if r["sentiment"] == "中性")
    total_relevant = len(top_relevant)

    # ---- 3. 板块情绪分析（具体模块分析） ----
    sector_detail = {}  # {板块: {利好: N, 利空: N, 中性: N, 新闻: [标题...]}}
    for r in top_relevant:
        for s in r["news"].get("affected_sectors", []):
            if s not in sector_detail:
                sector_detail[s] = {"利好": 0, "利空": 0, "中性": 0, "news": []}
            sector_detail[s][r["sentiment"]] = sector_detail[s].get(r["sentiment"], 0) + 1
            title = r["news"].get("title", "")
            if title and len(sector_detail[s]["news"]) < 3:
                sector_detail[s]["news"].append(title)

    opportunity_sectors = []
    risk_sectors = []
    for sector, counts in sector_detail.items():
        if counts["利好"] > counts["利空"]:
            opportunity_sectors.append(sector)
        elif counts["利空"] > counts["利好"]:
            risk_sectors.append(sector)

    # ---- 4. 生成具体板块分析（detailed_analysis） ----
    detailed_analysis = []
    # 大师对各板块的专属评语模板
    master_sector_views = {
        "buffett": {"消费": "消费是持久护城河的沃土，关注品牌壁垒和定价权", "银行": "银行股看净息差和资产质量，低估值是机会", "能源": "能源是周期股，要在低估时买入而非追涨", "保险": "保险的浮存金是优质资金来源，看好低成本浮存金"},
        "munger": {"科技": "科技要看重网络效应和转换成本，但要在能力圈内", "消费": "消费品看复购率和品牌心智，好生意简单易懂", "银行": "银行关注风控文化和管理层质量", "医药": "医药研发有不确定性，要看管线深度"},
        "lynch": {"消费": "消费新品爆卖是十倍股的起点，去商场找线索", "科技": "科技看成长催化剂，新品发布和份额提升是信号", "汽车": "汽车看销量拐点和新车型周期", "医药": "医药看新药审批和适应症扩展"},
        "soros": {"银行": "银行股是宏观流动性的晴雨表，关注信贷周期", "贵金属": "黄金是对冲法币信用的工具，关注实际利率", "证券": "券商是市场情绪放大器，反身性最强", "其他期货": "大宗商品看全球需求和美元周期"},
        "dalio": {"贵金属": "黄金在通胀周期中是核心配置，对冲法币贬值", "能源": "能源价格反映经济温度，关注供需平衡", "债券": "债券是全天候组合的压舱石，看利率周期", "银行": "银行股反映信贷周期，关注经济所处阶段"},
        "graham": {"银行": "银行看市净率，破净是安全边际的信号", "地产建材": "地产看资产重估价值，低PB有机会", "能源": "能源股看股息率和净资产折价", "农业": "农业看周期底部和资产价值"},
    }
    sector_views = master_sector_views.get(master_key, {})

    for sector, counts in sector_detail.items():
        if counts["利好"] >= counts["利空"] and counts["利好"] > 0:
            signal = "利好"
        elif counts["利空"] > counts["利好"]:
            signal = "利空"
        else:
            signal = "中性"

        master_view = sector_views.get(sector, f"该板块今日{counts['利好']}条利好、{counts['利空']}条利空，需结合估值判断")
        reasoning = f"今日{sector}板块相关新闻{counts['利好']+counts['利空']+counts['中性']}条，其中利好{counts['利好']}条、利空{counts['利空']}条。{master_view}。"

        detailed_analysis.append({
            "sector": sector,
            "signal": signal,
            "reasoning": reasoning,
            "related_news": counts["news"],
            "master_view": master_view,
        })

    # 按信号强度排序：利好在前，利空次之
    signal_order = {"利好": 0, "利空": 1, "中性": 2}
    detailed_analysis.sort(key=lambda x: signal_order.get(x["signal"], 3))

    # ---- 5. 生成市场观点和操作建议 ----
    if total_relevant == 0:
        market_view = "今日新闻中与我的投资领域关联不大，市场整体处于常态运行。我会保持耐心，等待更好的机会出现。"
        sentiment = "中性"
        action = "保持观望，等待安全边际充足的机会"
    else:
        if pos_count > neg_count and pos_count > 0:
            sentiment = "乐观"
            if master_key == "buffett":
                market_view = f"今日与我关注领域相关的{total_relevant}条新闻中，利好居多（{pos_count}条利好 vs {neg_count}条利空）。市场似乎给了我们一些机会，但不要因为价格上涨就兴奋——真正要看的是企业的长期竞争力是否在增强。"
                action = "关注被低估的优质消费和金融股，逢低布局；但勿追高，保留现金等待更佳击球区"
            elif master_key == "soros":
                market_view = f"相关新闻{total_relevant}条中利好占优。但要注意，市场的乐观情绪本身可能就是反身性循环的开始——价格上升改变预期，预期又推动价格。关键是判断这个循环还能持续多久。"
                action = "关注趋势加速的方向顺势参与，但必须设好止损，反身性逆转时速度极快"
            elif master_key == "dalio":
                market_view = f"今日{total_relevant}条相关新闻显示市场情绪偏多。从经济周期角度看，需要确认这是趋势性改善还是短期波动——关键看信贷增速和生产率变化。"
                action = "适度增加风险资产敞口，但保持全天候组合的风险平价，不要偏离原则"
            elif master_key == "lynch":
                market_view = f"今日相关新闻{total_relevant}条，利好占多数（{pos_count}条）。市场情绪积极，但更重要的是去生活中验证——公司故事是否依然成立？催化剂是否真的出现了？"
                action = "重点研究有利好催化剂的成长股，关注PEG低于1的快速扩张型公司"
            elif master_key == "munger":
                market_view = f"相关新闻{total_relevant}条中利好居多。利好是好事，但反过来想：这些利好是否已被市场充分定价？好公司不等于好价格。"
                action = "在能力圈内精选高品质标的，避免追逐热点，宁可错过也不做蠢事"
            else:
                market_view = f"今日{total_relevant}条相关新闻中利好占多。市场情绪积极，但价值投资者要关注安全边际而非追涨。"
                action = "寻找估值低于内在价值的标的，分散分批建仓"
        elif neg_count > pos_count and neg_count > 0:
            sentiment = "谨慎"
            if master_key == "buffett":
                market_view = f"相关新闻{total_relevant}条中利空较多（{neg_count}条利空）。市场恐慌时往往是好机会，但前提是企业的长期竞争力没有受损——要区分暂时性困难与永久性损伤。"
                action = "持有优质资产不慌张，逢大跌时分批加仓伟大公司，现金是最好的弹药"
            elif master_key == "soros":
                market_view = f"利空新闻占多数。如果市场形成负面反身性循环，跌幅可能超出预期——预期恶化导致抛售，抛售加剧基本面恶化。先存活，再盈利。"
                action = "控制仓位防范系统性风险，可适度对冲；若发现反身性接近拐点，准备反向布局"
            elif master_key == "graham":
                market_view = f"市场情绪偏空（{neg_count}条利空），但市场先生的恐惧恰恰是价值投资者的朋友——他给出的低价正是安全边际的来源。"
                action = "积极寻找跌破内在价值的标的，用定量方法筛选低PE/PB组合，分批买入"
            elif master_key == "dalio":
                market_view = f"今日{total_relevant}条相关新闻利空偏多。从经济周期看，需判断这是周期性回调还是趋势性衰退——关注信贷条件和就业数据。"
                action = "降低风险敞口，增加防御性资产配置（债券/黄金），等待周期信号明朗"
            elif master_key == "lynch":
                market_view = f"利空新闻偏多，但恐慌中往往蕴含困境反转的机会。关键看：是暂时性困境还是基本面恶化？故事是否还在？"
                action = "筛选被错杀的成长股，关注困境反转型公司的拐点信号，但仓位要轻"
            elif master_key == "munger":
                market_view = f"利空新闻{neg_count}条占多。反过来想：这些利空是否创造了避免犯错的机会？市场的恐慌是否让好公司变得便宜了？"
                action = "审视持仓品质是否受损，若品质未变则逆向加仓；若逻辑已变则果断止损"
            else:
                market_view = f"今日{total_relevant}条相关新闻中利空占多。需要谨慎评估风险，但恐慌中往往蕴含机会。"
                action = "降低仓位，等待更明确的信号，保留现金弹药"
        else:
            sentiment = "中性"
            market_view = f"相关新闻{total_relevant}条，多空相对平衡。市场没有给出明确的信号，此时最好的策略就是耐心等待——不交易也是一种交易。"
            action = "维持现有仓位，保持耐心，等待信号明确后再行动"

    # ---- 6. 择时提示（timing_signals）：根据当前情绪匹配择时信号 ----
    timing_signals = []
    if sentiment == "谨慎" and neg_count > pos_count:
        # 恐慌环境 → 展示买入信号
        for sig in timing.get("buy_signals", [])[:2]:
            timing_signals.append({"type": "买入时机", "signal": sig})
    elif sentiment == "乐观" and pos_count > neg_count:
        # 乐观环境 → 展示卖出/止盈信号
        for sig in timing.get("sell_signals", [])[:2]:
            timing_signals.append({"type": "止盈/减仓时机", "signal": sig})
    else:
        # 中性环境 → 展示观望条件
        timing_signals.append({"type": "观望条件", "signal": "多空平衡，耐心等待趋势明朗后再做决策"})
        if timing.get("buy_signals"):
            timing_signals.append({"type": "潜在买入时机", "signal": timing["buy_signals"][0]})

    # ---- 7. 关注要点（watch_points） ----
    watch_points = list(timing.get("watch_conditions", []))

    # 根据新闻动态补充实时关注要点
    high_impact_news = [r for r in top_relevant if r["news"].get("impact_level") == "高"]
    if high_impact_news:
        watch_points.insert(0, f"今日有{len(high_impact_news)}条高影响新闻，密切跟踪后续发酵")

    # ---- 8. 风险等级与仓位建议 ----
    if sentiment == "谨慎":
        risk_level = "偏高"
        position_advice = "建议降低至3-5成仓位，保留现金等待机会"
    elif sentiment == "乐观":
        risk_level = "中等"
        position_advice = timing.get("position_range", "建议5-7成仓位")
    else:
        risk_level = "中性"
        position_advice = timing.get("position_range", "建议维持5成左右均衡仓位")

    # ---- 9. 市场阶段判断 ----
    if pos_count > neg_count * 2:
        market_phase = "情绪偏热"
    elif neg_count > pos_count * 2:
        market_phase = "情绪偏冷"
    elif total_relevant == 0:
        market_phase = "平淡期"
    else:
        market_phase = "震荡平衡"

    # ---- 10. 核心洞见 ----
    insights = {
        "buffett": "价格是你付出的，价值是你得到的。关注企业内在价值，而非市场报价。",
        "munger": "反过来想，总是反过来想。先确保不犯错，再考虑如何盈利。",
        "lynch": "只要公司的故事没变，股价的短期波动反而是买入机会。",
        "soros": "市场总是错的，你的任务是在错误被纠正前发现它。",
        "dalio": "理解经济机器的运行方式，在周期中找到你的位置。",
        "graham": "市场先生是你的仆人，不是你的主人。利用他的情绪，而非被它左右。",
    }

    # ---- 11. 具体品种分析（黄金、白银、恒指期货、原油、A股/美股大盘） ----
    instrument_views = MASTER_INSTRUMENT_VIEWS.get(master_key, {})
    instrument_analysis = []

    for inst_name, inst_cfg in INSTRUMENT_CONFIG.items():
        inst_keywords = inst_cfg["keywords"]
        inst_news = []
        inst_pos = 0
        inst_neg = 0
        inst_neu = 0

        for n in news_list:
            text = f"{n.get('title', '')} {n.get('content', '')}"
            # 也检查 markets 字段是否直接匹配品种名
            markets = n.get("markets", [])
            if inst_name not in markets and not any(kw in text for kw in inst_keywords):
                continue

            sentiment_val = n.get("sentiment", "中性")
            if sentiment_val == "利好":
                inst_pos += 1
            elif sentiment_val == "利空":
                inst_neg += 1
            else:
                inst_neu += 1

            title = n.get("title", "")
            if title:
                inst_news.append({
                    "title": title,
                    "sentiment": sentiment_val,
                    "impact": n.get("impact_level", "低"),
                    "source": n.get("source", ""),
                    "url": n.get("url", ""),
                })

        inst_total = inst_pos + inst_neg + inst_neu
        if inst_total == 0:
            continue  # 没有相关新闻就跳过该品种

        # 判断品种信号
        if inst_pos > inst_neg and inst_pos > 0:
            inst_signal = "偏多"
        elif inst_neg > inst_pos and inst_neg > 0:
            inst_signal = "偏空"
        else:
            inst_signal = "中性"

        # 大师对该品种的策略建议
        master_view = instrument_views.get(inst_name, f"该品种今日{inst_total}条相关新闻，多空均衡，需结合基本面判断")

        # 根据大师风格和信号生成策略
        if inst_signal == "偏多":
            if master_key == "soros":
                strategy = "趋势偏多，可顺势参与但设好止损，关注反身性循环是否加速"
            elif master_key == "dalio":
                strategy = "偏多信号，在风险平价框架内适度增配"
            elif master_key == "buffett":
                strategy = "偏多但不追涨，关注相关优质公司的长期价值"
            elif master_key == "graham":
                strategy = "偏多但需确认安全边际，分批建仓不追高"
            elif master_key == "lynch":
                strategy = "偏多，关注相关成长股的催化剂和PEG"
            else:
                strategy = "偏多但在能力圈内操作，避免情绪化追涨"
        elif inst_signal == "偏空":
            if master_key == "soros":
                strategy = "偏空信号，控制风险敞口，若趋势加速可顺势做空"
            elif master_key == "dalio":
                strategy = "偏空，降低该品种敞口，增加防御性配置"
            elif master_key == "buffett":
                strategy = "偏空反而可能是机会，等待恐慌后逢低布局相关优质标的"
            elif master_key == "graham":
                strategy = "偏空若致低估，是安全边际充足的买入时机"
            elif master_key == "lynch":
                strategy = "偏空需区分周期性下跌还是基本面恶化，困境反转需谨慎"
            else:
                strategy = "偏空时保持理性，反过来想是否有逆向机会"
        else:
            strategy = "多空均衡，耐心等待信号明确后再行动"

        # 新闻摘要（最多5条）
        news_digest = "；".join([f"{n['title']}" for n in inst_news[:5]])

        instrument_analysis.append({
            "instrument": inst_name,
            "icon": inst_cfg["icon"],
            "category": inst_cfg["category"],
            "signal": inst_signal,
            "news_count": inst_total,
            "positive": inst_pos,
            "negative": inst_neg,
            "neutral": inst_neu,
            "master_view": master_view,
            "strategy": strategy,
            "news_digest": news_digest,
            "related_news": [n["title"] for n in inst_news[:3]],
        })

    # 按信号排序：偏多在前，偏空次之，中性最后
    inst_signal_order = {"偏多": 0, "偏空": 1, "中性": 2}
    instrument_analysis.sort(key=lambda x: inst_signal_order.get(x["signal"], 3))

    return {
        "master_key": master_key,
        "master_name": profile["name"],
        "master_emoji": profile["emoji"],
        "school": profile["school"],
        "tagline": profile["tagline"],
        "color": profile["color"],
        "market_view": market_view,
        "opportunity_sectors": opportunity_sectors[:5],
        "risk_sectors": risk_sectors[:5],
        "action": action,
        "key_insight": insights.get(master_key, "保持理性，坚持自己的投资原则。"),
        "sentiment": sentiment,
        "confidence": 0.65,
        "relevant_news_count": total_relevant,
        "analysis_method": "规则分析",
        # ---- 新增详细分析字段 ----
        "detailed_analysis": detailed_analysis[:6],
        "timing_signals": timing_signals,
        "watch_points": watch_points[:5],
        "risk_level": risk_level,
        "position_advice": position_advice,
        "market_phase": market_phase,
        "philosophy": profile.get("philosophy", ""),
        # ---- 具体品种分析 ----
        "instrument_analysis": instrument_analysis,
    }


# ============================================================
# 大模型分析
# ============================================================

def _llm_analyze_master(master_key: str, news_list: List[dict]) -> Optional[dict]:
    """
    使用大模型以大师的视角分析新闻，生成包含择时提示的详细分析
    """
    profile = MASTER_PROFILES[master_key]
    timing = MASTER_TIMING_CONFIG.get(master_key, {})

    if not LLM_CONFIG.get("enabled") or not LLM_CONFIG.get("api_key"):
        return None

    # 准备新闻摘要
    news_per_master = MASTER_AGENTS_CONFIG.get("news_per_master", 15)
    news_summary = "\n".join([
        f"{i+1}. [{n.get('sentiment','')}] [{n.get('impact_level','')}影响] "
        f"{n.get('title', '')}"
        for i, n in enumerate(news_list[:news_per_master])
    ])

    user_message = (
        f"以下是今日{len(news_list)}条重要财经新闻的摘要（展示前{min(news_per_master, len(news_list))}条）：\n\n"
        f"{news_summary}\n\n"
        f"请以{profile['name']}（{profile['school']}）的投资视角分析这些新闻对市场的影响。\n"
        f"返回JSON，必须包含以下字段：\n"
        '{\n'
        '  "market_view": "对当前市场的总体看法（3-4句，结合具体新闻）",\n'
        '  "detailed_analysis": [{"sector":"板块名","signal":"利好/利空/中性","reasoning":"具体分析（为什么看好/看空，引用相关新闻）","master_view":"该大师对此板块的专属观点"}],\n'
        '  "opportunity_sectors": ["看好的板块"],\n'
        '  "risk_sectors": ["需要回避的板块"],\n'
        '  "action": "建议操作（具体到仓位和方向）",\n'
        '  "timing_signals": [{"type":"买入时机/止盈减仓时机/观望条件","signal":"具体的择时触发条件"}],\n'
        '  "watch_points": ["需要持续关注的要点（如政策事件、经济数据等）"],\n'
        '  "risk_level": "偏低/中等/偏高",\n'
        '  "position_advice": "仓位建议（如：建议5-7成仓位）",\n'
        '  "market_phase": "情绪偏热/情绪偏冷/震荡平衡/平淡期",\n'
        '  "instrument_analysis": [{"instrument":"品种名(如黄金期货/白银期货/恒指期货主连/原油/A股大盘/美股大盘)","signal":"偏多/偏空/中性","master_view":"该大师对此品种的专属观点","strategy":"具体策略建议","news_count":相关新闻数}],\n'
        '  "key_insight": "一句话核心洞见",\n'
        '  "sentiment": "乐观/谨慎/中性",\n'
        '  "confidence": 0.85\n'
        '}\n只返回JSON，不要其他文字。'
    )

    messages = [
        {"role": "system", "content": profile["system_prompt"]},
        {"role": "user", "content": user_message},
    ]

    import requests

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
    }

    payload = {
        "model": LLM_CONFIG.get("model", "deepseek-chat"),
        "messages": messages,
        "temperature": LLM_CONFIG.get("temperature", 0.4),
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    base_url = LLM_CONFIG.get("base_url", "https://api.deepseek.com/v1")
    url = f"{base_url}/chat/completions"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            return None

        # 解析JSON
        result = json.loads(content)

        # 补充大师信息
        result["master_key"] = master_key
        result["master_name"] = profile["name"]
        result["master_emoji"] = profile["emoji"]
        result["school"] = profile["school"]
        result["tagline"] = profile["tagline"]
        result["color"] = profile["color"]
        result["relevant_news_count"] = len(news_list[:news_per_master])
        result["analysis_method"] = "大模型分析"
        result["confidence"] = result.get("confidence", 0.85)
        result["philosophy"] = profile.get("philosophy", "")

        # 如果LLM未返回新字段，用择时配置补全
        if not result.get("timing_signals"):
            result["timing_signals"] = [
                {"type": "买入时机", "signal": s} for s in timing.get("buy_signals", [])[:2]
            ]
        if not result.get("watch_points"):
            result["watch_points"] = timing.get("watch_conditions", [])
        if not result.get("position_advice"):
            result["position_advice"] = timing.get("position_range", "建议5-7成仓位")
        if not result.get("detailed_analysis"):
            result["detailed_analysis"] = []
        if not result.get("risk_level"):
            result["risk_level"] = "中等"
        if not result.get("market_phase"):
            result["market_phase"] = "震荡平衡"
        if not result.get("instrument_analysis"):
            result["instrument_analysis"] = []

        return result

    except Exception as e:
        print(f"  [大师Agent] {profile['name']} 大模型分析失败: {e}")
        return None


# ============================================================
# 主入口：运行所有大师分析
# ============================================================

def run_master_agents(news_list: List) -> List[dict]:
    """
    运行所有启用的大师Agent，返回分析结果列表
    """
    if not MASTER_AGENTS_CONFIG.get("enabled"):
        print("  [大师Agent] 未启用（在config.py中设置MASTER_AGENTS_CONFIG.enabled=True）")
        return []

    enabled_masters = MASTER_AGENTS_CONFIG.get("masters", [])
    use_llm = MASTER_AGENTS_CONFIG.get("use_llm", True) and LLM_CONFIG.get("enabled")

    print()
    print("=" * 60)
    print(f"  炒股大师 Agent 分析  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  启用大师: {len(enabled_masters)} 位")
    print(f"  分析方式: {'大模型深度分析' if use_llm else '规则分析'}")
    print("=" * 60)

    # 将 NewsItem 转为 dict（如果需要）
    news_dicts = []
    for n in news_list:
        if isinstance(n, dict):
            news_dicts.append(n)
        else:
            news_dicts.append(n.to_dict())

    # 按影响程度排序，取重要新闻
    impact_order = {"高": 0, "中": 1, "低": 2}
    news_dicts.sort(key=lambda x: impact_order.get(x.get("impact_level", "低"), 3))

    results = []

    for master_key in enabled_masters:
        if master_key not in MASTER_PROFILES:
            print(f"  [大师Agent] 未知大师: {master_key}，跳过")
            continue

        profile = MASTER_PROFILES[master_key]
        print(f"\n  [{profile['emoji']}] {profile['name']} 正在分析...")

        result = None

        # 优先使用大模型
        if use_llm:
            result = _llm_analyze_master(master_key, news_dicts)

        # 大模型失败或未启用时，降级为规则分析
        if result is None:
            print(f"  [{profile['emoji']}] {profile['name']} 使用规则分析...")
            result = _rule_based_analysis(master_key, news_dicts)

        if result:
            results.append(result)
            print(f"  [{profile['emoji']}] {profile['name']}: {result.get('sentiment', '中性')} - {result.get('key_insight', '')[:40]}...")

    print()
    print("=" * 60)
    print(f"  大师Agent分析完成！共 {len(results)} 位大师给出观点")
    print("=" * 60)

    return results


if __name__ == "__main__":
    # 测试：从数据文件加载新闻并运行大师分析
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    today = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(data_dir, f"news_analyzed_{today}.json")

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        news_list = data.get("news", [])
        print(f"  加载 {len(news_list)} 条新闻")
        results = run_master_agents(news_list)
        print(f"\n  大师分析结果:")
        for r in results:
            print(f"\n  {r['master_emoji']} {r['master_name']} ({r['school']})")
            print(f"    情绪: {r['sentiment']}")
            print(f"    观点: {r['market_view']}")
            print(f"    建议: {r['action']}")
            print(f"    洞见: {r['key_insight']}")
    else:
        print(f"  找不到数据文件: {filepath}")
