# DataFrame 字段速查

前面你已经学会用 `data.current(...)` 从 QuantFish 的数据包中拿数据。本章专门回答一个问题：**拿到手的表格里到底有什么？每一列是什么意思？**

读完本章，你会知道：

- `pandas DataFrame` 就是一个带行列的表格。
- `stock.daily_returns` 里每一列代表什么，哪些列可能是空的（`NaN`）。
- 业绩预告表 `BF_FORECAST` 里那些长名字字段是什么意思。
- 另外几张常用表的用途：`market.market_daily`、`factor_benchmark.adj_factor`、`financial_supplement.distribution.TRD_Cptl`。
- 怎样用几行代码快速查看一张表的列名和内容。
- `data.current`、`data.latest`、`data.load` 返回的表格在“行数”上有什么区别。

---

## 1. 先认识 DataFrame：一张表格

在 Python 的 `pandas` 库中，`DataFrame`（读作“数据框”）就是一张**二维表格**：

- 每一行是一条记录。
- 每一列是一种属性。
- 列有名字，行也有一个“索引”。

下面这个例子把 2022-06-30 的日行情表读进变量 `df` 里：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")  # 数据包对象
data = bundle.at("2022-06-30")                 # 日期绑定视图，只能看到这一天及之前的数据

df = data.current("stock.daily_returns")       # 取出当天的日行情表
```

**这行在做什么：**

- `DataBundle(...)` 打开学习数据集所在的目录。
- `bundle.at("2022-06-30")` 生成一个**日期绑定视图**。研究时它是 `DatedDataBundle`；在策略函数里，平台会把它包装成只公开 `current`/`load`/`history`/`latest`/`list_datasets`/`describe` 的 `StudentDataView`。
- `data.current("stock.daily_returns")` 只取 2022-06-30 这一天的行情，返回一个 `DataFrame`。

现在你只需要记住一个取列的方法：用方括号加列名。

```python
# 取出一列
prices = df["clsprc"]

# 同时取出多列
subset = df[["stkcd", "trddt", "clsprc", "dretwd"]]
```

**这行在做什么：**

- `df["clsprc"]` 会把收盘价那一整列抽出来，单独一个列也叫 `Series`（序列）。
- `df[["stkcd", "trddt", "clsprc", "dretwd"]]` 会返回一个新表格，只包含你指定的四列。

---

## 2. `stock.daily_returns`：最常用的一张表

### 2.1 一行代表什么

`stock.daily_returns` 是 QuantFish 里最常用的日行情表。

> **一行 = 一只股票在一个交易日的数据。**

如果某只股票当天没有交易（停牌、退市、未上市），通常就不会出现在当天的行里；但有时候会出现一行但部分字段是空的（`NaN`）。

下面是一个完整读取的例子：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

df = data.current("stock.daily_returns")
print(df.shape)        # 先看表格大小
print(list(df.columns))  # 再看有哪些列
```

**这行在做什么：**

- `df.shape` 返回 `(行数, 列数)`，例如 `(4892, 24)`，表示当天有 4892 只股票、24 列数据。
  - 不同交易日行数会不同，这里只是示例。
- `df.columns` 返回所有列名。用 `list(...)` 把它转成普通的 Python 列表，方便阅读。

### 2.2 列的完整解释

`stock.daily_returns` 的列大致可以分为几组：股票标识、价格、成交量/成交额、市值、收益率、复权价、昨收与涨跌幅、涨跌停信息、其他辅助字段。

#### 标识列

| 列名 | 含义 | 说明 |
|---|---|---|
| `stkcd` | 六位股票代码 | 例如 `"000001"`。平台内部会自动统一成 6 位字符串。 |
| `trddt` | 交易日期 | 字符串格式 `"2022-06-30"`，表示这一行属于哪一天。 |
| `markettype` | 市场板块码 | 例如主板、创业板、科创板、北交所等的分类编码。 |

#### 价格列：开高低收（单位：元）

| 列名 | 含义 |
|---|---|
| `opnprc` | 开盘价：当天第一笔成交的价格。 |
| `hiprc` | 最高价：当天成交过的最高价格。 |
| `loprc` | 最低价：当天成交过的最低价格。 |
| `clsprc` | 收盘价：当天最后一笔成交的价格，也叫“原始收盘价”。 |

#### 成交量与成交额

| 列名 | 含义 | 单位 |
|---|---|---|
| `dnshrtrd` | 成交量 | 股。例如 `154874501` 表示当天成交了约 1.55 亿股。 |
| `dnvaltrd` | 成交额 | 元。例如 `2.304889e+09` 是科学计数法，表示约 23.05 亿元。 |

> `dnvaltrd / dnshrtrd` 可以得到当天成交均价，也就是 `raw_vwap`（原始成交均价）。平台后来会用复权因子把它调整为**官方执行价** `front_vwap`。

#### 市值列

| 列名 | 含义 |
|---|---|
| `dsmvosd` | 流通市值：按流通股股本计算的总市值。 |
| `dsmvtll` | 总市值：按全部股本计算的总市值。 |

这两个值单位都是元，数值通常很大，可以用科学计数法表示。

#### 收益率列

| 列名 | 含义 |
|---|---|
| `dretwd` | 日收益率（含分红再投资）：假设把分红也重新买入股票后的收益。 |
| `dretnd` | 日收益率（不含分红）：只看价格变动的收益。 |

对大部分策略来说，`dretwd` 是默认使用的日收益率。如果当天停牌或数据缺失，这一列可能是 `NaN`。

#### 复权价格列

| 列名 | 含义 |
|---|---|
| `adjprcwd` | 前复权收盘价（含分红再投资调整）。 |
| `adjprcnd` | 前复权收盘价（不含分红调整）。 |

> **注意：`adjprcwd` 不是 QuantFish 的官方结算价/执行价。** 平台在回测时会自己重建官方价格：
>
> ```text
> raw_vwap   = dnvaltrd / dnshrtrd
> front_close = clsprc * cumulatefwardfactor
> front_vwap  = raw_vwap * cumulatefwardfactor
> ```
>
> 其中 `cumulatefwardfactor` 来自 `factor_benchmark.adj_factor` 表。所以你在做策略研究时，可以先用 `clsprc` 和 `dnvaltrd/dnshrtrd` 思考，平台会自动帮你算好执行价。

#### 昨收与涨跌幅

| 列名 | 含义 |
|---|---|
| `precloseprice` | 昨收：上一个交易日的收盘价，用来计算当天涨跌幅。 |
| `changeratio` | 原始涨跌幅：例如 `0.023224` 表示上涨 2.3224%。 |

#### 涨跌停相关列

| 列名 | 含义 |
|---|---|
| `limitup` | 涨停价：当天允许成交的最高价格。 |
| `limitdown` | 跌停价：当天允许成交的最低价格。 |
| `limitstatus` | 涨跌停状态码。`0` 表示正常交易；非 `0` 表示当天交易受限（涨停、跌停、停牌等）。具体编码值（例如区分涨停/跌停/停牌）可参考数据说明书；写策略时通常只需判断它是否为 0。 |

> 平台回测执行层会处理 `limitstatus != 0` 的交易限制。入门策略不需要手动过滤；如果你想在信号层提前把这些股票设成中性，可以参考 `examples/limit_guard.py`。

#### 交易状态与其他列

| 列名 | 含义 |
|---|---|
| `trdsta` | 交易状态码，用来标识正常交易、停牌、退市整理期等状态。具体编码可查看对应数据库说明书。 |
| `capchgdt` | 股本变动日期，表示最近一次股本变动生效的日期。 |
| `ahshrtrd_d` / `ahvaltrd_d` | A+H 股相关的成交量、成交额，通常只在同时发行 A 股和 H 股的股票上有值。 |

### 2.3 哪些列可能是 `NaN`？

`NaN` 是 pandas 里表示“没有数据”的标记。它不是一个数字，也不是字符串。在 `stock.daily_returns` 里，常见原因有：

- **停牌**：当天没有交易，`dretwd`、`dretnd`、`dnshrtrd`、`dnvaltrd` 等可能为 `NaN`。
- **新股**：刚上市前几天的某些字段可能不完整。
- **A+H 专用列**：`ahshrtrd_d`、`ahvaltrd_d` 不是每只股都有。
- **市值/收益字段**：在极少数历史数据里也可能缺失。

如果你需要跳过这些缺失值，可以用：

```python
# 只保留 dretwd 不是 NaN 的行
df = df[df["dretwd"].notna()]
```

**这行在做什么：**

- `df["dretwd"].notna()` 会对每一行判断 `dretwd` 是否有值，返回一列 `True/False`。
- `df[...]` 只保留判断为 `True` 的行。

---

## 3. `BF_FORECAST`：业绩预告表

### 3.1 一行代表什么

> **一行 = 一只股票发布的一次业绩预告。**

上市公司在正式财报公布前，有时会先发布一个“业绩预告”，告诉投资者“我们预计这一期净利润大概会增长多少”。`BF_FORECAST` 就是这类预告的合集。

它的完整数据集 ID 是 `financial_supplement.forecast_vs_report.BF_FORECAST`，你也可以直接用别名 `BF_FORECAST`。

因为它不是每天都有新预告，所以通常用 `data.latest(...)` 取“截至当天每只股票的最新预告”：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

df = data.latest("BF_FORECAST")
print(df.shape)
print(list(df.columns))
```

**这行在做什么：**

- `data.latest("BF_FORECAST")` 会返回“在 2022-06-30 或之前，每只股票最新的一条业绩预告”。
- 行数通常和股票数量接近，但远多于单日新增预告。

### 3.2 核心列解释

| 列名 | 含义 |
|---|---|
| `Stkcd` | 六位股票代码。 |
| `EndDate` | 报告期。例如 `"2010-12-31"` 表示这是 2010 年年报的业绩预告。 |
| `PubliDate` | 业绩预告的发布日期。 |
| `Anondt` | 对应正式财报的公告日期。 |
| `ForecFinReportType` | 预告类型，用中文简写表示公司业绩的增减方向。 |
| `RatNetProfPareComp_Hig` | 归属于上市公司股东的净利润同比增长区间的上限。 |
| `RatNetProfPareComp_Low` | 归属于上市公司股东的净利润同比增长区间的下限。 |
| `NetProfPareComp_Hig` | 归属于上市公司股东的净利润绝对值区间的上限。 |
| `NetProfPareComp_Low` | 归属于上市公司股东的净利润绝对值区间的下限。 |
| `NetProfPareCompLast` | 上年同期的净利润绝对值。 |
| `ReaFinResuVari` | 业绩变动原因的文本说明。 |
| `Status` | 数据状态码，例如 `A` 通常表示正常。 |

### 3.3 `ForecFinReportType` 的中文含义

这是学生最容易困惑的一列。下面是所有可能出现的类型：

| 类型值 | 含义 |
|---|---|
| `大增` | 净利润大幅增长。 |
| `扭亏` | 之前亏损，本期转为盈利。 |
| `略增` | 净利润小幅增长。 |
| `续盈` | 上期盈利，本期继续盈利。 |
| `不确定` | 公司无法判断业绩方向。 |
| `略降` | 净利润小幅下降。 |
| `续亏` | 上期亏损，本期继续亏损。 |
| `转亏` | 之前盈利，本期转为亏损。 |
| `大降` | 净利润大幅下降。 |

### 3.4 同比增长 vs 绝对值区间

这两组列经常一起出现：

- `RatNetProfPareComp_Hig` / `RatNetProfPareComp_Low` 是**同比增长率区间**。
  - 单位是百分比，但表里的数字已经省略了 `%`。
  - 例如 `70.0` 表示增长 70%。
  - 如果是 `NaN`，说明预告没有给出增长率区间。
- `NetProfPareComp_Hig` / `NetProfPareComp_Low` 是**净利润绝对值区间**。
  - 单位是元。
  - 例如 `1.026320e+09` 表示约 10.26 亿元。

如果一个策略想看“业绩预增”的股票，通常会筛选 `ForecFinReportType` 为 `大增`、`扭亏`、`略增`、`续盈`，或者筛选 `RatNetProfPareComp_Low` 大于某个正值。

---

## 4. 其他常用表简化字段指南

### 4.1 `market.market_daily`：市场每日综合数据

> **一行 = 一个市场/板块在一个交易日的综合统计。**

这张表包含整个市场层面的数据，比如全市场成交额、市场收益率、市场市盈率、换手率等。列非常多（例如 50 多列），初学者不需要全部记住。

常用列：

| 列名 | 含义 |
|---|---|
| `date` | 交易日期。 |
| `markettype` | 市场板块码。 |
| `dretwdeq` | 流通市值加权的市场日收益率（含分红再投资）。 |
| `dretmdeq` | 等权的市场日收益率。 |
| `dretwdos` / `dretmdos` | 不同口径的市场日收益率，具体口径可查看数据说明。 |
| `dnvaltrdtl` | 全市场总成交额。 |
| `dnshrtrdtl` | 全市场总成交量。 |
| `mkt_marketvalue` | 全市场总市值。 |
| `mkt_circulatedmktvalue` | 全市场流通市值。 |
| `mkt_avgpe` | 全市场平均市盈率。 |
| `mkt_turnoverrate1` / `mkt_turnoverrate2` | 不同口径的换手率。 |

> 列名里常见的英文缩写：`dret` = daily return（日收益率），`wd` = with dividend（含分红再投资），`eq` = equity-weighted（流通市值加权），`md` = equal-weighted（等权），`mkt` = market（市场）。

> 用 `data.current("market.market_daily")` 取某一天，通常只会返回少数几行（不同市场类型）。

### 4.2 `factor_benchmark.adj_factor`：复权因子表

> **一行 = 一只股票在某一天的复权调整因子。**

当股票发生分红、送股、配股时，历史价格需要调整才能前后比较。复权因子就是用来做这个调整的系数。

| 列名 | 含义 |
|---|---|
| `tradingdate` | 交易日期。 |
| `symbol` | 股票代码。注意这里的列名是 `symbol`，不是 `stkcd`。 |
| `fwardfactor` | 单日前复权因子（`fward` 是 forward，向前复权）。 |
| `bwardfactor` | 单日后复权因子（`bward` 是 backward，向后复权）。 |
| `cumulatefwardfactor` | 累计前复权因子（`cumulate` 是累计），QuantFish 用它来计算**官方收盘价**和**官方执行价**。 |
| `cumulatebwardfactor` | 累计后复权因子。 |

> 平台里的**官方收盘价/结算价**和**官方执行价**是这样算的：
>
> ```text
> front_close = clsprc * cumulatefwardfactor
> front_vwap  = (dnvaltrd / dnshrtrd) * cumulatefwardfactor
> ```
>
> 你的策略函数只需要返回 `code` 和 `score`，平台会自动用这些官方价格替你成交和结算。

### 4.3 `financial_supplement.distribution.TRD_Cptl`：公司资本事件表

> **一行 = 一只股票的一次资本变动事件。**

这张表记录分红、送股、配股、增发等资本事件。完整 ID 是 `financial_supplement.distribution.TRD_Cptl`，也可以用别名 `TRD_Cptl`。

| 列名 | 含义 |
|---|---|
| `Stkcd` | 六位股票代码。 |
| `Disttyp` | 分配类型编码，例如 `SD`（送股）、`CA`（派现）等。具体编码含义可查看对应数据库说明书。 |
| `Exdistdt` | 除权除息日，事件正式生效的日期。 |
| `Annodt` | 公告日，公司公告该事件的日期。 |
| `Paydt` | 支付/到账日，红利或股份实际到账的日期。 |
| `Amount` | 每股数量，例如每股派现 0.30 元、每股送股 0.5 股。 |
| `Roprc` | 再发行价格，配股、增发时用到；现金分红时通常为 0。 |
| `Markettype` | 市场板块码。 |

---

## 5. 调试代码：先看列名，再看内容

不知道一张表有哪些列时，先用下面这段代码。这是本章最重要的调试习惯：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

df = data.current(
    "stock.daily_returns",
    columns=["stkcd", "trddt", "dretwd"],
    numeric_columns=["dretwd"],
)

print(df.shape)      # 行数和列数
print(df.columns)    # 列名
print(df.head())     # 前 5 行
```

**这行在做什么：**

- `columns=["stkcd", "trddt", "dretwd"]` 只读取你关心的三列，表格更小、速度更快。
- `numeric_columns=["dretwd"]` 让平台把日收益率转成数字，异常文本或空值会变成 `NaN`。
- `df.shape` 会输出类似 `(4892, 3)`，表示 4892 行、3 列。不同交易日行数会变化。
- `df.columns` 会输出类似 `Index(['stkcd', 'trddt', 'dretwd'], dtype='str')`，告诉你列名和顺序。
- `df.head()` 会打印前 5 行的内容，例如：

```text
            stkcd      trddt    dretwd
11905028   000001 2022-06-30  0.023224
11905029   000002 2022-06-30  0.044320
11905030   000004 2022-06-30  0.003378
11905031   000005 2022-06-30  0.016760
11905032   000006 2022-06-30 -0.014644
```

> 注意：最左边的一列是 pandas 自动保留的“原始行号”，你暂时不用管它。不同电脑上输出的列宽、小数位数可能略有不同，但意思一样。`head()` 只是让你快速“瞄一眼”。

---

## 6. `current`、`latest`、`load` 返回的 DataFrame 行数有什么区别？

三张接口返回的表格结构一样（都是 `DataFrame`），但**行数不同**，因为它们回答的问题不同：

| 接口 | 含义 | 典型行数示例（以 2022-06-30 的 `stock.daily_returns` 为例） |
|---|---|---|
| `data.current(...)` | “这一天”的数据。 | 约 4892 行（当天有交易的股票）。 |
| `data.latest(...)` | “截至这一天，每只股票最新的一条”数据。 | 约 5114 行（包含当天没交易但之前交易过的股票）。 |
| `data.load(..., start=..., end=...)` | 从 `start` 到 `end` 之间所有交易日的数据。 | 2022-06-01 到 2022-06-30 约有 10 万+ 行。 |

代码对比：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

# 只取当天
today = data.current("stock.daily_returns", columns=["stkcd", "trddt"])
print("current:", today.shape)

# 每只股票截至当天最新的记录
latest = data.latest("stock.daily_returns", columns=["stkcd", "trddt"])
print("latest :", latest.shape)

# 2022-06-01 到 2022-06-30 的所有日行情
history = data.load(
    "stock.daily_returns",
    start="2022-06-01",
    end="2022-06-30",
    columns=["stkcd", "trddt"],
)
print("load   :", history.shape)
```

**这行在做什么：**

- `today.shape` 显示当天有多少只股票有数据。
- `latest.shape` 显示截至当天一共有多少只不同的股票有过数据。
- `history.shape` 显示这段日期范围内累计有多少条“股票-日期”记录。

> 还有一个 `data.history(..., lookback_days=20)`，它和 `data.load(..., start=..., end=...)` 本质一样，只是用“往前推多少天”来代替写开始日期。例如 `lookback_days=20` 会取从 20 天前到当前日期的数据。

---

## 7. 不要背所有列

QuantFish 的数据集很多，每张表又有几十列，**不要试图死记硬背**。

正确的做法是：

1. 先用 `print(df.columns)` 或 `print(list(df.columns))` 看看有哪些列。
2. 再用 `print(df.head())` 瞄几行真实数据。
3. 遇到不认识的列名，回到本章查询含义。
4. 写策略时，只读取你需要的列，表格会更快、更省内存。

---

---

## 本章要点

- pandas DataFrame 是带行列的表格，`df["列名"]` 可取出单列。
- `stock.daily_returns` 常见列含义及 `NaN` 的常见原因（停牌、新股、缺失等）。
- `BF_FORECAST` 业绩预告中 `ForecFinReportType`、增速上下限等字段的含义。
- `current`、`latest`、`load` 返回的 DataFrame 行数不同，分别对应不同问题。
- 调试时先用 `df.shape`、`list(df.columns)`、`df.head()` 观察数据。

上一步：[数据集目录](./03-dataset-catalog.md) | 下一步：[策略函数深入解析](./04-generate-signals-deep-dive.md)
