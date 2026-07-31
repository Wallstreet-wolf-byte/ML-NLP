# 股吧与东方财富投资者情绪扩展方案

## 背景

当前项目已经具备 7x24 财经资讯爬取能力，主要覆盖：

- 汇通财经
- 金十数据
- 华尔街见闻

这类数据更偏向“新闻供给侧”，适合识别宏观事件、行业事件、政策信息和市场快讯。但如果要做中低频量化因子研究，仅依赖新闻源还不够，需要进一步补充“投资者情绪侧”数据。

东方财富股吧、个股讨论区等数据可以用于观察：

- 投资者如何反应
- 讨论热度是否异常
- 看多/看空是否极端
- 市场分歧是否扩大
- 新闻是否已经被情绪充分 price in

因此，后续可以把项目从“财经新闻爬虫”扩展为：

```text
新闻事件流 + 投资者情绪流 + 因子生成器
```

## 新闻情绪与股吧情绪的区别

新闻情绪关注：

```text
发生了什么事件
事件偏利多还是利空
影响哪些行业、市场或资产
```

股吧情绪关注：

```text
投资者怎么反应
讨论热度是否异常
看多看空是否极端
分歧是否扩大
情绪是否过热
```

例如一条新闻可能是：

```text
某公司业绩增长
```

新闻侧可能判断为偏利多，但股吧里可能出现：

```text
利好兑现
明天高开低走
主力出货
不及预期
```

这说明投资者情绪可能并不完全跟新闻方向一致。这种分歧本身就可能成为量化研究信号。

## 建议新增模块

不要把股吧逻辑直接塞进现有 `finance_news_crawler`，建议单独新增模块：

```text
ML-NLP/
  finance_news_crawler/          # 7x24 财经新闻资讯
  investor_sentiment_crawler/    # 股吧、论坛、投资者讨论
  nlp_analysis/                  # 分词、词典、TF-IDF、情绪评分
  factor_builder/                # 日频/周频因子生成
  data/
    raw/
    processed/
    factors/
```

其中，`finance_news_crawler` 继续负责新闻事件流，`investor_sentiment_crawler` 负责投资者讨论数据。

## 股吧数据字段设计

股吧数据不应该和新闻完全混在一起，建议单独设计数据结构：

```json
{
  "post_id": "",
  "stock_code": "",
  "stock_name": "",
  "title": "",
  "content": "",
  "publish_time": "",
  "crawl_time": "",
  "author": "",
  "read_count": 0,
  "comment_count": 0,
  "like_count": 0,
  "source": "东方财富股吧",
  "data_type": "investor_discussion"
}
```

核心字段包括：

- `stock_code`：股票代码
- `publish_time`：帖子发布时间
- `crawl_time`：实际抓取时间
- `read_count`、`comment_count`、`like_count`：热度指标
- `title`、`content`：文本内容

其中 `publish_time` 和 `crawl_time` 都要保留，便于后续避免回测中的未来函数问题。

## 股吧情绪因子方向

东方财富股吧适合构造个股维度的中低频情绪因子，例如：

```text
daily_post_count
daily_comment_count
daily_bullish_score
daily_bearish_score
daily_sentiment_mean
daily_sentiment_std
daily_disagreement_score
daily_attention_score
daily_emotion_extreme_score
```

含义：

- `daily_post_count`：当日发帖数量
- `daily_comment_count`：当日评论数量
- `daily_bullish_score`：看多情绪强度
- `daily_bearish_score`：看空情绪强度
- `daily_sentiment_mean`：平均情绪
- `daily_sentiment_std`：情绪分歧
- `daily_disagreement_score`：多空分歧程度
- `daily_attention_score`：关注度
- `daily_emotion_extreme_score`：情绪极端程度

示例输出：

```csv
date,stock_code,post_count,sentiment_mean,bullish_ratio,bearish_ratio,disagreement_score
2026-07-27,300750,328,0.42,0.61,0.18,0.37
2026-07-27,002594,215,-0.12,0.31,0.45,0.52
```

## 股吧专用情绪词典

股吧语言和新闻语言差异很大，不能直接复用新闻情绪词典。

新闻常见词：

```text
增长
亏损
获批
处罚
回购
减持
```

股吧常见词：

```text
起飞
冲鸭
满仓
割肉
砸盘
出货
洗盘
套牢
跌停
涨停
垃圾股
妖股
主力
庄家
韭菜
```

建议将股吧情绪词典分成：

- 看多词
- 看空词
- 恐慌词
- 狂热词
- 怀疑词
- 交易行为词

示例：

```text
看多：起飞、涨停、满仓、突破、主升浪、反包
看空：割肉、砸盘、出货、跌停、套牢、凉了
恐慌：崩了、血亏、踩雷、跑路、爆雷
狂热：无脑买、梭哈、十倍、妖王、躺赢
怀疑：诱多、骗炮、假突破、利好出尽
```

第一版可以先使用人工词典法，后续再用 Word2Vec 扩展相似词，用 BERT 做更精细的文本分类。

## 热度异常检测

股吧数据中，最重要的不一定是情绪正负，而是讨论热度是否异常。

例如：

```text
今日发帖数 / 过去20日平均发帖数
```

可以构造：

```text
attention_zscore = (今日发帖数 - 过去20日均值) / 过去20日标准差
```

进一步可以结合情绪：

```text
高热度 + 高乐观 = 情绪拥挤
高热度 + 高悲观 = 恐慌释放
高热度 + 高分歧 = 重大事件争议
```

这些指标适合做中低频个股因子，也适合观察主题炒作和情绪反转。

## 新闻与股吧联动研究

后续可以将新闻事件流和股吧情绪流结合，研究：

```text
新闻先出现 -> 股吧讨论升温 -> 股价反应
股吧先异常升温 -> 新闻后出现
新闻和股吧是否共振
新闻和股吧是否背离
```

可以设计因子：

```text
news_sentiment_score
guba_sentiment_score
news_attention_score
guba_attention_score
news_guba_consensus_score
news_guba_divergence_score
```

解释：

- `news_guba_consensus_score`：新闻情绪和投资者情绪同向程度
- `news_guba_divergence_score`：新闻情绪和投资者情绪背离程度

例如：

```text
新闻偏利多，股吧也极度乐观
```

可能说明市场形成共识。

```text
新闻偏利多，但股吧大量质疑
```

可能说明市场不买账，或者存在预期差。

## 建议开发路线

第一阶段：指定股票股吧爬虫

```text
支持指定 stock_code
支持指定 start_date / end_date
抓取帖子标题、正文、时间、作者、阅读数、评论数
```

示例命令：

```powershell
python investor_sentiment_crawler/main.py --stock-code 300750 --start-date 2026-07-01 --end-date 2026-07-31
```

第二阶段：文本清洗

清洗内容包括：

```text
表情
链接
广告
无意义短帖
重复灌水
纯数字
异常符号
```

第三阶段：情绪词典打分

构建：

```text
看多词典
看空词典
恐慌词典
狂热词典
怀疑词典
交易行为词典
```

第四阶段：日频个股情绪因子

按 `stock_code + date` 聚合：

```text
发帖数
评论数
平均情绪
看多比例
看空比例
分歧程度
热度异常
极端情绪
```

第五阶段：回测验证

将股吧因子与行情数据对齐，研究：

```text
今日股吧情绪 -> 未来1日收益
今日股吧情绪 -> 未来3日收益
今日股吧情绪 -> 未来5日收益
热度异常 -> 成交量变化
情绪极端 -> 反转效应
```

第六阶段：模型增强

在人工词典和基础因子跑通后，再考虑：

```text
Word2Vec：扩展股吧词典、发现相似表达
BERT：做看多/看空/中性分类
聚类模型：识别集中讨论主题
```

## 与现有 7x24 新闻爬虫的关系

现有新闻爬虫解决：

```text
事件信息流
```

股吧扩展解决：

```text
投资者情绪流
```

两者结合后，可以研究：

```text
事件发生了什么
投资者如何反应
市场是否已经 price in
是否存在预期差
是否存在情绪拥挤
是否存在反转机会
```

这比单独做新闻情绪或单独做股吧情绪更有研究价值。

## 总结

后续项目可以从单一新闻爬虫升级为：

```text
财经事件数据库 + 投资者情绪数据库 + 中低频因子生成器
```

优先顺序建议：

```text
1. 保持 7x24 新闻爬虫稳定
2. 新增指定股票的东方财富股吧爬虫
3. 建立股吧专用文本清洗和情绪词典
4. 输出 stock_code + date 维度的日频情绪因子
5. 与行情数据对齐，做 1日/3日/5日收益回测
6. 再引入 Word2Vec 和 BERT 做模型增强
```
