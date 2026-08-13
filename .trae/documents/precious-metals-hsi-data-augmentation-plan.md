# 财经数据采集平台多维升级计划

> 目标：将项目从「纯快讯爬虫」升级为「多维度财经即时数据采集平台」，覆盖行情、资金、宏观、技术等多个数据维度，内置分类筛选体系，用户可按市场/品种/板块快速选取所需数据。金银及恒指期货为典型使用场景之一。

---

## 1. 现状总览

| 维度 | 状态 | 覆盖范围 |
|------|------|---------|
| 7x24 文本快讯 | ✅ 已完善 | 5 源（财联社/金十/华尔街见闻/汇通财经/证券时报） |
| 公告数据 | ⚠️ 框架已就绪 | 巨潮资讯（token 未配） |
| 大盘指数 | ⚠️ 仅 A 股+美股+韩股 | 缺恒指、期货、贵金属、外汇、债市 |
| 行情数据 | ❌ 缺失 | 无任何品种的实时/历史行情 |
| 资金流向 | ❌ 缺失 | 无 ETF 持仓/北向南向/期货持仓 |
| 宏观数据 | ❌ 缺失 | 无经济日历/利率/汇率/VIX |
| 技术指标 | ❌ 缺失 | 无 K 线/均线/波动率/比值 |
| 投资者情绪 | ❌ 缺失 | 无股吧/雪球/论坛 |
| 香港市场 | ❌ 几乎空白 | 仅有恒生/恒指关键词分类 |
| 统一 YAML 配置 | ⚠️ 仅 crawler | analysis 子项目使用独立 Python 硬编码配置 |

**核心问题**：项目目前只有一层数据——文本快讯。真正的投资决策需要多层数据的交叉验证。

---

## 2. 平台升级总体架构

### 2.1 数据维度分层

```
┌─────────────────────────────────────────────────────────┐
│                    财经数据采集平台                        │
├─────────────┬─────────────┬─────────────┬───────────────┤
│  文本层      │  行情层      │  资金层      │  宏观层        │
│  (快讯+公告) │  (实时/历史)  │  (流向/持仓) │  (事件/指标)   │
├─────────────┼─────────────┼─────────────┼───────────────┤
│ 5 快讯源     │ 股票/指数    │ 北向/南向    │ 经济数据日历   │
│ 巨潮公告     │ 期货/贵金属  │ ETF 持仓     │ 央行利率决议   │
│ 股吧/雪球    │ 外汇/债市    │ 期货持仓(COT)│ 地缘事件       │
│             │ 加密货币     │ 大股东增减持  │ 政策新闻       │
├─────────────┴─────────────┴─────────────┴───────────────┤
│                    技术指标层（本地计算）                    │
│  K线 · 均线 · 布林带 · RSI · MACD · ATR · 比值（金银比等）  │
├─────────────────────────────────────────────────────────┤
│                    分类筛选层                              │
│  按市场 · 按品种 · 按板块 · 按重要度 · 按时间               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
多源采集 → 统一标准化 → 分类打标 → 去重存储 → 按需筛选 → 分析/导出
   │            │           │
   ▼            ▼           ▼
config.yaml  models.py  classifier.py (扩展)
(统一配置)   (多类型模型) (多维分类)
```

---

## 3. 行情层：补齐所有核心品种实时行情

### 3.1 待新增的指数/品种配置

基于现有 `market_index.py` 的东方财富 push2 API 模式扩展，覆盖五大类：

| 大类 | 品种 | 优先级 |
|------|------|--------|
| **A 股指数** | 上证50、沪深300、中证500、中证1000（已有） | - |
| **港股市场** | 恒生指数、恒生科技、恒指期货、国企指数 | P0 |
| **美股指数** | 道琼斯、纳斯达克、标普500（已有） | - |
| **商品期货** | COMEX 黄金、COMEX 白银、美原油、伦铜、伦铝、CBOT 大豆 | P0 |
| **外汇 & 债市** | 美元指数、离岸人民币、欧元/美元；美国 10Y/2Y 国债收益率 | P0 |
| **贵金属现货** | 伦敦金、伦敦银 | P1 |
| **加密货币** | BTC/USD、ETH/USD | P2 |
| **恐慌指数** | VIX、VHSI（恒指波幅） | P1 |
| **亚太其他** | 日经225、KOSPI（已有）、台湾加权 | P2 |

### 3.2 数据采集方式

| 方案 | 适用 | 说明 |
|------|------|------|
| 东方财富 push2 | 主力 | 免费、多品种、已有代码先例。新增 secid 映射即可扩展 |
| 新浪财经 API | 备用 | 东方财富不可用时回退 |
| 通达信 MCP | 增强 | 港股/期货品种覆盖更全，需 API Key |
| TuShare MCP | 历史 | 补历史日线，需 Token |

### 3.3 统一配置段 `config.yaml`

```yaml
# --- API Keys 统一管理（新增） ---
api_keys:
  tushare_token: ""          # TuShare Pro Token
  tdx_api_key: ""            # 通达信 API Key
  ifind_api_key: ""          # 同花顺 iFinD API Key
  finnhub_api_key: ""        # Finnhub API Key
  alphavantage_api_key: ""   # Alpha Vantage API Key
  llm_api_key: ""            # DeepSeek/OpenAI LLM API Key

# --- 行情采集配置（新增） ---
market_data:
  enabled: true
  sources: ["eastmoney", "sina", "tdx"]  # 优先级递减
  fetch_interval_seconds: 60

  # 品种分类配置（用于筛选）
  categories:
    a_share:
      label: "A股指数"
      enabled: true
    hk_market:
      label: "港股市场"
      enabled: true
      items:
        - symbol: "HSI"        # 恒生指数
          secid_eastmoney: "100.HSI"
          secid_sina: "hHSI"
        - symbol: "HSTECH"     # 恒生科技
          secid_eastmoney: "100.HSTECH"
        - symbol: "HSCEI"      # 国企指数
          secid_eastmoney: "100.HSCEI"
        - symbol: "HSIF1"      # 恒指期货
          market: "futures"
    us_market:
      label: "美股指数"
      enabled: true
    precious_metals:
      label: "贵金属"
      enabled: true
      items:
        - symbol: "GC"         # COMEX 黄金期货
          secid_eastmoney: "112.GC00Y"
          name: "COMEX黄金"
        - symbol: "SI"         # COMEX 白银期货
          secid_eastmoney: "112.SI00Y"
          name: "COMEX白银"
        - symbol: "XAUUSD"     # 伦敦金现货
          name: "伦敦金"
        - symbol: "XAGUSD"     # 伦敦银现货
          name: "伦敦银"
    commodities:
      label: "大宗商品"
      enabled: true
    fx_bond:
      label: "外汇债市"
      enabled: true
      items:
        - symbol: "DXY"        # 美元指数
          secid_eastmoney: "100.DINIW"
        - symbol: "USDCNH"     # 离岸人民币
        - symbol: "US10Y"      # 美10年国债收益率
          secid_eastmoney: "100.US10YR"
        - symbol: "US2Y"       # 美2年国债收益率
    crypto:
      label: "加密货币"
      enabled: false
    volatility:
      label: "波动率"
      enabled: true
      items:
        - symbol: "VIX"
          secid_eastmoney: "100.VIX"
        - symbol: "VHSI"       # 恒指波幅指数
```

---

## 4. 资金层：补齐持仓与流向数据

### 4.1 数据维度

| 数据类型 | 粒度 | 来源 | 用途 |
|---------|------|------|------|
| 北向资金（沪/深股通） | 每日/盘中 | 东方财富 push2 | A 股外资态度 |
| 南向资金（港股通） | 每日/盘中 | 东方财富 / iFinD | 港股资金驱动 |
| SPDR 黄金 ETF (GLD) 持仓 | 每日 | 东方财富 / Web | 黄金资金面 |
| iShares 白银 ETF (SLV) 持仓 | 每日 | 东方财富 / Web | 白银资金面 |
| CFTC COT 持仓报告 | 每周 | 东方财富 / TuShare | 期货持仓情绪 |
| 大股东增减持 | 事件驱动 | 巨潮公告 / TuShare | 个股信号 |
| 融资融券余额 | 每日 | 东方财富 / TuShare | 杠杆情绪 |

采集方式统一走东方财富 push2 / 东方财富数据中心页面 + TuShare MCP 补历史。

---

## 5. 宏观层：补齐经济事件与指标

### 5.1 数据维度

| 数据类型 | 来源 | 关键字段 |
|---------|------|---------|
| 经济数据日历 | 东方财富财经日历 / 金十 | 事件名、国家/地区、重要性、预期值、前值、发布时间 |
| 央行利率决议 | 金十快讯（已有） | 决议结果、声明文本 |
| 地缘事件追踪 | 快讯源（已有） | 事件类型、影响分析 |

采集后自动计算：
- 实际值 vs 预期值偏离度
- 偏离度 × 重要性 → 冲击评分

---

## 6. 技术指标层：本地计算

从行情层获取原始价格数据后，本地计算（numpy/pandas），不依赖外部 API：

| 指标类别 | 具体指标 | 参数 |
|---------|---------|------|
| 趋势 | MA（简单移动平均） | 5/10/20/60/120 日 |
| 通道 | 布林带（Bollinger Bands） | 20,2 |
| 动量 | RSI（相对强弱） | 14 |
| 动量 | MACD | 12/26/9 |
| 波动 | ATR（真实波幅） | 14 |
| 比值 | 金银比 (GC/SI) | 实时 |
| 比值 | 金油比 (GC/CL) | 实时 |
| 比值 | 铜金比 (HG/GC) | 实时 |
| 价差 | 期现价差（期货-现货） | 实时 |

---

## 7. 香港市场专属扩展

香港市场是用户重点关注区域，需要额外补齐：

### 7.1 恒生系列指数行情

| 指数 | 说明 |
|------|------|
| 恒生指数 (HSI) | 大盘基准 |
| 恒生科技指数 (HSTECH) | 科技板块 |
| 恒生中国企业指数 (HSCEI) | H 股 |
| 恒指期货 (HSIF) | 日间 + 夜期 |
| 恒指波幅指数 (VHSI) | 恐慌指标 |

### 7.2 资金面

| 数据 | 说明 |
|------|------|
| 南向资金（港股通） | 沪港通 + 深港通每日净流向 |
| 北向资金 | A 股外资流向 |
| 港交所成交统计 | 市场总成交额、期货成交量 |

### 7.3 香港市场情绪数据（后续阶段）

| 来源 | 说明 |
|------|------|
| 雪球港股讨论 | 投资者情绪 |
| 香港经济日报 | 本地财经快讯（可选新增爬虫源） |
| AASTOCKS | 香港本地财经平台（可选新增） |

---

## 8. 分类筛选体系

### 8.1 多维标签

每条采集数据自动打上以下标签：

| 标签维度 | 示例值 |
|---------|--------|
| `data_type` | flash_news / market_quote / fund_flow / macro_event / technical_signal |
| `market` | A股 / 港股 / 美股 / 全球 |
| `asset_class` | 股票 / 期货 / 现货 / 外汇 / 债券 / 加密货币 / 指数 |
| `sector` | 半导体 / 新能源 / 贵金属 / 银行 / 地产 / 科技 ... |
| `symbol` | HSI / GC / SI / DXY / 000300 ... |
| `importance` | 高 / 中 / 低 |
| `sentiment` | 利多 / 利空 / 中性 |
| `region` | 中国 / 美国 / 欧洲 / 亚太 / 中东 |

### 8.2 CLI 筛选命令示例

```bash
# 金银用户：拉取贵金属相关全维度数据
python main.py --asset-class 贵金属 --data-type all

# 恒指用户：拉取港股全维度数据  
python main.py --market 港股 --data-type all

# 指定品种 + 指定维度
python main.py --symbol HSI,GC,SI --data-type market_quote,fund_flow

# 只看高影响事件
python main.py --importance 高
```

### 8.3 `common/models.py` 扩展

在现有 `make_news_record()` 基础上，新增通用数据工厂函数：

```python
# 通用行情快照模型
def make_quote_snapshot(
    symbol: str, name: str, market: str, asset_class: str,
    latest: float, change_pct: float, high: float, low: float,
    volume: float, timestamp: str, source: str, **extra
) -> dict: ...

# 通用资金流模型
def make_fund_flow_record(
    symbol: str, name: str, market: str, flow_type: str,
    net_amount: float, cumulative: float, timestamp: str, source: str
) -> dict: ...

# 通用宏观事件模型
def make_macro_event(
    event_name: str, country: str, importance: str,
    expected: float, actual: float, previous: float,
    release_time: str, source: str
) -> dict: ...
```

所有模型统一包含分类标签字段，便于筛选。

---

## 9. 平台入口重构

### 9.1 扩展 `main.py` CLI

```bash
# 现有命令保持不变
python main.py --source all --start-date ... --end-date ...

# 新增：按数据维度采集
python main.py --pipeline flash       # 只跑快讯（默认）
python main.py --pipeline market      # 只跑行情
python main.py --pipeline fundflow    # 只跑资金
python main.py --pipeline macro       # 只跑宏观
python main.py --pipeline technical   # 只跑技术指标
python main.py --pipeline all         # 全量采集

# 新增：按市场/品种筛选
python main.py --pipeline all --market 港股 --asset-class 贵金属
```

### 9.2 扩展 `config.yaml` 顶层结构

```yaml
# --- 顶层功能开关 ---
pipelines:
  flash_news: true       # 7x24 快讯
  cninfo: false          # 巨潮公告
  market_data: true      # 实时行情
  fund_flow: true        # 资金流向
  macro_calendar: true   # 宏观日历
  technical: true        # 技术指标

# --- 分类筛选默认值 ---
filter:
  default_market: all    # all / A股 / 港股 / 美股
  default_asset_class: all
  default_importance: all
```

---

## 10. 实施步骤

### 阶段一：基础设施（P0）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | 扩展 `config.yaml` | `config.yaml` | 新增 `api_keys`、`market_data`、`filter` 等配置段 |
| 2 | 扩展 `common/models.py` | `models.py` | 新增 `make_quote_snapshot`、`make_fund_flow_record`、`make_macro_event` |
| 3 | 扩展 `config.py` | `config.py` | 加载新配置段，支持环境变量覆盖 |
| 4 | 升级 `classifier.py` | `analyzer/classifier.py` | 新增 `asset_class`、`region` 等多维分类 |

### 阶段二：行情层（P0）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 5 | 重构 `market_index.py` | `analyzer/market_index.py` | 改为配置驱动，增收全品种 |
| 6 | 新建 `market_data_client.py` | `clients/market_data_client.py` | 行情独立采集模块 |

### 阶段三：资金 + 宏观 + 技术（P1）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 7 | 新建 `fund_flow_client.py` | `clients/fund_flow_client.py` | 资金流向/ETF 持仓/北向南向 |
| 8 | 新建 `macro_calendar_client.py` | `clients/macro_calendar_client.py` | 经济日历 + 冲击评分 |
| 9 | 新建 `technical_client.py` | `clients/technical_client.py` | K 线获取 + numpy 指标计算 |

### 阶段四：平台整合（P2）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 10 | 重构 `main.py` | `main.py` | 多 pipeline 编排 + 筛选参数 |
| 11 | 注册表扩展 | `clients/registry.py` | 类似 `flash_registry.py` 统一管理各 pipeline |

---

## 11. 金银/恒指用户典型使用流程

### 场景 A：做金银期货的用户

```bash
# 每日开盘前：拉取贵金属全维度数据
python main.py --pipeline all --asset-class 贵金属

# 输出包含：
# - GC/SI 实时行情 + 伦敦金/银现货
# - GLD/SLV ETF 持仓变化
# - DXY 美元指数 + 美债收益率
# - 金银比、技术指标（MA/RSI/MACD）
# - 关于黄金/白银的快讯聚合
# - 宏观经济日历（非农/CPI/FOMC 等黄金敏感事件）
```

### 场景 B：做恒指期货的用户

```bash
# 每日开盘前：拉取港股全维度数据
python main.py --pipeline all --market 港股

# 输出包含：
# - HSI/HSTECH/HSIF 实时行情
# - VHSI 恒指波幅指数
# - 南向资金流向
# - 离岸人民币汇率
# - 恒指相关快讯
# - 技术指标
```

---

## 12. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 行情主力 API | 东方财富 push2（免费） | 代码先例存在，无密钥依赖，覆盖广 |
| MCP 角色 | 辅助增强 + 历史回补 | 避免单点依赖，MCP 需 API Key 配好后启用 |
| 技术指标 | 本地计算（numpy） | 不依赖外部 API，可控性高 |
| 数据存储 | JSON 文件（不变） | 保持简单，后续可视需要引入 SQLite |
| 配置管理 | 统一 YAML | 所有 API Key 和开关归一到 `config.yaml` |
