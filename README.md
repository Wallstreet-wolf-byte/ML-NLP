# ML-NLP

面向贵金属期货的**事件驱动舆情数据引擎**与结构化事件抽取系统。将非结构化7×24财经快讯转化为结构化事件数据，为事件驱动型量化研究提供可计算的数据基础。

## 项目定位

本项目不是简单的"情绪分析"，而是更完整的**事件抽取 + 价格映射研究框架**：

```
非结构化财经快讯
        ↓
【数据层】多源采集 + 去重 + 清洗 + OCR + 翻译
        ↓
【事件层】结构化事件抽取（事件类型 × 方向 × 程度）
        ↓
【词典层】触发词词库（Word2Vec扩展 → BERT校验 → 人工抽检）
        ↓
【指数层】日度事件指数（按类型/方向/程度聚合）
        ↓
【研究层】事件驱动价格映射 / 因子检验
```

## 项目结构

```
ML-NLP/
├── crawler/        # 多源财经快讯采集引擎
│   ├── clients/                  # 金十数据、汇通财经、财联社等5源
│   ├── common/                   # 两层去重、工具函数
│   ├── config.py
│   └── main.py
│
├── extractor/               # 事件本体与抽取（核心）
│   ├── extractor.json       # 10类事件本体定义（触发词+程度词+方向）
│   ├── event_extractor.py        # 事件抽取器（规则驱动，可解释）
│   └── human_reviewer.py         # 人工抽检工具（精确率/召回率/F1）
│
├── dicts/                        # 贵金属情绪词典（兼容旧版）
│   ├── positive.txt              # 正面触发词（10类）
│   ├── negative.txt              # 负面触发词（10类）
│   └── negation.txt              # 否定翻转词
│
├── dictionary/              # 词典扩展管线
│   ├── expand_dictionary.py      # Word2Vec 种子词扩展
│   ├── bert_validator.py         # FinBERT 上下文语义校验
│   ├── corpus_collector.py       # akshare 语料采集（补充用）
│   ├── sentiment_scorer.py       # 词典法情绪打分（旧版）
│   └── requirements.txt
│
└── README.md
```

## 事件本体（三级标注体系）

### 10类定价驱动因子

| 事件类型 | 说明 | 利多触发词示例 | 利空触发词示例 |
|---------|------|--------------|--------------|
| 货币政策 | 央行利率/准备金/QE | 降息、鸽派、QE、宽松 | 加息、鹰派、缩表、紧缩 |
| 美元汇率 | 美元指数走势 | 美元下跌、美元走弱、美指回落 | 美元上涨、美元走强、美指拉升 |
| 通胀预期 | CPI/PCE等通胀数据 | 通胀上升、CPI超预期、通胀粘性 | 通胀回落、CPI不及预期、通胀降温 |
| 避险情绪 | 地缘/危机/恐慌 | 避险升温、地缘冲突、VIX飙升 | 避险消退、风险偏好上升、VIX回落 |
| 央行购金 | 各国央行黄金储备 | 央行购金、增持黄金、去美元化 | 央行售金、减持黄金、抛售储备 |
| ETF与需求 | 黄金/白银ETF持仓 | ETF增持、流入、买盘强劲 | ETF减持、流出、获利了结 |
| 白银供需 | 白银工业供需 | 白银短缺、光伏用银增加、去库 | 白银过剩、需求疲软、累库 |
| 经济衰退/复苏 | 经济增长预期 | 衰退、滞胀、收益率倒挂 | 复苏、经济增长、软着陆 |
| 债市收益率 | 美债/实际利率 | 收益率下降、实际利率走低 | 收益率上升、实际利率走高 |
| 技术面 | 技术分析信号 | 突破新高、金叉、多头排列 | 破位、死叉、空头排列 |

### 程度修饰词

| 程度 | 示例 |
|------|------|
| 强 | 大幅、超预期、暴、剧、断崖式、创纪录、历史性 |
| 中 | 小幅、温和、边际、略有、轻微、逐步 |
| 不确定 | 预期、可能、或、拟、传闻、市场预计 |

## 核心模块使用说明

### 1. 事件抽取器

```bash
cd extractor

# 单条快速测试
python event_extractor.py --text "美联储宣布加息25个基点，美元走强，金价承压下跌"

# 批量抽取 + 生成日度事件指数
python event_extractor.py --input ./news_data --output events.json --daily-index
```

输出结构化事件：
```json
{
  "commodities": ["gold"],
  "events": [
    {"event_type": "monetary_policy", "direction": "bearish", "degree": "moderate", "trigger_word": "加息"},
    {"event_type": "dollar_exchange", "direction": "bearish", "degree": "moderate", "trigger_word": "美元走强"}
  ],
  "summary": {
    "net_direction": "bearish",
    "dominant_types": ["monetary_policy", "dollar_exchange"]
  }
}
```

### 2. 人工抽检

```bash
# 生成50条随机抽检样本
python human_reviewer.py --input events.json --sample 50 --mode random

# 标注完成后，计算精确率/召回率/F1
python human_reviewer.py --input events.json --review reviewed.json --report
```

支持三种抽检模式：
- `random`: 完全随机抽样
- `by_type`: 按事件类型分层抽样
- `edge`: 边界case优先（多空交织、不确定程度）

### 3. 词典扩展管线

```bash
cd dictionary

# 第一步：Word2Vec 种子词扩展
python expand_dictionary.py --crawler-data ../corpus

# 第二步：BERT 语义校验
python bert_validator.py --input output/expanded_dict.xlsx

# 第三步：人工抽检（见 extractor/human_reviewer.py）
```

三级扩充机制：
1. **Word2Vec 扩展**：从种子词出发，用语料训练skip-gram模型，召回相似词
2. **BERT 校验**：用FinBERT对候选词做上下文语义校验，过滤极性错误
3. **人工抽检**：随机抽样人工复核，确保精确率达标后入库

## 为什么不用通用情感词典？

通用情感词典（HowNet、Loughran-McDonald等）在期货市场存在五大问题：

1. **领域术语覆盖差，极性容易整反**："去库""升水""抛储"等词通用词典没有或极性错
2. **只有整体正负，没有事件维度**：丢掉了供应/需求/政策等关键维度信息
3. **多空方向因角色而异**："库存累积"对空头是利好、对多头是利空，通用词典只打一个分
4. **宏观/跨品种传导处理不了**：美联储→黄金/有色/股指的传导路径完全不同
5. **否定/程度/短句噪声更明显**：期货快讯短、数字多、套路化，通用词典否定窗口不够

本项目的事件本体方案，正是针对这些问题设计的——**从"一维情绪打分"升级为"多维结构化事件抽取"**。

## 研究路线图

### Phase 1：数据基础设施 ✅
- [x] 5源7×24财经快讯采集
- [x] 两层去重（精确 + 近似）
- [x] OCR图文识别 + 翻译对齐

### Phase 2：事件本体与抽取 ✅
- [x] 10类事件本体定义（380+触发词）
- [x] 规则驱动事件抽取器
- [x] 程度/否定/品种识别
- [x] 人工抽检工具与评估流程

### Phase 3：词典自动化扩展
- [x] Word2Vec 种子词扩展脚本
- [x] FinBERT 语义校验模块
- [ ] 扩展后效果评估（P/R/F1）

### Phase 4：事件驱动因子研究
- [ ] 日度事件指数构建（按类型/方向/程度）
- [ ] 事件研究法（Event Study）：超额收益检验
- [ ] 事件类型因子正交化
- [ ] 跨品种传导与领先滞后关系

## 参考研究

- **Beyond Polarity: Multi-Dimensional LLM Sentiment Signals for WTI Crude Oil Futures** (arXiv 2603.11408) — 五维情绪信号（相关性/极性/强度/不确定性/前瞻性），超越单一极性的研究范式
- **大语言模型驱动的期货市场新闻多主题和多层次情感分析框架** (北师大学报 2025) — "整体-主题-方面"三层分析架构
- **事件研究法（Event Study）** — 金融学术经典方法，检验事件对价格的冲击效应
