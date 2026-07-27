# finance_news_crawler

独立财经新闻爬虫项目。当前主流程抓取三个财经新闻来源：

- 汇通财经网页新闻
- 金十数据网页端市场快讯
- 华尔街见闻要闻

不依赖原 `巨灾信息爬虫` 项目，不使用 MCP Token，也不使用 Selenium。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 日期区间

默认日期在 `config.py`：

```python
START_DATE = "2026-07-24 08:00:00"
END_DATE = "2026-07-24 09:59:59"
```

也可以运行时指定：

```powershell
python finance_news_crawler/main.py --start-date "2026-07-24 08:00:00" --end-date "2026-07-24 11:00:00"
```

## 运行

抓全部来源，顺序为汇通财经、金十数据、华尔街见闻：

```powershell
python finance_news_crawler/main.py --source all
```

只抓单个来源：

```powershell
python finance_news_crawler/main.py --source fx678
python finance_news_crawler/main.py --source jin10
python finance_news_crawler/main.py --source wallstreetcn
```

控制分页或读取数量：

```powershell
python finance_news_crawler/main.py --source fx678 --fx678-page-limit 3
python finance_news_crawler/main.py --source jin10 --jin10-limit 100
python finance_news_crawler/main.py --source wallstreetcn --wallstreetcn-page-limit 5
python finance_news_crawler/main.py --source all --concurrent-workers 6
```

所有来源统一输出：

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

写入 JSON 前会按 `publish_time` 从近到远排序。无法解析时间的记录会排在最后。

输出文件位于：

```text
finance_news_crawler/crawler_data/
```
