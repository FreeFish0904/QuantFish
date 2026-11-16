# 策略函数深入解析

在 QuantFish 里，策略文件只有一个核心入口：

```python
def generate_signals(data, date):
    ...
```

如果你不需要用到 `date`，只写一个参数也完全合法：

```python
def generate_signals(data):
    ...
```

平台会自动识别参数个数。你可以把它理解成“每个交易日收盘后，平台问你：今天每只股票打多少分？”

> **参数必须是位置参数。** 不要把 `date` 写成关键字参数，例如 `def generate_signals(data, *, date)`。平台只统计普通位置参数，关键字参数不会被识别为第二个参数，策略可能收不到 `date`。

---

## 1. 最推荐的新手写法：返回 Series

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    day_return = today["dretwd"]
    score = -day_return
    return pd.Series(score.values, index=today["stkcd"])
```

这段代码返回一个 `pd.Series`：

- index 是股票代码；
- value 是 `score`；
- 平台会自动把它整理成内部需要的 `date`、`code`、`score` 三列。

这是最适合第一天使用的写法，因为学生只需要关注 `score`。

---

## 2. `data` 和 `date` 是什么

`data` 是平台提供的数据视图（内部叫 `StudentDataView`），不是完整的 `DataBundle`。它只能看到当前交易日及以前的数据，不能读取未来。在 `generate_signals` 里，它只公开这些方法：

| 接口 | 用途 |
|---|---|
| `data.current(...)` | 只读当天数据 |
| `data.load(...)` | 读一段时间的数据 |
| `data.history(...)` | 读过去一段历史数据 |
| `data.latest(...)` | 每只股票取截至当天最新一条记录 |
| `data.list_datasets()` | 列出所有数据集名称 |
| `data.describe(...)` | 查看一张表的元信息 |

`date` 是当前交易日。大多数入门策略不需要直接使用它，因为 `data.current(...)` 已经自动绑定到当天。

> **注意：** `data.path(...)`、`data.load_raw(...)`、`data.at(...)` 在 `generate_signals` 里不存在。需要文件路径或全量原始数据时，请在研究脚本里直接使用 `DataBundle`。

---

## 3. `score` 是什么

`score` 是你对每只股票的相对打分。

- `score` 越高：平台越偏向做多或排到前面。
- `score` 越低：平台越不看好，长短仓模式下可能进入空头侧。
- `NaN`：表示这只股票今天没有信号。显式返回 `NaN` 是允许的，平台会把它当作“无信号”处理。
- `0`：是中性信号。如果组合构建规则允许，它仍然会被持有；它和 `NaN` 不是一回事。

注意：只有无法被转成数字的值（如 `"高"`、`"1.2%"`）才会触发 `StrategySignalError: signal scores must be numeric`；`NaN` 不会触发这个错误。

例如短期反转：

```python
score = -today["dretwd"]
```

`dretwd` 是当天日收益率。读取时传入 `numeric_columns=["dretwd"]` 后，平台会把它转成数字，异常文本或空值会变成 `NaN`。前面加负号后，当天跌得越多，分数越高。

你可以同时读取多列数据并在函数内组合它们，例如 `data.current(..., columns=["dretwd", "dnvaltrd", "dsmvosd"])`。

---

## 4. 平台会自动整理股票代码

原始数据里的股票代码可能是：

- `1`
- `1.0`
- `"000001"`

你返回 Series 时可以直接用原始 `stkcd` 做 index：

```python
return pd.Series(score.values, index=today["stkcd"])
```

平台收到后会统一整理成六位字符串，例如 `"000001"`。具体做法是：先把代码转成字符串，去掉末尾的 `.0`，然后用 `zfill(6)` 补齐六位，最后取最右边六位。如果你的代码长度超过六位（例如 `"1234567"`），它会被截成 `"234567"`，而不是报错。

对于 `pd.Series` 返回，平台会自动把索引规范化为 6 位代码；手动写 `.astype(str).str.zfill(6).str[-6:]` 是可选但无害的，只有在你策略内部用股票代码做合并/对齐时才需要显式处理。最安全的做法是直接返回已经是六位的代码。

只有在你自己要用 pandas `merge`（把两张表格按股票代码合并成一张）时，才需要在策略内部临时把代码整理成统一格式。示例见 [`examples/merge_forecast.py`](./examples/merge_forecast.py)。

---

## 5. 也可以返回 DataFrame

如果你更喜欢表格，也可以返回包含 `code` 和 `score` 两列的 DataFrame：

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    score = -today["dretwd"]
    return pd.DataFrame({"code": today["stkcd"], "score": score})
```

DataFrame 更啰嗦一点，但适合你想在返回前检查中间列的时候使用。

如果你返回的 DataFrame 只有一列，平台会把 index 当作股票代码、该列当作 score：

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    score = -today["dretwd"]
    return pd.DataFrame({"score": score}).set_index(today["stkcd"])
```

---

## 6. score 怎样变成仓位

你不需要自己写仓位计算。平台会自动做：

1. 收集当天所有股票的 `score`。
2. 根据配置里的 `execution.long_only` 回测模式开关决定是多空还是只做多。
   - 多空模式：可以同时做多看好的股票、做空不看好的股票。
   - 只做多模式：只能买入看好的股票，不能做空。
3. 按 `top_k` / `long_only_target_count`（最多持有股票数）、杠杆上限 `max_leverage`、流动性限制计算目标仓位。
4. 下一个交易日用官方执行价 `front_vwap` 模拟成交。
5. 生成收益曲线、回撤、分组收益和排行榜指标。

也就是说，今天收盘后产生的 `score`，会在下一个交易日按 `front_vwap` 成交，而不是当天收盘后立即成交。

回测模式开关、`top_k`、`long_only_target_count`、`max_leverage`、`max_participation_rate` 这些参数是在平台配置里设置的，不是在 `generate_signals` 函数里写的。本地测试时可以通过 `config/platform.yaml` 或代码里的配置对象调整。具体含义可以参考 [回测与评价指标](./06-backtest-and-metrics.md) 和 [术语表](./glossary.md)。

所以策略文件里最重要的代码通常就是：

```python
score = ...
return pd.Series(score.values, index=...)
```

---

## 7. 交易限制由平台执行层处理

入门策略不需要手动写 `limitstatus != 0`。

平台回测会处理：

- 股票不可交易；
- 涨跌停导致买不进或卖不出；
- 成交金额太小导致不能建太大仓位；
- 价格或成交数据缺失。

如果你想在信号层更保守，也可以看 `docs/student/examples/limit_guard.py`，但那是进阶积木，不是第一天必写内容。

---

## 8. 常见错误

### 函数名写错

平台只找 `generate_signals`。写成 `generate_signal`、`GenerateSignals` 都不行。

### 返回了普通 list 或 dict

错误：

```python
return {"000001": 1.0}
```

正确：

```python
return pd.Series({"000001": 1.0})
```

### score 不是数字

错误信息：`StrategySignalError: signal scores must be numeric`

如果你把 `"高"`、`"1.2%"` 这种文本放进 score，平台会报错。注意：

- 显式返回 `NaN` 是允许的，它表示“这只股票今天没有信号”。
- `0` 是中性信号，不是“无信号”；它仍可能根据组合规则被持有。
- 只有无法被强制转换成数字的非空值（如字符串 `"高"`）才会触发这个错误。

读取平台数据时，优先在接口里写：

```python
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "dretwd"],
    numeric_columns=["dretwd"],
)
```

`numeric_columns` 会把指定列转成数字，转不了的值变成 `NaN`，从而避免非数字文本导致的报错。

### 同一只股票出现多次

同一天同一只股票只能有一个分数。如果你做了 merge 后出现重复股票，要先去重或聚合。

---

## 本章要点

- 最推荐的新手写法是返回 `pd.Series(score.values, index=stock_codes)`。
- 单参数 `generate_signals(data)` 仍然有效；平台会自动识别。
- 学生主要负责构造 `score`。
- `NaN` 是合法的无信号；`0` 是中性信号，不等于 `NaN`。
- 平台会自动整理股票代码、转换仓位、处理执行限制。
- 只有做多表合并时，才需要在策略内部临时统一股票代码。
- DataFrame 返回仍然支持，但不是第一天最简写法。

上一步：[DataFrame 字段速查](./dataframe-field-guide.md) | 下一步：[示例策略逐行讲解](./05-example-strategies-walkthrough.md)
