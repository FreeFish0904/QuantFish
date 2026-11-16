# 数据集目录

这一章是学习数据集的“菜单”。读完之后，你会知道：

- 想查某类数据时，应该写哪个数据集名字。
- 同一个表为什么可能有两个名字。
- 哪些表是带日期的、哪些表是静态的、主日期列和股票代码列分别叫什么。

> **数据集**（dataset）就是一张大表，里面存放着同一类信息，例如日行情、资产负债表、业绩预告等。QuantFish 把很多张这样的表打包在一起，组成了**学习数据集** `data_releases/learning`。

---

## 1. 数据集 ID 与别名

每一张表都有两个名字：

- **数据集 ID**：长名字，带有分类前缀，例如 `financial_supplement.forecast_vs_report.BF_FORECAST`。
- **别名**：短名字，例如 `BF_FORECAST`。

这两个名字指向**同一张表**，你在代码里写哪一个都可以。平台会自动把它们对应起来。

下面这段代码可以列出学习数据集里的所有表，并查看其中一张表的元信息：

```python
from quantfish.data import DataBundle

# 1. 打开学习数据集
bundle = DataBundle("data_releases/learning")

# 2. 列出所有数据集 ID
print(bundle.list_datasets())

# 3. 查看 BF_FORECAST 这张表的详细信息
spec = bundle.describe("BF_FORECAST")
print("数据集 ID:", spec.dataset_id)
print("别名:", spec.aliases)
print("主日期列:", spec.primary_asof_column)
print("股票代码列:", spec.symbol_column)
print("是否静态表:", spec.is_static)
```

**这行在做什么：**

- `DataBundle("data_releases/learning")` 创建一个**数据包对象**，它代表整个学习数据集目录。
- `bundle.list_datasets()` 返回所有表的长名字 ID。
- `bundle.describe("BF_FORECAST")` 用短名字也能查到同一张表的描述信息，返回的对象里包含主日期列、代码列、是否静态等元信息。

> **关于市场范围过滤的小提示**
>
> 平台默认使用 `markettype` 为 `[1, 4, 16, 32, 64]` 的 A 股，覆盖沪深主板、创业板、科创板和北交所。这个范围写在 `config/platform.yaml` 的 `execution.allowed_market_types` 里。因此，在 `generate_signals` 里读取的 `stock.daily_returns` 已经按这组市场过滤。
>
> 如果你在本地研究时想复现同样的市场范围，可以显式指定：
>
> ```python
> bundle = DataBundle("data_releases/learning", allowed_market_types=[1, 4, 16, 32, 64])
> ```
>
> 如果某张表没有 `markettype` 列，这个过滤不会生效，整张表照常读取。

知道表名之后，你就可以用上一章学过的 `data.current()` 读取某一天的行。例如：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")  # 绑定到 2022-06-30 这个交易日

# 读取 2022-06-30 当天的日行情
df = data.current(
    "stock.daily_returns",
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)
print(df.head())  # 只打印前 5 行
```

**这行在做什么：**

- `bundle.at("2022-06-30")` 拿到一个**日期绑定视图**，你只能看到这个交易日及之前的数据。
- `data.current("stock.daily_returns", columns=[...])` 从日行情表中读取 2022-06-30 当天的行，并且只返回你指定的列。
- `numeric_columns=["clsprc", "dretwd"]` 把收盘价和日收益率转成数字，异常文本或空值会变成 `NaN`。
- `df.head()` 把结果的前 5 行打印出来，方便快速查看。

---

## 2. 从问题到代码

这一章最重要的不是背表名，而是学会把一句普通问题翻译成代码。

你可以按这四步走：

1. 先说清楚你要查什么。
2. 找到对应的数据集名字。
3. 选择读取方法：`current`、`history`、`latest` 或 `load`。
4. 只读取需要的列，把要计算的列放进 `numeric_columns`。

### 2.1 第一步：先说清楚你要查什么

| 你心里的问题 | 常用数据集 | 常用读取方法 | 原因 |
|---|---|---|---|
| 今天哪些股票跌得多、成交额大、涨跌停了？ | `stock.daily_returns` | `data.current(...)` | 日行情每天都有，当前交易日一只股票通常一行。 |
| 最近 60 天哪只股票涨得多、波动大？ | `stock.daily_returns` | `data.history(..., lookback_days=60)` | 需要一段历史窗口，而不是只看当天。 |
| 每只股票截至今天最新的业绩预告是什么？ | `BF_FORECAST` | `data.latest(..., by="Stkcd")` | 业绩预告不是每天都有，通常要取“截至今天最新一条”。 |
| 每只股票最近一期估值指标是什么？ | `FI_T10` | `data.latest(..., by="Stkcd")` | 估值指标按报告期更新，通常也是取最新一条。 |
| 某个指数每天怎么涨跌？ | `market.index_daily` 或 `TRD_Index` | `data.current(...)` / `data.history(...)` | 指数行情是日频数据。 |
| 想知道一张表到底有哪些元信息？ | 任意数据集 | `bundle.describe(...)` | 查看正式 ID、别名、主日期列、股票代码列。 |

> **小提醒：** 不要想着“一次把所有数据集都用上”。一个好策略通常先从 1 张表开始，熟悉后再加第 2 张、第 3 张表。

### 2.2 第二步：选对读取方法

QuantFish 里最常用的是下面四个方法。

| 方法 | 读到什么 | 适合什么数据 |
|---|---|---|
| `data.current(dataset, ...)` | 绑定日期当天的行 | 日行情、指数日行情、市场日度指标。 |
| `data.history(dataset, lookback_days=N, ...)` | 从绑定日期往前 N 个自然日，到绑定日期为止 | 计算过去一段时间的均值、涨跌幅、波动率、成交额变化。 |
| `data.latest(dataset, by="股票代码列", ...)` | 每个分组截至绑定日期最新的一行 | 业绩预告、财报、股东持股、高管持股等不一定每天更新的数据。 |
| `data.load(dataset, start=..., end=..., ...)` | 指定时间区间内的所有行 | 研究或调试时需要明确开始、结束日期。 |

最容易混淆的是 `current` 和 `latest`：

- `current("BF_FORECAST")` 只会找**刚好在今天发布**的业绩预告。
- `latest("BF_FORECAST", by="Stkcd")` 会找**每只股票截至今天最新发布**的业绩预告。

所以，查“当天日行情”用 `current`；查“当前能知道的最新公告、财报、股东信息”通常用 `latest`。

### 2.3 第三步：只拿需要的列

读取数据时，建议永远先写 `columns=[...]`。这样代码更清楚，也更快。

```python
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "dretwd", "dnvaltrd"],
    numeric_columns=["dretwd", "dnvaltrd"],
)
```

这里有两个列表：

- `columns`：这次读取要返回哪些列。
- `numeric_columns`：哪些列接下来要参与加减乘除，需要转成数字。

通常可以这样判断：

| 列的用途 | 放在哪里 |
|---|---|
| 股票代码、日期、行业名称、公告类型 | 只放进 `columns` |
| 收益率、价格、成交额、市值、比例、利润增速 | 同时放进 `columns` 和 `numeric_columns` |

如果你要计算，就放进 `numeric_columns`。平台会把异常文本、空值、无法转换的内容变成 `NaN`，策略后面就不需要自己写一堆清洗代码。

### 2.4 第四步：在策略里返回 `score`

学生策略最终不是返回一张完整研究报告，而是返回每只股票的分数。最推荐的新手写法是：

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    score = -today["dretwd"]
    return pd.Series(score.values, index=today["stkcd"])
```

这段代码使用了 `stock.daily_returns`：

- `stkcd` 用来告诉平台“这是哪只股票”。
- `dretwd` 用来计算分数。
- `score = -today["dretwd"]` 表示短期反转：今天跌得越多，分数越高。

平台后面会负责把 `score` 变成仓位、执行交易、计算收益和指标。

---

## 3. 四种最常见用法

下面四种写法基本覆盖了入门阶段 80% 的数据使用场景。

### 3.1 用当天日行情写一个最小策略

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd"],
        numeric_columns=["dretwd", "dnvaltrd"],
    )

    # 例子：短期反转 + 成交额过滤思路。
    # 成交额太小的股票给 NaN，表示今天没有有效信号。
    score = -today["dretwd"]
    score = score.where(today["dnvaltrd"] > 10_000_000)

    return pd.Series(score.values, index=today["stkcd"])
```

这段代码适合学习：

- `stock.daily_returns` 怎么读；
- `numeric_columns` 怎么用；
- `NaN` 怎么表达“无信号”；
- 最终怎样返回 `pd.Series`。

### 3.2 用过去 60 天历史数据计算动量

```python
import pandas as pd


def generate_signals(data, date):
    history = data.history(
        "stock.daily_returns",
        lookback_days=60,
        columns=["stkcd", "trddt", "dretwd"],
        numeric_columns=["dretwd"],
    )

    # 对每只股票分别计算过去窗口内的平均日收益率。
    momentum = history.groupby("stkcd")["dretwd"].mean()

    # 平均收益率越高，score 越高。
    return pd.Series(momentum.values, index=momentum.index)
```

这段代码适合学习：

- `history` 会自动限制到当前日期及以前；
- `lookback_days=60` 是自然日，不是 60 个交易日；
- `groupby("stkcd")` 可以按股票分别做计算。

### 3.3 用最新业绩预告和日行情合并

很多基本面数据不是每天都有。如果你想把业绩预告变成策略分数，通常写法是：

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )

    latest_forecast = data.latest(
        "BF_FORECAST",
        by="Stkcd",
        columns=[
            "Stkcd",
            "RatNetProfPareComp_Hig",
            "RatNetProfPareComp_Low",
        ],
        numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
    )

    base = pd.DataFrame({
        "code": today["stkcd"].map(_code_for_merge),
        "market_score": -today["dretwd"],
    })

    forecast_score = (
        latest_forecast["RatNetProfPareComp_Hig"]
        + latest_forecast["RatNetProfPareComp_Low"]
    ) / 2.0
    forecast = pd.DataFrame({
        "code": latest_forecast["Stkcd"].map(_code_for_merge),
        "forecast_score": forecast_score,
    })

    merged = base.merge(forecast, on="code", how="left")
    merged["forecast_score"] = merged["forecast_score"].fillna(0.0)

    # 一个简单组合：市场反转分数 + 业绩预告分数。
    score = merged["market_score"].fillna(0.0) + merged["forecast_score"] / 100.0
    return pd.Series(score.values, index=merged["code"])


def _code_for_merge(value):
    """只在策略内部合并表格时使用：把 1、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]
```

这段代码适合学习：

- 为什么业绩预告要用 `latest`；
- 怎么用当天日行情确定股票池；
- 怎么把两张表按股票代码合并；
- 为什么做 `merge` 时要临时统一股票代码格式。

如果只是返回最终 `Series`，平台会自动整理股票代码；只有在策略内部自己 `merge` 两张表时，才需要像 `_code_for_merge` 这样先对齐代码格式。

### 3.4 本地探索时先查目录

写策略之前，你可以先在本地跑一小段探索代码，确认表名、日期列和代码列。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")

print(bundle.list_datasets())

spec = bundle.describe("BF_FORECAST")
print("正式 ID:", spec.dataset_id)
print("别名:", spec.aliases)
print("主日期列:", spec.primary_asof_column)
print("股票代码列:", spec.symbol_column)
print("是否静态表:", spec.is_static)
```

也可以直接看某张表在某一天返回什么：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

sample = data.current(
    "stock.daily_returns",
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)
print(sample.head())
```

这类探索代码适合放在临时练习文件里，不需要上传到网页端。上传策略时，核心仍然是 `generate_signals(data, date)`。

---

## 4. 数据表分组速览

下面的表格把学习数据集中的表按主题分成几组。每一行代表一张表，包含：

- **数据集 ID**（括号里是**别名**，短名字）。
- **主日期列 / 股票代码列 / 是否静态表**。
  - 主日期列：平台判断“这一行属于哪一天”用的列。
  - 股票代码列：标识股票或指数的列。
  - 是否静态表：`是`表示整张表不随日期变化；`否`表示每天都会新增数据。
- **一句话说明**。
- **学生最常用的 3～5 个列**。

> **怎么读这些表格？** 先看你感兴趣的“主题”（例如公司财务、日行情），再找到对应的数据集名字。日频表通常写进 `data.current(...)` 或 `data.history(...)`；公告、财报、股东等不定期更新的表通常写进 `data.latest(...)`。



> **列名缩写提示**：下面表格里的英文列名来自原始数据库字段。遇到不认识的名字时，可以用 `bundle.describe("表名")` 查看它的元信息。这里先列出最常见缩写的含义：
>
> | 缩写 | 含义 |
> |---|---|
> | `stkcd` / `Stkcd` / `Symbol` | 股票代码 |
> | `trddt` / `Trddt` / `date` | 交易日期 |
> | `accper` / `Accper` | 会计期间（也就是报告期） |
> | `typrep` / `Typrep` | 报表类型（例如合并报表、母公司报表） |
> | `declaredate` / `Annodt` / `PubliDate` | 公告发布日期 |
> | `clsprc` | 收盘价 |
> | `dretwd` | 考虑现金红利再投资的日收益率 |
> | `dnvaltrd` | 日成交额 |
> | `limitstatus` | 涨跌停状态码 |
> | `cumulatefwardfactor` | 累计前复权因子 |

### 4.1 公司基本信息

| 数据集 ID（别名） | 主日期 / 代码 / 静态 | 一句话说明 | 常用列 |
|---|---|---|---|
| `basic.company_info`（无别名） | 主日期：`statdt`<br>代码：`stkcd`<br>静态：否 | 上市公司基本信息，例如上市日期、行业、地区等。 | `stkcd`、`stknme`、`listdt`、`indcd`、`indnme`、`nindcd` |
| `basic.STK_INDUSTRYCLASS`<br>（`STK_INDUSTRYCLASS`） | 主日期：`ImplementDate`<br>代码：`Symbol`<br>静态：否 | 公司行业分类变更记录。 | `Symbol`、`ImplementDate`、`IndustryClassificationName`、`IndustryName` |

### 4.2 日行情与市场

| 数据集 ID（别名）                 | 主日期 / 代码 / 静态                          | 一句话说明                     | 常用列                                                                 |
| -------------------------- | -------------------------------------- | ------------------------- | ------------------------------------------------------------------- |
| `stock.daily_returns`（无别名） | 主日期：`trddt`<br>代码：`stkcd`<br>静态：否      | **个股日行情与收益率**，是写策略时最常用的表。 | `stkcd`、`trddt`、`clsprc`、`dretwd`、`dnvaltrd`、`limitstatus`          |
| `market.market_daily`（无别名） | 主日期：`date`<br>代码：无<br>静态：否             | 整个市场或分市场的日度汇总指标。          | `date`、`cdretwdeq`、`dretwdeq`、`mkt_turnoverrate1`、`mkt_marketvalue` |
| `market.index_daily`（无别名）  | 主日期：`idxtrd01`<br>代码：`indexcd`<br>静态：否 | 指数日行情，例如上证指数、深证成指。        | `indexcd`、`idxtrd01`、`idxtrd02`、`idxtrd05`、`idxtrd08`               |

### 4.3 公司财务

这四张表是原始的财务报表，列名是会计科目编码。如果你只需要常见的估值指标，可以直接看 4.6 节的 `factor_benchmark.relative_value.FI_T10`。

| 数据集 ID（别名）                    | 主日期 / 代码 / 静态                      | 一句话说明       | 常用列                                     |
| ----------------------------- | ---------------------------------- | ----------- | --------------------------------------- |
| `firm.balance_sheet`（无别名）     | 主日期：`accper`<br>代码：`stkcd`<br>静态：否 | 资产负债表。      | `stkcd`、`accper`、`typrep`、`declaredate` |
| `firm.income_statement`（无别名）  | 主日期：`accper`<br>代码：`stkcd`<br>静态：否 | 利润表。        | `stkcd`、`accper`、`typrep`、`declaredate` |
| `firm.cashflow_direct`（无别名）   | 主日期：`accper`<br>代码：`stkcd`<br>静态：否 | 现金流量表（直接法）。 | `stkcd`、`accper`、`typrep`、`declaredate` |
| `firm.cashflow_indirect`（无别名） | 主日期：`accper`<br>代码：`stkcd`<br>静态：否 | 现金流量表（间接法）。 | `stkcd`、`accper`、`typrep`、`declaredate` |

### 4.4 业绩预告与公司事件

| 数据集 ID（别名） | 主日期 / 代码 / 静态 | 一句话说明 | 常用列 |
|---|---|---|---|
| `financial_supplement.forecast_vs_report.BF_FORECAST`<br>（`BF_FORECAST`） | 主日期：`PubliDate`<br>代码：`Stkcd`<br>静态：否 | 业绩预告及后续实际业绩对比。 | `Stkcd`、`PubliDate`、`ForecFinReportType`、`RatNetProfPareComp_Hig`、`RatNetProfPareComp_Low` |
| `financial_supplement.distribution.TRD_Cptl`<br>（`TRD_Cptl`） | 主日期：`Annodt`<br>代码：`Stkcd`<br>静态：否 | 分红、送股、配股、增发等资本分配事件。 | `Stkcd`、`Annodt`、`Disttyp`、`Exdistdt`、`Amount` |
| `financial_supplement.equity_change.FN_FN046`<br>（`FN_FN046`） | 主日期：`Accper`<br>代码：`Stkcd`<br>静态：否 | 所有者权益变动表，记录净利润、利润分配、资本公积转增股本等。 | `Stkcd`、`Accper`、`Typrep`、`SubjectCode`、`SubjectName` |
| `financial_supplement.equity_change.FN_FN0461`<br>（`FN_FN0461`） | 主日期：`Accper`<br>代码：`Stkcd`<br>静态：否 | 所有者权益变动表的补充表。 | `Stkcd`、`Accper`、`Typrep`、`SubjectCode`、`SubjectName` |

### 4.5 行为金融

| 数据集 ID（别名）                                                                 | 主日期 / 代码 / 静态                       | 一句话说明                     | 常用列                                                               |
| -------------------------------------------------------------------------- | ----------------------------------- | ------------------------- | ----------------------------------------------------------------- |
| `behavioral_finance.executive_compensation.BF_EXPAY`<br>（`BF_EXPAY`）       | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 上市公司董事、监事及高管薪酬。           | `Stkcd`、`EndDate`、`SumSalary`、`Total_1`、`Total_3`                 |
| `behavioral_finance.executive_shareholding.BF_EXSHARE`<br>（`BF_EXSHARE`）   | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 高管持股明细，包含增减持标识。           | `Stkcd`、`EndDate`、`Name`、`EndShares`、`EndRatio`、`Class`           |
| `behavioral_finance.executive_shareholding.BF_EXSHARE1`<br>（`BF_EXSHARE1`） | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 高管持股的另一张汇总表。              | `Stkcd`、`EndDate`、`Name`、`EndShares`、`EndRatio`                   |
| `behavioral_finance.herd_industry_daily.BF_IHEAD`<br>（`BF_IHEAD`）          | 主日期：`Trddt`<br>代码：无<br>静态：否         | 行业层面羊群效应/趋同行为了日度指标。       | `Trddt`、`Nnindcd`、`CSAD1`、`CSSD1`、`Dretwdeq`                      |
| `behavioral_finance.herd_industry_daily.BF_IHEAD1`<br>（`BF_IHEAD1`）        | 主日期：`Trddt`<br>代码：无<br>静态：否         | 行业层面羊群效应补充表（学习数据集中行数为 0）。 | `Trddt`、`Nnindcd`                                                 |
| `behavioral_finance.herd_stock_daily.BF_MHEAD`<br>（`BF_MHEAD`）             | 主日期：`Trddt`<br>代码：无<br>静态：否         | 市场层面羊群效应/趋同行为了日度指标。       | `Trddt`、`MarketType`、`CSAD1`、`CSSD1`、`Dretwdeq`                   |
| `behavioral_finance.top10_shareholder.BF_HOLDER`<br>（`BF_HOLDER`）          | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 前十大股东持股情况。                | `Stkcd`、`EndDate`、`ShareHolderName`、`Holdshares`、`HoldProportion` |
| `behavioral_finance.top10_shareholder.BF_HOLDER1`<br>（`BF_HOLDER1`）        | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 前十大股东的补充明细表。              | `Stkcd`、`EndDate`、`ShareHolderName`、`Holdshares`、`HoldProportion` |
| `behavioral_finance.top10_shareholder.BF_HOLDER2`<br>（`BF_HOLDER2`）        | 主日期：`EndDate`<br>代码：`Stkcd`<br>静态：否 | 前十大股东的机构类别明细表。            | `Stkcd`、`EndDate`、`ShareHolderName`、`Holdshares`、`CategoryCode`   |
| `behavioral_finance.datago.上市公司网络搜索分析数据表_fullpacked_data.上市公司网络搜索分析数据表`<br>（`上市公司网络搜索分析数据表`） | 主日期：`pub_date`<br>代码：`stock_id`<br>静态：否 | 百度搜索关注度相关指标。 | `stock_id`、`pub_date`、`index_all`、`index_pc`、`index_mobile` |
| `behavioral_finance.datago.新闻情感量化数据表_fullpacked_data.新闻情感量化数据表`<br>（`新闻情感量化数据表`） | 主日期：`pub_date`<br>代码：无<br>静态：否 | 报刊新闻正文与标题情绪指标。 | `news_id`、`pub_date`、`neg_sents`、`pos_sents`、`overall_senti_score` |
| `behavioral_finance.datago.新闻相关上市公司表_fullpacked_data.新闻相关上市公司表`<br>（`新闻相关上市公司表`） | 主日期：`pub_date`<br>代码：`stkcd`<br>静态：否 | 报刊新闻与上市公司的关联明细。 | `news_id`、`pub_date`、`stkcd`、`ment_times`、`relev_score` |
| `behavioral_finance.datago.网络新闻相关上市公司表_fullpacked_data.网络新闻相关上市公司表`<br>（`网络新闻相关上市公司表`） | 主日期：`pub_date`<br>代码：`stkcd`<br>静态：否 | 网络新闻与上市公司的关联明细。 | `news_id`、`pub_date`、`stkcd`、`ment_times`、`relev_score` |
| `behavioral_finance.datago.股吧量化舆情表(交易时段分组)_fullpacked_data.股吧量化舆情表(交易时段分组)`<br>（`股吧量化舆情表(交易时段分组)`） | 主日期：`Pub_Date`<br>代码：`Stock_Id`<br>静态：否 | 股吧阅读、回复、发帖与情绪统计。 | `Stock_Id`、`Pub_Date`、`Trade_Time`、`Reads_Announce_Sum`、`Senti_Score_Div` |

Datago 表可以像其他表一样用长数据集 ID 或括号里的别名读取。有些新闻表还带有 `valid_date`，但平台按新闻或统计本身的 `pub_date` / `Pub_Date` 做日期边界。

### 4.6 因子与基准

| 数据集 ID（别名） | 主日期 / 代码 / 静态 | 一句话说明 | 常用列 |
|---|---|---|---|
| `factor_benchmark.adj_factor`（无别名） | 主日期：`tradingdate`<br>代码：`symbol`<br>静态：否 | 前复权累计因子，平台用它计算官方价格。 | `symbol`、`tradingdate`、`cumulatefwardfactor` |
| `factor_benchmark.relative_value.FI_T10`<br>（`FI_T10`） | 主日期：`Accper`<br>代码：`Stkcd`<br>静态：否 | 常用估值指标，例如市盈率、市净率、市销率等。 | `Stkcd`、`Accper`、`F100101B`、`F100401A`、`F100103C` |
| `factor_benchmark.carhart4.STK_MKT_CARHARTFOURFACTORS`<br>（`STK_MKT_CARHARTFOURFACTORS`） | 主日期：`TradingMonth`<br>代码：无<br>静态：否 | 月度 Carhart 四因子组合收益率。 | `TradingMonth`、`MarkettypeID`、`RiskPremium1`、`SMB1`、`HML1`、`UMD1` |
| `factor_benchmark.momentum_factor.STK_MKT_MOMENTUM`<br>（`STK_MKT_MOMENTUM`） | 主日期：`TradingMonth`<br>代码：无<br>静态：否 | 月度动量因子组合收益率。 | `TradingMonth`、`MarkettypeID`、`FormationPeriod`、`MomRe1`、`Mom52Weeks1` |

### 4.7 指数与国际数据

| 数据集 ID（别名） | 主日期 / 代码 / 静态 | 一句话说明 | 常用列 |
|---|---|---|---|
| `index_metadata.index_info.IDX_Gidxinfo`<br>（`IDX_Gidxinfo`） | 主日期：无<br>代码：`Indexcd`<br>静态：是 | 国际指数的基本信息。 | `Indexcd`、`Idxnme`、`Cuncd` |
| `index_metadata.index_info.IDX_Idxinfo`<br>（`IDX_Idxinfo`） | 主日期：无<br>代码：`Indexcd`<br>静态：是 | 国内指数的基本信息。 | `Indexcd`、`Idxinfo01`、`Idxinfo06`、`Idxinfo09` |
| `index_metadata.index_info.TRD_Index`<br>（`TRD_Index`） | 主日期：`Trddt`<br>代码：`Indexcd`<br>静态：否 | 国内指数日行情。 | `Indexcd`、`Trddt`、`Opnindex`、`Hiindex`、`Loindex`、`Clsindex` |
| `international.exchange_rate.TRD_Exchange`<br>（`TRD_Exchange`） | 主日期：无（静态表，含 `Exchdt` 列）<br>代码：无<br>静态：是 | 汇率数据，例如人民币对美元、港币汇率。 | `Exchdt`、`Rmbusd`、`Hkdrmb`、`Hkdusd` |
| `international.index_intl_daily.IDX_Gidxtrd`<br>（`IDX_Gidxtrd`） | 主日期：`Trddt`<br>代码：`Indexcd`<br>静态：否 | 国际指数日行情。 | `Indexcd`、`Trddt`、`Opnidx`、`Highidx`、`Lowidx`、`Clsidx` |

---

## 5. `stock.daily_returns` 字段清单

`stock.daily_returns` 是最常用的一张表，这一节把它的列名逐个列出来。每个列名后面只给一句话提示，详细含义请参考 [DataFrame 字段速查](./dataframe-field-guide.md)。

| 列名              | 一句话说明                             |
| --------------- | --------------------------------- |
| `stkcd`         | 六位股票代码。                           |
| `trddt`         | 交易日期。                             |
| `opnprc`        | 开盘价。                              |
| `hiprc`         | 最高价。                              |
| `loprc`         | 最低价。                              |
| `clsprc`        | 收盘价。                              |
| `dnshrtrd`      | 日成交量（股）。                          |
| `dnvaltrd`      | 日成交额（元）。                          |
| `dsmvosd`       | 日流通市值。                            |
| `dsmvtll`       | 日总市值。                             |
| `dretwd`        | 考虑现金红利再投资的日收益率。                   |
| `dretnd`        | 不考虑现金红利再投资的日收益率。                  |
| `adjprcwd`      | 考虑现金红利再投资的调整后收盘价。**注意：这不是官方收盘价。** |
| `adjprcnd`      | 不考虑现金红利再投资的调整后收盘价。                |
| `markettype`    | 市场类型编码。平台默认保留 `[1, 4, 16, 32, 64]`，即沪深主板、创业板、科创板和北交所 A 股。                           |
| `capchgdt`      | 股本变动日期。                           |
| `trdsta`        | 交易状态。                             |
| `ahshrtrd_d`    | A 股日成交量（股）。                       |
| `ahvaltrd_d`    | A 股日成交额（元）。                       |
| `precloseprice` | 昨日收盘价。                            |
| `changeratio`   | 涨跌幅。                              |
| `limitdown`     | 跌停价。                              |
| `limitup`       | 涨停价。                              |
| `limitstatus`   | 涨跌停状态，非 0 通常表示当天交易受限。             |

---

## 6. 官方价格不是 `adjprcwd`

很多同学第一次写策略时，会直接用 `adjprcwd` 当作“复权后的真实价格”。但在 QuantFish 平台上，**官方价格**是平台自己重新计算出来的，核心就下面三个公式：

- `raw_vwap = dnvaltrd / dnshrtrd`：用日成交额除以日成交量，得到日成交均价（`raw_vwap`，raw 表示“原始”）。
- `front_close = clsprc * cumulatefwardfactor`：用当日收盘价乘以**前复权累计因子**（`cumulatefwardfactor`），得到官方收盘价/结算价（`front_close`）。
- `front_vwap = raw_vwap * cumulatefwardfactor`：用日成交均价乘以前复权累计因子，得到**官方执行价**（`front_vwap`）。

**这意味着：**

- 回测时，平台用 `front_vwap` 给你成交。
- 计算当天持仓市值时，平台用 `front_close`。
- `adjprcwd` 只是原始数据里的一个参考列，**不要把它和官方价格混为一谈**。

作为初学者，只要记住：**策略里返回 `score`；平台会在回测时自动用官方执行价和结算价成交、结算。**不要把原始数据里的 `adjprcwd` 当成平台官方价格。

---

## 7. 三张速查表

### 速查 1：查日行情用哪个表？

| 你想查什么 | 用哪个数据集 |
|---|---|
| 个股每天的开盘价、收盘价、成交量、涨跌幅、涨跌停状态 | `stock.daily_returns` |
| 整个市场每天的综合指标，例如市场收益率、换手率 | `market.market_daily` |
| 上证指数、深证成指、沪深 300 等指数的日行情 | `market.index_daily` |

### 速查 2：查业绩预告用哪个表？

| 你想查什么 | 用哪个数据集 |
|---|---|
| 公司业绩预增/预减公告、预告净利润上下限 | `financial_supplement.forecast_vs_report.BF_FORECAST`（或别名 `BF_FORECAST`） |
| 业绩预告和正式报告发布后的实际净利润对比 | `financial_supplement.forecast_vs_report.BF_FORECAST` |

### 速查 3：查财务报表用哪个表？

| 你想查什么 | 用哪个数据集 |
|---|---|
| 资产负债表 | `firm.balance_sheet` |
| 利润表 | `firm.income_statement` |
| 现金流量表（直接法） | `firm.cashflow_direct` |
| 现金流量表（间接法） | `firm.cashflow_indirect` |
| 不想看原始会计科目，只想用市盈率、市净率等常用指标 | `factor_benchmark.relative_value.FI_T10`（别名 `FI_T10`） |

---

## 本章要点

- 每张表有数据集 ID（长名）和别名（短名），两者指向同一张表。
- 使用数据集时先问“我要查什么”，再选数据集、读取方法和列名。
- 日行情常用 `current` / `history`；公告、财报、股东等不定期数据常用 `latest`。
- 重点关注主日期列、股票代码列、是否静态等元信息，它们决定平台怎么按日期和股票读取数据。
- 要参与计算的列放进 `numeric_columns`，让平台自动把异常文本和空值转成 `NaN`。
- `stock.daily_returns` 是最常用的日行情表。
- 官方价格由 `front_close` / `front_vwap` 计算，不要直接使用 `adjprcwd`。
- 利用速查表可以快速定位“查日行情 / 业绩预告 / 财务报表用哪张表”。

上一步：[数据包接口](./02-data-bundle-api.md) | 下一步：[DataFrame 字段速查](./dataframe-field-guide.md)
