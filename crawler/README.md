# crawler

独立财经新闻爬虫项目，当前主流程抓取 5 个财经新闻来源：汇通财经、金十数据、华尔街见闻、财联社、证券时报-人民财讯。项目会按时间区间采集多个 7x24 财经资讯源，并统一输出为结构化 JSON。

当前主线支持 5 个来源：

| source 参数 | 新闻来源 | 采集方式 | 主要内容 |
|---|---|---|---|
| `fx678` | 汇通财经 | 列表页 + 详情页 HTML 解析 | 外汇、商品、宏观、市场快讯 |
| `jin10` | 金十数据 | 网页快讯 API，失败时回退 HTML 解析 | 7x24 市场快讯、宏观数据、政策消息 |
| `wallstreetcn` | 华尔街见闻 | live JSON API + cursor 翻页 | 全球市场、宏观、盘中快讯 |
| `cls` | 财联社 | telegraph JSON API + 时间翻页 + sign 参数 | A 股、政策、产业和盘中快讯 |
| `stcn` | 证券时报-人民财讯 | 快讯 JSON API + 时间游标翻页 | 官方财经新闻、市场快讯 |

本项目不依赖原来的 `巨灾信息爬虫` 项目，不使用 MCP Token，也不使用 Selenium。它的定位是轻量、可复现、便于后续接入 NLP / 舆情分析 / 量化因子研究的数据采集层。

## 1. 环境准备

建议使用 Python 3.9+。

在 `ML-NLP` 目录下安装依赖：

```powershell
cd D:\爬虫预警程序\ML-NLP
python -m pip install -r crawler\requirements.txt
```

如果你已经进入 `crawler` 目录，也可以运行：

```powershell
python -m pip install -r requirements.txt
```

## 2. 快速运行

在 `ML-NLP` 目录下运行全部来源：

```powershell
python crawler\main.py --source all
```

只抓单个来源：

```powershell
python crawler\main.py --source fx678
python crawler\main.py --source jin10
python crawler\main.py --source wallstreetcn
python crawler\main.py --source cls
python crawler\main.py --source stcn
```

如果当前终端已经在 `crawler` 目录下，则命令写成：

```powershell
python main.py --source all
```

## 3. 指定日期区间

默认日期区间在 `config.py` 中维护：

```python
START_DATE = "2026-08-04 00:00:00"
END_DATE = "2026-08-04 09:59:59"
```

也可以在运行时指定：

```powershell
python crawler\main.py --source all --start-date "2026-08-04 00:00:00" --end-date "2026-08-04 09:59:59"
```

支持的日期格式包括：

```text
2026-08-04
2026-08-04 09:30
2026-08-04 09:30:00
20260804 09:30:00
```

如果只传入日期，例如 `2026-08-04`，开始日期会被解释为当天 `00:00:00`，结束日期会被解释为当天 `23:59:59`。

## 4. 常用参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--source` | `all` | 选择来源：`all`、`fx678`、`jin10`、`wallstreetcn`、`cls`、`stcn` |
| `--start-date` | `config.py` 中的 `START_DATE` | 开始时间 |
| `--end-date` | `config.py` 中的 `END_DATE` | 结束时间 |
| `--fx678-page-limit` | `40` | 汇通财经列表页最大翻页数 |
| `--jin10-limit` | `1000` | 金十最多保留记录数 |
| `--jin10-page-limit` | `80` | 金十最大翻页数 |
| `--wallstreetcn-page-limit` | `40` | 华尔街见闻最大翻页数 |
| `--cls-page-limit` | `40` | 财联社最大翻页数 |
| `--stcn-page-limit` | `40` | 证券时报-人民财讯最大翻页数 |
| `--concurrent-workers` | `6` | 汇通财经详情页并发抓取线程数 |
| `--parallel-sources` | 关闭 | 抓全部来源时是否并行抓取不同网站 |
| `--source-workers` | `5` | 来源级并发线程数，仅在 `--parallel-sources` 开启时生效 |
| `--output-prefix` | `finance_news` | 输出 JSON 文件名前缀 |

示例：

```powershell
python crawler\main.py --source fx678 --fx678-page-limit 3
python crawler\main.py --source jin10 --jin10-limit 100 --jin10-page-limit 10
python crawler\main.py --source all --parallel-sources --source-workers 5
python crawler\main.py --source all --output-prefix morning_news
```

## 5. 输出格式

所有来源最终会被统一成同一套字段：

```json
{
  "id": "",
  "title": "",
  "content": "",
  "publish_time": "",
  "source": "",
  "data_source": "",
  "data_frequency": "7x24实时"
}
```

字段含义：

| 字段 | 含义 |
|---|---|
| `id` | 新闻唯一编号，优先使用网站原始 ID；没有原始 ID 时会根据时间生成 |
| `title` | 新闻标题 |
| `content` | 新闻正文或快讯正文 |
| `publish_time` | 新闻发布时间，格式通常为 `YYYY-MM-DD HH:MM:SS` |
| `source` | 人类可读的新闻来源名称 |
| `data_source` | 具体采集渠道或接口说明 |
| `data_frequency` | 数据频率，目前统一为 `7x24实时` |

输出文件位于：

```text
crawler\crawler_data\
```

文件名示例：

```text
finance_news_20260804_090228.json
morning_news_20260804_090228.json
```

写入 JSON 前，程序会按 `publish_time` 从新到旧排序。无法解析发布时间的记录会排在最后。

## 6. 去重逻辑

多来源采集时，同一条新闻可能被多个网站同步发布，因此保存前会做去重。

当前去重分为两层：

1. 精确去重  
   对标题和正文做清洗、去空白、去常见来源前缀，再生成哈希 key。key 完全相同的记录只保留一条。

2. 近似去重  
   在设定时间窗口内比较文本相似度。默认配置为：

```python
DEDUP_SIMILARITY_THRESHOLD = 0.9
DEDUP_TIME_WINDOW_MINUTES = 120
```

也就是说，如果两条新闻发布时间相近，并且标题 / 正文高度相似，就会被视为同一事件的重复报道。

## 7. 推荐使用流程

初次排查或开发时，建议先抓单个来源：

```powershell
python crawler\main.py --source jin10 --start-date "2026-08-04 09:00:00" --end-date "2026-08-04 10:00:00"
```

确认输出正常后，再抓全部来源：

```powershell
python crawler\main.py --source all --start-date "2026-08-04 00:00:00" --end-date "2026-08-04 09:59:59"
```

如果需要更快，可以开启来源并行：

```powershell
python crawler\main.py --source all --parallel-sources --source-workers 5
```

## 8. 常见问题

### 8.1 抓不到数据

优先检查：

- 日期区间是否过窄或过旧。
- 对应来源是否在该时间段内有新闻。
- `page_limit` 是否太小，导致还没翻到目标时间就停止。
- 网络请求是否失败，终端里通常会打印错误信息。

### 8.2 只有某一个来源失败

不同网站的接口和页面结构不同，单个来源失败不一定代表整个项目坏了。可以先单独运行该来源，缩小问题范围：

```powershell
python crawler\main.py --source cls
```

### 8.3 输出里有重复新闻

去重规则是“保守删除”，不是“只要像就删”。如果两条新闻相似但不是同一事件，程序会尽量保留，避免误删研究样本。

如需更激进地去重，可以在 `config.py` 中调整：

```python
DEDUP_SIMILARITY_THRESHOLD = 0.9
DEDUP_TIME_WINDOW_MINUTES = 120
```

### 8.4 JSON 打开后中文显示异常

输出文件使用 UTF-8 编码保存。建议用 VS Code、Python 或支持 UTF-8 的编辑器打开。

## 9. 项目定位

`crawler` 只负责新闻采集和基础整理，不负责情绪打分、行业分类、因子构造或回测。

推荐的数据流是：

```text
财经网站 -> crawler -> 统一 JSON -> NLP 分析 -> 因子构造 / 事件研究 / 可视化
```

这样可以把采集层和研究层解耦：爬虫只管稳定拿数据，后续分析模块只管读标准化后的新闻数据。
