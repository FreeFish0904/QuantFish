# DataGo 舆情数据使用指南

DataGo 数据是一组和投资者关注度、新闻情绪、股吧讨论有关的行为金融数据。它已经和其他 QuantFish 数据一样放进 `data_releases/learning`，可以通过 `DataBundle` 读取，也可以在 `generate_signals` 策略函数里使用。

这章重点回答三个问题：

- DataGo 里有哪些表？
- 在平台里应该写哪个数据集名字？
- 怎么把搜索、新闻、股吧舆情变成可以回测的 `score`？

> 小提醒：DataGo 表很大。写代码时一定要先用 `columns=[...]` 只读取需要的列，再用 `numeric_columns=[...]` 把要计算的字段转成数字。不要一上来整表 `print(df)`。

---

## 1. DataGo 在平台里的位置

DataGo 原始文件在学习数据集中保留原来的目录结构：

```text
data_releases/learning/
└── teacher/
    └── behavioral_finance/
        └── datago/
```

你平时不需要手动拼路径，直接用平台的数据接口即可：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")
```

`bundle.at("2022-06-30")` 的意思是：把数据视角绑定到 2022-06-30。之后用 `data.current(...)`、`data.history(...)`、`data.latest(...)`、`data.load(...)` 读取带日期的表时，平台会自动避免读到这个日期之后的数据。

> **市场范围过滤提示**
>
> DataGo 表本身没有 `markettype` 列，平台默认的市场过滤不会直接作用于它们。平台默认交易 `[1, 4, 16, 32, 64]` 对应的沪深主板、创业板、科创板和北交所 A 股，这个范围来自 `config/platform.yaml` 的 `execution.allowed_market_types`。
>
> 所以，当你先把 `stock.daily_returns` 作为股票池、再和 DataGo 表合并时，行情股票池已经按上述 A 股范围过滤。如果你希望用 DataGo 数据构造全市场信号，也建议从 `data.current("stock.daily_returns")` 的股票池出发，以保持和平台回测一致。

---

## 2. 五张 DataGo 表

下面是当前平台支持的 DataGo 表。你可以用长数据集 ID，也可以用括号里的短别名。初学时建议先用短别名。

| 短别名 | 主日期列 | 股票代码列 | 大概用途 |
|---|---|---|---|
| `上市公司网络搜索分析数据表` | `pub_date` | `stock_id` | 百度搜索关注度，例如某只股票当天被搜索得多不多。 |
| `新闻情感量化数据表` | `pub_date` | 无 | 每条报刊新闻自己的情绪分数、正负面句子数。 |
| `新闻相关上市公司表` | `pub_date` | `stkcd` | 报刊新闻提到了哪些上市公司，以及相关程度。 |
| `网络新闻相关上市公司表` | `pub_date` | `stkcd` | 网络新闻提到了哪些上市公司，以及相关程度。 |
| `股吧量化舆情表(交易时段分组)` | `Pub_Date` | `Stock_Id` | 股吧阅读、回复、发帖数量，以及情绪指标。 |

完整长名字如下：

```text
behavioral_finance.datago.上市公司网络搜索分析数据表_fullpacked_data.上市公司网络搜索分析数据表
behavioral_finance.datago.新闻情感量化数据表_fullpacked_data.新闻情感量化数据表
behavioral_finance.datago.新闻相关上市公司表_fullpacked_data.新闻相关上市公司表
behavioral_finance.datago.网络新闻相关上市公司表_fullpacked_data.网络新闻相关上市公司表
behavioral_finance.datago.股吧量化舆情表(交易时段分组)_fullpacked_data.股吧量化舆情表(交易时段分组)
```

如果你不确定某张表的日期列、代码列、字段说明，可以这样查：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
spec = bundle.describe("上市公司网络搜索分析数据表")

print("数据集 ID:", spec.dataset_id)
print("别名:", spec.aliases)
print("主日期列:", spec.primary_asof_column)
print("股票代码列:", spec.symbol_column)
print("字段说明:", spec.column_descriptions)
```

---

## 3. 读取方法怎么选

DataGo 和其他带日期的数据一样，可以用四种读取方法。

| 你想做什么 | 推荐方法 | 例子 |
|---|---|---|
| 只看绑定日期当天的数据 | `data.current(...)` | 今天百度搜索关注度最高的是哪些股票？ |
| 看过去一段时间的数据 | `data.history(..., lookback_days=N)` | 过去 7 天哪些股票被新闻频繁提到？ |
| 每只股票取截至今天最新记录 | `data.latest(..., by="股票代码列")` | 每只股票最近一次股吧情绪是多少？ |
| 明确指定开始和结束日期 | `data.load(..., start=..., end=...)` | 调试某个固定月份的舆情数据。 |

最常用的是 `current` 和 `history`。DataGo 新闻、搜索、股吧数据通常是日频或事件频数据，所以不要默认用 `latest` 解决所有问题。

---

## 4. 示例一：查看某天的搜索关注度

先从最简单的探索开始：读取一天的百度搜索指数。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

search = data.current(
    "上市公司网络搜索分析数据表",
    columns=["stock_id", "pub_date", "index_all", "index_pc", "index_mobile"],
    numeric_columns=["index_all", "index_pc", "index_mobile"],
)

print(search.head())
```

这段代码会读取 `pub_date == 2022-06-30` 的搜索数据。

常用列：

- `stock_id`：带交易所后缀的股票代码，例如 `000001.SZ`。
- `pub_date`：统计日期。
- `index_all`：全部设备搜索指数。
- `index_pc`：电脑端搜索指数。
- `index_mobile`：移动端搜索指数。

如果你只需要六位股票代码，可以这样处理：

```python
search["code"] = search["stock_id"].astype(str).str.slice(0, 6)
```

---

## 5. 示例二：用搜索关注度写一个策略

下面这个策略把“搜索关注度高”当成信号。它不是说这个想法一定赚钱，只是展示 DataGo 数据怎么变成 `score`。

```python
import pandas as pd


def generate_signals(data, date):
    search = data.current(
        "上市公司网络搜索分析数据表",
        columns=["stock_id", "index_all"],
        numeric_columns=["index_all"],
    )

    codes = search["stock_id"].astype(str).str.slice(0, 6)
    score = pd.Series(search["index_all"].values, index=codes)
    return score
```

平台会把 `score` 变成多空权重，然后继续完成回测。这里你只需要决定一件事：哪只股票分数更高。

如果你的想法是“关注度过高可能过热，未来反而回落”，也可以反过来：

```python
score = pd.Series(-search["index_all"].values, index=codes)
```

---

## 6. 示例三：用过去 7 天新闻提及次数做信号

`新闻相关上市公司表` 告诉你每条报刊新闻提到了哪些上市公司。我们可以统计过去 7 天每只股票被新闻提到的强度。

```python
import pandas as pd


def generate_signals(data, date):
    mentions = data.history(
        "新闻相关上市公司表",
        lookback_days=7,
        columns=["stkcd", "ment_times", "relev_score"],
        numeric_columns=["ment_times", "relev_score"],
    )

    weighted_mentions = mentions["ment_times"] * mentions["relev_score"]
    score = weighted_mentions.groupby(mentions["stkcd"].astype(str).str.zfill(6)).sum()
    return pd.Series(score.values, index=score.index)
```

这段代码的含义是：

- `ment_times`：新闻中提到这只股票的次数。
- `relev_score`：新闻和这只股票的相关程度。
- `ment_times * relev_score`：把“提到很多次”和“相关程度高”结合起来。

如果你想做反向信号，可以对 `score` 取负号。

---

## 7. 示例四：把新闻情绪和新闻关联表合并

`新闻情感量化数据表` 是新闻本身的情绪分数；`新闻相关上市公司表` 是新闻和股票的对应关系。两张表都带有 `news_id`，所以可以合并。

```python
import pandas as pd


def generate_signals(data, date):
    news = data.history(
        "新闻情感量化数据表",
        lookback_days=3,
        columns=["news_id", "overall_senti_score"],
        numeric_columns=["overall_senti_score"],
    )

    links = data.history(
        "新闻相关上市公司表",
        lookback_days=3,
        columns=["news_id", "stkcd", "relev_score"],
        numeric_columns=["relev_score"],
    )

    joined = links.merge(news, on="news_id", how="inner")
    joined["weighted_sentiment"] = (
        joined["overall_senti_score"] * joined["relev_score"]
    )

    score = joined.groupby(joined["stkcd"].astype(str).str.zfill(6))[
        "weighted_sentiment"
    ].mean()
    return pd.Series(score.values, index=score.index)
```

这段代码做了三步：

1. 读取过去 3 天新闻的情绪分数。
2. 读取过去 3 天新闻和股票的对应关系。
3. 用 `news_id` 合并，再按股票求平均情绪。

这个例子适合用来理解“事件表 + 关联表”的组合方法。实际策略里可以继续加成交额、行业、市值等约束。

---

## 8. 示例五：用股吧情绪和热度做信号

`股吧量化舆情表(交易时段分组)` 里同时有热度和情绪。因为它按交易时段分组，同一只股票同一天可能有多行，所以通常先按股票聚合。

```python
import numpy as np
import pandas as pd


def generate_signals(data, date):
    guba = data.current(
        "股吧量化舆情表(交易时段分组)",
        columns=[
            "Stock_Id",
            "Reads_All_AllUser_Sum",
            "Posts_All_AllUser_Sum",
            "Senti_Score_Div",
        ],
        numeric_columns=[
            "Reads_All_AllUser_Sum",
            "Posts_All_AllUser_Sum",
            "Senti_Score_Div",
        ],
    )

    grouped = guba.groupby(guba["Stock_Id"].astype(str).str.zfill(6)).agg(
        reads=("Reads_All_AllUser_Sum", "sum"),
        posts=("Posts_All_AllUser_Sum", "sum"),
        sentiment=("Senti_Score_Div", "mean"),
    )

    score = grouped["sentiment"] * np.log1p(grouped["reads"] + grouped["posts"])
    return pd.Series(score.values, index=score.index)
```

这里的想法是：

- 情绪越正面，分数越高；
- 讨论热度越高，信号权重越大；
- 用 `np.log1p(...)` 是为了避免超大阅读量直接压倒其他信息。

如果你想做“热度过高反向”的策略，也可以改成：

```python
score = -grouped["sentiment"] * np.log1p(grouped["reads"] + grouped["posts"])
```

---

## 9. 示例六：用 `valid_date` 做更保守的新闻过滤

部分新闻表里还有 `valid_date`。平台的主日期边界使用 `pub_date`，也就是新闻发布日或统计日。如果你想更保守，要求“这条数据进入 DataGo 表的日期也不能晚于当前回测日”，可以自己再过滤一次 `valid_date`。

```python
import pandas as pd


def generate_signals(data, date):
    mentions = data.history(
        "新闻相关上市公司表",
        lookback_days=7,
        columns=["stkcd", "pub_date", "valid_date", "ment_times", "relev_score"],
        numeric_columns=["ment_times", "relev_score"],
    )

    asof = pd.Timestamp(date).normalize()
    valid_dates = pd.to_datetime(mentions["valid_date"], errors="coerce").dt.normalize()
    mentions = mentions[valid_dates <= asof]

    score_values = mentions["ment_times"] * mentions["relev_score"]
    score = score_values.groupby(mentions["stkcd"].astype(str).str.zfill(6)).sum()
    return pd.Series(score.values, index=score.index)
```

什么时候需要这样做？

- 如果你担心新闻虽然 `pub_date` 很早，但供应商后续才补进数据库；
- 如果你想把策略假设写得更保守；
- 如果你在做严谨研究，而不是课堂里的第一版策略。

什么时候可以先不管？

- 你只是学习 DataGo 表怎么用；
- 你只是想快速测试一个想法；
- 你已经明确接受平台默认的 `pub_date` 时间边界。

---

## 10. 常见坑

### 10.1 股票代码格式不一样

不同 DataGo 表的股票代码格式不完全一样：

- 搜索表：`stock_id`，形如 `000001.SZ`。
- 新闻关联表：`stkcd`，通常是六位代码。
- 股吧表：`Stock_Id`，通常是六位代码。

建议统一成六位字符串：

```python
codes = raw_codes.astype(str).str.slice(0, 6).str.zfill(6)
```

### 10.2 字段名大小写要照抄

`pub_date` 和 `Pub_Date` 是两个不同列名；`stock_id` 和 `Stock_Id` 也不同。写代码时请照着 `bundle.describe(...)` 或本章表格复制。

### 10.3 DataGo 很大，读取要克制

下面这种写法不推荐：

```python
all_news = data.load("网络新闻相关上市公司表")
print(all_news)
```

更推荐：

```python
recent_news = data.history(
    "网络新闻相关上市公司表",
    lookback_days=3,
    columns=["news_id", "stkcd", "relev_score"],
    numeric_columns=["relev_score"],
)
```

### 10.4 不要把新闻本身当成股票代码表

`新闻情感量化数据表` 没有股票代码列，它只是“新闻自己的情绪”。如果你想把情绪分配到股票上，需要和 `新闻相关上市公司表` 或 `网络新闻相关上市公司表` 用 `news_id` 合并。

---

## 11. 建议练习顺序

如果你第一次用 DataGo，建议按这个顺序来：

1. 先跑示例一，确认自己能读取搜索关注度。
2. 把示例二复制到 `strategy.py`，跑一次本地学习数据回测。
3. 再试示例三，用过去 7 天新闻提及次数做信号。
4. 最后再尝试示例四或示例五，把多张表组合起来。

每次只改一个想法。比如先只改“看 3 天还是看 7 天”，不要同时改字段、公式、方向和过滤条件。这样你才知道回测结果到底是谁造成的。

---

## 12. 完整示例策略文件

如果你想直接看可以上传的完整 `.py` 文件，完整仓库的项目根目录下还有这些 DataGo 示例策略：

```text
examples/strategies/datago_search_attention.py
examples/strategies/datago_news_mention_momentum.py
examples/strategies/datago_news_sentiment.py
examples/strategies/datago_guba_sentiment_heat.py
```

它们和本章示例一一对应，但写成了完整策略文件。每个文件都定义了 `generate_signals(data, date)`，可以直接复制、改名、上传，也可以作为你自己的 `strategy.py` 起点。

---

上一步：[原始数据因子排序实验](./12-raw-factor-ranking-lab.md) | 返回：[学生文档首页](./README.md)
