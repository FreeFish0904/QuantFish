# 数据包接口

在 [第一个策略](./01-first-strategy.md) 里，你已经见过 `generate_signals` 函数。它收到的第一个参数 `data` 是平台提供的数据视图（内部叫 `StudentDataView`）。

这个视图只公开了少量方法：`current`、`load`、`history`、`latest`、`list_datasets`、`describe`。你可以把它理解成一个“数据遥控器”：它背后连着整个学习数据集，但又被限制在某一个交易日当天。你按不同的按钮，就能拿到当天、过去一段时间、或者截至当天的最新数据。

> **注意：** 在 `generate_signals` 里，`data` 不是原始的 `DataBundle`/`DatedDataBundle`。`data.path(...)`、`data.load_raw(...)`、`data.at(...)` 这些方法**不存在**，调用会直接报错。需要全量数据或文件路径时，请在研究脚本里直接使用 `DataBundle`。

> **运行本章代码前，请确认：**
>
> - 已经激活 `QuantFish` 环境（终端提示符前面有 `(QuantFish)`）。
> - 当前目录是 QuantFish 项目根目录，否则 `DataBundle("data_releases/learning")` 会找不到文件夹。

## 1. 打开数据仓库的大门

使用 `DataBundle` 之前，要先创建**数据包对象**。数据包对象指向一个已经生成好的数据目录，负责帮你加载里面的各种数据表。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
```

**这行在做什么：**

- `from quantfish.data import DataBundle`：从 QuantFish 包里把 `DataBundle` 拿出来。
- `DataBundle("data_releases/learning")`：创建一个数据包对象，它知道去哪里找学习数据集里的所有文件。

这一行本身不会把所有数据都读进内存，只是“开门”。真正读取数据是在你调用后面的方法时发生的。

> **平台只交易配置允许的市场类型。** 默认配置 `execution.allowed_market_types` 是 `[1, 4, 16, 32, 64]`，覆盖沪深主板、创业板、科创板和北交所 A 股。如果研究脚本直接写 `DataBundle("data_releases/learning")` 而不传 `allowed_market_types`，它不会过滤市场类型，也可能读到 B 股等非目标市场。想与平台保持一致，可以显式指定：
>
> ```python
> bundle = DataBundle(
>     "data_releases/learning",
>     allowed_market_types=[1, 4, 16, 32, 64],
> )
> ```

## 2. 绑定日期：只能看到今天及之前

回测的时候，平台会按 `stock.daily_returns` 里的交易日逐个调用你的策略函数。每次调用时，它都会把 `data` 绑定到那个交易日。你手动做研究时，可以用 `bundle.at("YYYY-MM-DD")` 来绑定。

```python
data = bundle.at("2022-06-30")
```

**这行在做什么：**

- `bundle.at("2022-06-30")`：生成一个**日期绑定视图**。
- 这个 `data` 只能看到 2022-06-30 及之前的数据，2022-07-01 以后的数据对它来说是“未来”，不允许读取。

这一步非常重要。它保证你的策略在研究时不会“偷看未来”，和在平台上回测时的行为完全一致。

## 3. current 按钮：只读当天

`data.current(dataset, columns=[...])` 只返回绑定日期当天的数据。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "trddt", "clsprc", "dretwd", "dnvaltrd", "limitstatus"],
    numeric_columns=["clsprc", "dretwd", "dnvaltrd", "limitstatus"],
)

print(today.head())
```

**这行在做什么：**

- `"stock.daily_returns"`：要读取的数据集名称，这里用的是日行情表。
- `columns=[...]`：只要列表里的几列。如果你不写这一行，平台会返回这张表的所有列。
- `numeric_columns=[...]`：把指定列转成数字；空值或异常文本会变成 `NaN`。
- `today.head()`：打印结果的前几行，方便你观察数据长什么样。

返回的结果是一张**表格**（pandas 里的 `DataFrame`），每一行是一只股票在 2022-06-30 这一天的记录。

完整可运行示例见 [`examples/load_current.py`](./examples/load_current.py)。

## 4. load 按钮：读一段时间

`data.load(dataset, start=..., end=..., columns=[...])` 可以读取从 `start` 到 `end` 之间的所有数据。如果你不传 `end`，它默认就是绑定日期。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

window = data.load(
    "stock.daily_returns",
    start="2022-01-01",
    end="2022-06-30",
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)

print("从", window["trddt"].min(), "到", window["trddt"].max())
print("总行数:", len(window))
```

**这行在做什么：**

- `start="2022-01-01"`：从 2022-01-01 开始读。
- `end="2022-06-30"`：读到 2022-06-30 为止。
- 不传 `end` 时，平台会自动把它当成绑定日期 2022-06-30。
- `numeric_columns=["clsprc", "dretwd"]`：让平台把收盘价和收益率转成数字。

这个方法适合需要计算过去几个月累计收益、波动率等场景。

## 5. history 按钮：读过去 N 天

如果你不想写明确的开始日期，可以用 `data.history(dataset, lookback_days=60, columns=[...])`。它会自动从绑定日期往前数 60 个自然日，读到绑定日期为止。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

history = data.history(
    "stock.daily_returns",
    lookback_days=60,
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)

print("从", history["trddt"].min(), "到", history["trddt"].max())
print("总行数:", len(history))
```

**这行在做什么：**

- `lookback_days=60`：从 2022-06-30 往回推 60 天，也就是大约从 2022-05-01 开始。
- 注意：这里按自然日计算，包含周末。所以实际返回的交易日数量通常会少于 60 天。
- `numeric_columns` 的含义和 `current` 一样，只转换你明确列出来的字段。

`history` 其实底层调用的就是 `load`，只是帮你自动算好了开始日期。

> **`history` 的两个限制：**
>
> - 不能同时传 `start` 和 `lookback_days`，只能二选一。
> - `lookback_days` 必须是非负数。
>
> 违反任意一条都会抛出 `ValueError`。

完整可运行示例见 [`examples/load_history.py`](./examples/load_history.py)。

## 6. latest 按钮：每只股票取最新一条

有些数据不是每天都有，比如业绩预告、财务报表、股东持股等。你想知道“每只股票截至今天最新的那一条公告”时，就用 `data.latest`。

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

latest = data.latest(
    "BF_FORECAST",
    by="Stkcd",
    columns=["Stkcd", "PubliDate", "ForecFinReportType", "RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
    numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
)

print(latest.head())
```

**这行在做什么：**

- `"BF_FORECAST"`：业绩预告表的数据集名称。
- `by="Stkcd"`：按股票代码分组，对每只股票分别取最新一条。
- `columns=[...]`：只要这几列。
- `numeric_columns=[...]`：把预告净利润同比增速上下限转成数字。
- 返回的表格里，每只股票最多只有一行，内容是它在 2022-06-30 或之前最新发布的一条预告。

如果你写 `by=None`，平台会优先用数据集中默认的股票代码列来分组；如果这张表没有股票代码列，就返回整张表里日期最新的那一行。

完整可运行示例见 [`examples/load_latest.py`](./examples/load_latest.py)。

## 7. numeric_columns：让平台帮你转数字

原始数据里有些数值字段可能混有空值或异常文本。读取数据时，可以把要用于计算的列放进 `numeric_columns`：

```python
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "dretwd", "dnvaltrd"],
    numeric_columns=["dretwd", "dnvaltrd"],
)
```

**这行在做什么：**

- 平台只会转换 `numeric_columns` 里明确列出的字段。
- 转得成数字的值会变成数值类型。
- 空值、异常文本、无法解释的内容会变成 `NaN`（表示“没有有效数字”）。
- 如果你写了不存在于返回表格里的列名，平台会抛出清楚的 `KeyError`，提醒你检查列名。

> **小技巧：** 凡是接下来要用来加减乘除的列，都建议写进 `numeric_columns`。这样即使原始数据里有乱码或空值，也不会在后续计算时突然报错。

## 8. 查看有哪些数据集：list_datasets / describe / path

刚开始写策略时，你可能不记得某张表的确切名字。数据包对象提供了几个“目录”方法。

### list_datasets：列出所有数据集名称

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
names = bundle.list_datasets()

print("总共有", len(names), "个数据集")
print(names[:10])  # 只看前 10 个
```

**这行在做什么：**

- `bundle.list_datasets()`：返回学习数据集里所有数据表的正式名称列表。
- `names[:10]`：只打印前 10 个名称，方便快速浏览。

### describe：查看一张表的元信息

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
spec = bundle.describe("stock.daily_returns")

print("数据集 ID:", spec.dataset_id)
print("文件格式:", spec.format)
print("相对路径:", spec.relative_path)
print("日期列:", spec.primary_asof_column)
print("股票代码列:", spec.symbol_column)
```

**这行在做什么：**

- `bundle.describe("stock.daily_returns")`：返回这张表的描述信息。
- `spec.dataset_id`：这张表的正式名称。
- `spec.format`：文件格式，比如 `csv`（纯文本表格格式）或 `parquet`（一种压缩后的高效列式存储格式）。
- `spec.primary_asof_column`：平台用来判断“这条记录属于哪一天”的日期列。
- `spec.symbol_column`：这张表里的股票代码列名。

### path：查看文件存在哪里

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
file_path = bundle.path("stock.daily_returns")

print("文件位置:", file_path)
```

**这行在做什么：**

- `bundle.path(...)`：返回这张表文件在你电脑上的完整路径。
- 你一般不需要手动打开它，但知道这个路径有助于理解平台是怎么组织数据的。

## 9. 为什么不能看未来：FutureDataAccessError

日期绑定视图最重要的作用就是防止你读取未来数据。如果你请求的日期区间超出了绑定日期——无论是 `start` 还是 `end` 晚于绑定日期——平台都会抛出一个 `FutureDataAccessError`。

### 会报错的代码

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

# 错误：end 传了 2022-07-15，比绑定日期还晚
bad = data.load(
    "stock.daily_returns",
    start="2022-06-01",
    end="2022-07-15",
    columns=["stkcd", "trddt", "dretwd"],
    numeric_columns=["dretwd"],
)
```

运行上面的代码会报错：

```text
FutureDataAccessError: end date 2022-07-15 is after bound date 2022-06-30
```

**这行在做什么：**

- 你绑定的是 2022-06-30，但请求读到 2022-07-15。
- 平台发现你想“偷看未来”，于是直接报错。

### 修正后的代码

把 `end` 改成绑定日期或之前，或者干脆不传 `end`：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

# 正确：只读到绑定日期
ok = data.load(
    "stock.daily_returns",
    start="2022-06-01",
    end="2022-06-30",  # 也可以直接删掉这一行
    columns=["stkcd", "trddt", "dretwd"],
    numeric_columns=["dretwd"],
)

print("从", ok["trddt"].min(), "到", ok["trddt"].max())
```

**这行在做什么：**

- `end="2022-06-30"`：结束日期不超过绑定日期，所以平台允许读取。
- 如果删掉 `end`，平台会自动把绑定日期当成结束日期。

### start 也不能晚于绑定日期

下面这种写法同样会报错：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

# 错误：start 传了 2022-07-01，比绑定日期还晚
bad = data.load(
    "stock.daily_returns",
    start="2022-07-01",
    columns=["stkcd", "trddt", "dretwd"],
    numeric_columns=["dretwd"],
)
```

错误信息和 `end` 越界类似：

```text
FutureDataAccessError: start date 2022-07-01 is after bound date 2022-06-30
```

也就是说，**`start` 和 `end` 都必须 ≤ 绑定日期**。

### 没有日期列的静态表不受限制

`FutureDataAccessError` 只针对带日期列的时间序列表。如果一张表没有日期列（例如 `spec.primary_asof_column` 为 `None`），平台会把它当作静态参考表，可以一次性完整加载，不受绑定日期限制。

## 小结

| 方法 | 作用 | 常用场景 |
|---|---|---|
| `bundle.at(date)` | 绑定到某一天，生成日期绑定视图 | 每次研究或回测时固定观察点 |
| `data.current(...)` | 只读绑定日期当天的数据 | 获取当天所有股票的行情 |
| `data.load(...)` | 读一段时间的数据 | 计算过去几个月的累计收益或波动率 |
| `data.history(...)` | 读过去 N 天的数据 | 用固定窗口做滚动计算 |
| `data.latest(...)` | 每只股票取最新一条 | 读取财报、预告等非日频数据 |
| `numeric_columns=[...]` | 把指定返回列转成数字 | 计算收益、价格、成交额、市值等数值字段 |
| `bundle.list_datasets()` | 列出所有数据集 | 查看平台提供了哪些表 |
| `bundle.describe(...)` | 查看表的元信息 | 确认日期列、股票代码列、文件格式 |
| `bundle.path(...)` | 查看文件路径 | 理解数据在磁盘上的组织方式 |

记住一个核心原则：**有时间序列的表，绑定日期之后的都是未来，不能读取**。没有日期列的静态参考表可以完整加载，不受这个限制。这是保证你的策略在回测时不会作弊的关键。

---

## 本章要点

- `DataBundle("data_releases/learning")` 打开数据集，`bundle.at(date)` 生成日期绑定视图。
- `current` 读当天；`load` 读区间；`history` 读过去 N 天；`latest` 取每只股票最新一条。
- 用 `numeric_columns=[...]` 读取要计算的数值列，异常文本和空值会变成 `NaN`。
- `list_datasets`、`describe`、`path` 帮你查表名、列名和文件位置。
- 绑定日期之后的数据属于未来，访问会触发 `FutureDataAccessError`；没有日期列的静态表除外。
- 只读取需要的列，能让策略更快、更省内存。

相关代码示例：[load_current.py](./examples/load_current.py)、[load_history.py](./examples/load_history.py)、[load_latest.py](./examples/load_latest.py)

上一步：[第一个策略](./01-first-strategy.md) | 下一步：[数据集目录](./03-dataset-catalog.md)
