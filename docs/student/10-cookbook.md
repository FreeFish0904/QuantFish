# Cookbook：像拼积木一样写策略

本章提供一组可以直接复制粘贴的代码片段。你不需要从头写每一行，只要像拼积木一样，把需要的片段组合进你的策略函数 `generate_signals` 里即可。

> 术语提醒：`generate_signals` 就是**策略函数**，平台会在每个交易日调用它，用来生成当天每只股票的信号分数。

---

## 1. 截面 z-score 标准化

这里的“截面”指的是“同一天的所有股票”。

### 为什么要标准化？

不同因子的数值范围往往不一样。例如：

- 市值可能是几千万到几千亿；
- 日收益可能是 -0.1 到 0.1；
- 成交金额可能是几十万到几十亿。

如果你直接把它们相加，数值大的因子会“欺负”数值小的因子。所以我们需要把它们放到同一个尺度上，这就是**标准化**。

**z-score** 是最常用的标准化方法。它的含义是：

> 某个值距离当天所有股票平均值有多少个标准差。

例如，某只股票的市值 z-score 是 2，说明它的市值比当天平均水平高很多；如果是 -1，说明它比平均水平低一些。

### 代码：`zscore_helper.py`

网页提交通常只上传一个 `.py` 策略文件。最稳妥的做法是把需要的 helper 函数直接复制到你的 `strategy.py` 里。`docs/student/examples/zscore_helper.py` 可以作为参考文件，不建议新手在提交文件里跨文件 import。

```python
import numpy as np
import pandas as pd


def zscore(values):
    """
    对一组数值做横截面 z-score 标准化。

    参数 values：一个 pandas Series，通常代表某一天所有股票在某个因子上的原始值。
    返回值：每个值距离当天平均值有多少个标准差；缺失值填 0。
    """
    # 如果 values 来自平台数据，读取时请先用 numeric_columns=[...]。
    # 这里主要处理无穷大，避免它影响平均值和标准差。
    numeric = pd.Series(values, copy=False).replace([np.inf, -np.inf], np.nan)
    # 计算标准差，衡量当天这些值分散程度。
    spread = numeric.std(skipna=True)
    # 如果标准差不存在或为 0，说明所有值一样或全部缺失，标准化后全给 0。
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    # 用 (值 - 平均值) / 标准差 得到 z-score，缺失值填 0。
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
```

**这行在做什么**：如果数据来自 `data.current/history/latest/load`，先在读取时写 `numeric_columns=[...]`，平台会把异常文本和空值变成 `NaN`（缺失值）。`zscore` 再计算平均值和标准差，最后得到每个值的标准分。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    rows = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "day_return": current["dretwd"],
    })
    # 当天跌得越多，反转分越高。
    rows["score"] = -zscore(rows["day_return"])
    return rows.loc[:, ["code", "score"]]
```

**这行在做什么**：先读取当天所有股票的日收益，做成只有 `code` 和 `day_return` 两列的表，然后用 `zscore` 把日收益标准化，最后取负号得到反转信号。

---

## 2. 涨跌停 / 交易受限过滤

有些股票当天涨停或跌停，第二天可能无法按理想价格成交。所以通常要把这些股票的信号分数设成 0，表示“今天不交易它”。

日行情数据集里的 `limitstatus` 字段就是用来判断这个的：`limitstatus` 非 0 通常表示当天交易受限。

### 代码：`limit_guard.py`

```python
import pandas as pd


def drop_blocked_scores(scores, daily_df, limit_col_candidates=None):
    """
    根据 daily_df 里的 limitstatus 列，把受限股票的 score 设为 0。

    参数 scores：DataFrame，必须包含 code 和 score 两列。
    参数 daily_df：DataFrame，通常来自 data.current(..., numeric_columns=["limitstatus"])。
    参数 limit_col_candidates：候选列名列表，兼容不同数据版本。
    返回值：新的 DataFrame，code 和 score 两列，受限股票的 score 为 0。
    """
    if limit_col_candidates is None:
        limit_col_candidates = ["limitstatus", "LimitStatus", "limit_status"]
    # 找一个存在的限制交易列名。
    limit_col = _optional_column(daily_df, limit_col_candidates)
    if limit_col is None:
        # 没有这一列就直接原样返回。
        return scores.copy()
    # limitstatus 非 0 表示当天交易受限（如涨跌停）。
    blocked = daily_df[limit_col].ne(0)
    result = scores.copy()
    result.loc[blocked.to_numpy(), "score"] = 0.0
    return result


def _optional_column(frame, candidates):
    """从候选列名里找一个存在的；找不到返回 None。"""
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    folded = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    return None
```

**这行在做什么**：`drop_blocked_scores` 先尝试找到 `limitstatus` 列；找到了就把对应行标记为 `blocked`，最后把这些行的 `score` 改成 0。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "limitstatus"],
        numeric_columns=["dretwd", "limitstatus"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    rows = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "score": -current["dretwd"],
    })
    # 把涨跌停股票的分数清零。
    rows = drop_blocked_scores(rows, current)
    return rows.loc[:, ["code", "score"]]
```

**这行在做什么**：生成原始分数后，调用 `drop_blocked_scores` 把当天不能交易的股票分数设为 0，避免策略去追涨停或卖跌停。

---

## 3. 读取最新业绩预告并和日行情合并

业绩预告（forecast）是公司在正式财报发布前给出的利润预告。它通常包含净利润增速的上下限，是很好的基本面信号来源。

平台里的 `BF_FORECAST` 数据集保存了这些预告。因为要防止偷看未来，所以要用 `data.latest` 来读取：**每只股票在当前交易日及之前最新发布的那一条预告**。

### 代码：`merge_forecast.py`

```python
import pandas as pd


def merge_latest_forecast(data, daily_df):
    """
    读取 BF_FORECAST 中每只股票截至当前交易日的最新预告，
    并返回包含 code 和 forecast_score 两列的 DataFrame。
    没有预告的股票 forecast_score 为 0。

    参数 data：平台提供的数据视图（StudentDataView），也就是 generate_signals 里的 data 参数。
    参数 daily_df：当天日行情 DataFrame，用来确定股票池。
    """
    if daily_df.empty:
        return pd.DataFrame({"code": [], "forecast_score": []})

    symbol_col = _column(daily_df, ["stkcd", "Symbol", "symbol"])
    base = pd.DataFrame({"code": daily_df[symbol_col].map(_normalize_code)})

    try:
        # latest 会自动过滤掉当前交易日之后的预告，防止偷看未来。
        latest = data.latest(
            "BF_FORECAST",
            by="Stkcd",
            columns=[
                "Stkcd",
                "RatNetProfPareComp_Hig",
                "RatNetProfPareComp_Low",
            ],
            numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
        )
    except KeyError:
        # 如果数据集中没有这张表，就给所有股票 0 分，策略仍可运行。
        return base.assign(forecast_score=0.0)

    if latest.empty:
        return base.assign(forecast_score=0.0)

    code_col = _column(latest, ["Stkcd", "stkcd", "Symbol", "symbol"])
    high_col = _optional_column(latest, ["RatNetProfPareComp_Hig"])
    low_col = _optional_column(latest, ["RatNetProfPareComp_Low"])

    score = pd.Series(0.0, index=latest.index)
    if high_col is not None and low_col is not None:
        # latest 已经通过 numeric_columns 把上下限转成数字，异常值是 NaN。
        high = latest[high_col]
        low = latest[low_col]
        # 取上下限平均值，并截断极端值，防止异常数字支配结果。
        growth = ((high + low) / 2.0).clip(lower=-100.0, upper=200.0) / 100.0
        score = score + growth.fillna(0.0)

    forecast = pd.DataFrame({
        "code": latest[code_col].map(_normalize_code),
        "forecast_score": score,
    })
    # 同一股票如果仍有多条记录，保留最后一条。
    forecast = forecast.groupby("code", as_index=False)["forecast_score"].last()

    merged = base.merge(forecast, on="code", how="left")
    merged["forecast_score"] = merged["forecast_score"].fillna(0.0)
    return merged


def _column(frame, candidates):
    """必须存在的列：找不到就抛错，帮助尽早定位字段问题。"""
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    folded = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    raise KeyError(f"missing required column from {candidates}")


def _optional_column(frame, candidates):
    """可选列：找不到返回 None。"""
    try:
        return _column(frame, candidates)
    except KeyError:
        return None


def _normalize_code(value):
    """把股票代码统一成 6 位字符串。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]
```

**这行在做什么**：`merge_latest_forecast` 先以当天日行情为股票池，再用 `data.latest` 获取每只股票最新预告，计算预告净利润增速的平均值作为 `forecast_score`，最后左连接回股票池，没有预告的股票给 0 分。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    # 获取基本面分数。
    forecast = merge_latest_forecast(data, current)

    # 获取市场面分数（这里用短期反转）。
    market = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "market_score": -zscore(current["dretwd"]),
    })

    # 合并两个因子，等权相加。
    combined = forecast.merge(market, on="code", how="left")
    combined["market_score"] = combined["market_score"].fillna(0.0)
    combined["score"] = zscore(combined["forecast_score"]) + zscore(combined["market_score"])
    return combined.loc[:, ["code", "score"]]
```

**这行在做什么**：把业绩预告分数和市场反转分数合并，每个因子先标准化再加起来。这样两个因子即使原始数值范围不同，也不会互相“欺负”。

---

## 4. 多因子等权合成

很多策略不是只看一个信号，而是把多个信号合在一起看。最常见的合成方式是**等权合成**：每个因子先标准化，然后直接相加。

```python
import pandas as pd


def equal_weight_score(*factors):
    """
    把多个 z-score 因子等权相加，再对总分做一次标准化。

    参数 factors：若干个 pandas Series，每个 Series 是一只因子在某天的值。
    返回值：标准化后的总分数 Series。
    """
    if not factors:
        # 如果没有传入任何因子，返回空 Series。
        return pd.Series(dtype=float)
    total = pd.Series(0.0, index=factors[0].index)
    for factor in factors:
        total = total + zscore(factor)
    return zscore(total)
```

**这行在做什么**：`def equal_weight_score(*factors)` 中的 `*factors` 表示可以传入任意多个因子；函数内部对每个因子先做 `zscore` 标准化，然后全部相加得到总分，最后对总分再做一次 `zscore`，保证输出分数的尺度稳定。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd", "dsmvosd", "limitstatus"],
        numeric_columns=["dretwd", "dnvaltrd", "dsmvosd", "limitstatus"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    rows = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "day_return": current["dretwd"],
        "amount": current["dnvaltrd"],
        "market_cap": current["dsmvosd"],
    })

    # 三个因子：小市值、低流动性、短期反转。
    rows["score"] = equal_weight_score(
        -rows["market_cap"],   # 市值越小越好
        -rows["amount"],       # 成交额越小越好
        -rows["day_return"],   # 当天跌得越多越好
    )
    return rows.loc[:, ["code", "score"]]
```

**这行在做什么**：读取三个不同因子的原始值，用 `equal_weight_score` 做等权合成。每个因子前面加减号表示方向：负号表示“越小越好”。

---

## 5. 处理缺失列的稳健写法

不同数据版本里，列名可能略有不同。例如股票代码列有时是 `stkcd`，有时是 `Symbol`。如果你直接写 `df["stkcd"]`，一旦列名变了就会报错。

写一个 `_column(candidates)` 函数，优先使用存在的列名：

```python
def _column(frame, candidates):
    """
    从候选列名里找一个真实存在的列名。

    参数 frame：DataFrame。
    参数 candidates：候选列名列表，按优先级排列。
    返回值：第一个存在的列名。
    如果都没有，抛出 KeyError。
    """
    # 先精确匹配。
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    # 再忽略大小写匹配一次。
    folded = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    raise KeyError(f"missing required column from {candidates}")
```

**这行在做什么**：`_column` 先在 DataFrame 里精确查找候选列名；找不到再试试小写版本。这样可以兼容不同数据发布版本的列名差异。

如果某个列不是必须的，可以再加一个 `_optional_column`：

```python
def _optional_column(frame, candidates):
    """可选列：找不到返回 None，不抛错。"""
    try:
        return _column(frame, candidates)
    except KeyError:
        return None
```

**这行在做什么**：`_optional_column` 把 `_column` 包在 `try/except` 里，找不到列时返回 `None`，让主逻辑自己决定怎么处理。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    # 兼容不同版本中的股票代码列名。
    symbol_col = _column(current, ["stkcd", "Symbol", "symbol"])
    return_col = _column(current, ["dretwd", "Dretwd", "return"])

    rows = pd.DataFrame({
        "code": current[symbol_col].astype(str).str.zfill(6).str[-6:],
        "score": -current[return_col],
    })
    return rows
```

**这行在做什么**：用 `_column` 自动选择当前数据表里实际存在的列名，这样即使不同数据版本列名不同，策略也能跑。

---

## 6. 在策略里加 `print` 调试

刚开始写策略时，你可能想知道程序跑到哪一步、某个变量里到底存了什么。这时可以在策略里加 `print`。

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    print("当前交易日:", date)
    print("当天行数:", len(current))
    print("前 5 行:")
    print(current.head())

    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    rows = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "score": -current["dretwd"],
    })
    print("输出信号前 5 行:")
    print(rows.head())
    return rows
```

**这行在做什么**：在关键步骤打印当前日期、数据行数、数据样本和输出结果，方便你在本地调试时检查逻辑是否正确。

### 注意

- `print` 在本地运行和网页提交时都可能输出大量日志。
- 提交到平台前，**请删除或注释掉所有 `print`**，避免超时或日志过大。
- 如果某个交易日数据为空，`print` 也能帮你快速定位问题。

---

## 7. 用 Series 返回最简信号

平台允许 `generate_signals` 返回三种格式。新手最推荐的是 Series：

```python
pd.Series(scores.values, index=codes)
```

Series 的 index 是股票代码，值是分数。平台会自动把它整理成内部需要的 `code` / `score` 表格。

```python
import pandas as pd


def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    scores = -current["dretwd"]
    return pd.Series(scores.values, index=current["stkcd"])
```

**这行在做什么**：`current["stkcd"]` 放在 Series 的 index 里，`scores.values` 放在值里。你不用手动补齐六位股票代码，平台会自动处理。

---

## 8. 构造只做多信号

平台用 `execution.long_only` 开关决定回测模式：`false` 是多空模式，`true` 是只做多模式。

- 在多空模式里，正分表示做多，负分表示做空。
- 在只做多模式里，你通常希望**只保留正分**的股票，负分股票直接给 0。

```python
def make_long_only(scores):
    """
    把分数中小于等于 0 的部分截断为 0，只保留看好的股票。

    参数 scores：包含 code 和 score 两列的 DataFrame。
    返回值：同样的 DataFrame，score 列里没有负数。
    """
    result = scores.copy()
    result["score"] = result["score"].clip(lower=0.0)
    return result
```

**这行在做什么**：`clip(lower=0.0)` 把 `score` 列里所有小于 0 的值都改成 0，只留下正分。

### 怎么用

```python
def generate_signals(data, date):
    current = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if current.empty:
        return pd.DataFrame({"code": [], "score": []})

    rows = pd.DataFrame({
        "code": current["stkcd"].astype(str).str.zfill(6).str[-6:],
        "score": -current["dretwd"],
    })

    # 只做多：负分股票不参与交易。
    rows = make_long_only(rows)
    return rows
```

**这行在做什么**：先生成一个多空都有的反转信号，然后用 `make_long_only` 把负分截断成 0，得到只做多信号。

---

## 小总结

| 需求 | 用哪个片段 |
|---|---|
| 让不同因子可比 | `zscore` |
| 避开涨跌停股票 | `drop_blocked_scores` |
| 加入业绩预告 | `merge_latest_forecast` |
| 多个因子合成 | `equal_weight_score` |
| 兼容不同列名 | `_column` / `_optional_column` |
| 本地调试 | `print`（提交前删除） |
| 最简 Series 返回 | `pd.Series(scores.values, index=codes)` |
| 只做多 | `make_long_only` |

网页提交通常只上传一个 `.py` 策略文件，所以建议把需要的函数复制到同一个 `strategy.py` 里。关键是像拼积木一样，把它们组合进你的 `generate_signals` 中。

---

## 本章要点

- 用 z-score 把不同量纲的因子放到同一尺度，才能公平相加。
- 用 `drop_blocked_scores` 把涨跌停或交易受限股票的分数清零。
- 用 `data.latest` 安全读取业绩预告等不定期发布的数据，避免偷看未来。
- 多因子常用等权合成；用 `_column` / `_optional_column` 兼容不同列名。
- 提交前删除调试 `print`，并优先用 Series 返回股票代码和分数。

相关代码示例：[zscore_helper.py](./examples/zscore_helper.py)、[limit_guard.py](./examples/limit_guard.py)、[merge_forecast.py](./examples/merge_forecast.py)

上一步：[常见错误](./09-common-errors.md) | 下一步：[术语表](./glossary.md)
