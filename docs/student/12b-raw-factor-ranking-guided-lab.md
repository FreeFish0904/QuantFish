# 原始数据因子排序引导练习：补全 longshort 权重

这是一份**引导版**练习。它不会直接给出完整答案，而是通过一系列问题，带你一步步搭建出一个因子排序系统。

本练习的终极目标，不是立即做回测，也不是立刻用 VWAP 去成交。而是先得到一张完整的表：

```text
每只股票一行
包含 code / 股票基本信息 / score / centered_score / weighted_score
weighted_score 有正有负
```

这张表就是longshort 排序系统应当输出的结果。


---

## 练习规则

每完成一小步，都请打印结果查看。不要一开始就把整段逻辑写在一个长脚本里。

每一步都要问自己三个问题：

1. 当前这张表有多少行？
2. 新增的列中有没有 `NaN` 或无穷值？
3. 这列数字的方向是否符合我的投资直觉？

你可以新建一个临时文件来练习，例如：

```text
scratch/raw_factor_guided.py
```

这个文件不需要上传到平台，只作为本地练习草稿使用。

---

## Goal 1：先拿到“一天的股票列表”

先不要急着计算因子，先回答几个问题：

- 你准备研究哪一天？
- 那一天一共有多少只股票？
- 每只股票的代码、收盘价、成交额是否都能正常读取？

如果你使用的是学生下载包，可以尝试读取以下文件：

```text
data_releases/learning/distribute/stock/daily_returns.parquet
data_releases/learning/distribute/basic/company_info.csv
```

先写一段最小读取代码：

```python
from pathlib import Path

import pandas as pd


daily_path = Path("___/stock/daily_returns.parquet")

columns = [
    "stkcd",
    "trddt",
    "opnprc",
    "clsprc",
    "dnshrtrd",
    "dnvaltrd",
    "dretwd",
    "markettype",
    "limitstatus",
]

target_date = pd.Timestamp("____-__-__")

daily = pd.read_parquet(
    daily_path,
    columns=columns,
    filters=[("trddt", "=", target_date)],
)

print(daily.head())
print("rows:", len(daily))
```

### 请自行检查

1. `stkcd` 是不是股票代码？
2. `trddt` 是否都等于你选定的日期？
3. `dnshrtrd` 和 `dnvaltrd` 中是否存在 0 或缺失值？
4. `markettype` 有哪些取值？你准备保留哪些市场？

提示：当前平台默认主板 A 股范围常用 `markettype` 为 `1,4`。不过本次练习是否采用这一筛选条件，由你自己决定。

---

## Goal 2：设计自己的 score，而不是直接套用公式

现在需要为每只股票打一个原始分数 `score`。

先不要写代码，先用一句话概括你的因子直觉：

```text
我认为 ________ 的股票，明天更可能表现更好，所以它们应该有更高的 score。
```

例如：

- 如果你相信短期反转：今天跌幅较大的股票，明天可能反弹。
- 如果你相信趋势延续：今天涨势较强的股票，明天可能继续走强。
- 如果你重视流动性：成交额过小的股票可能不适合参与排序。
- 如果你关注 VWAP：收盘价相对全天成交均价的位置可能包含信息。

### 小片段 1：先构造可能需要的中间列

不要急着合成 `score`，先把中间变量算出来：

```python
rows = daily.copy()

numeric_cols = ["opnprc", "clsprc", "dnshrtrd", "dnvaltrd", "dretwd"]
for col in numeric_cols:
    rows[col] = pd.to_numeric(rows[col], errors="coerce")

rows["raw_vwap"] = rows["______"] / rows["______"]
rows["intraday_return"] = rows["______"] / rows["______"] - 1.0

print(rows[["stkcd", "clsprc", "raw_vwap", "intraday_return"]].head())
```

思考：

- `raw_vwap` 应该用哪两个字段相除？
- 日内收益应该是收盘价除以什么价格？
- 分母为 0 时会发生什么？

### 小片段 2：把不同量纲放到同一尺度

如果一个因子是收益率，另一个因子是成交额，它们不能直接相加。你需要先做横截面标准化。

下面这个函数已经写了一半，请补全关键位置：

```python
import numpy as np
import pandas as pd


def zscore(values):
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)

    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0

    return (numeric - ________) / ________
```

思考：

- 横截面平均值应该用什么函数计算？
- 横截面标准差应该用哪个变量？
- 为什么最后可能还需要处理缺失值？

### 小片段 3：合成你自己的 score

这里不要照搬别人的权重。先明确你的方向：

```python
signal_1 = zscore(rows["________"])
signal_2 = zscore(rows["________"])

rows["score"] = (
    ___ * signal_1
    + ___ * signal_2
)

print(rows[["stkcd", "score"]].sort_values("score", ascending=False).head(10))
print(rows[["stkcd", "score"]].sort_values("score", ascending=True).head(10))
```

检查问题：

1. 分数最高的股票，是否真的符合你的直觉？
2. 分数最低的股票，是否真的应该排在后面？
3. 如果方向反了，你应该调整哪一个符号？

---

## Goal 3：把 score 转换成一列有正有负的 weighted_score

现在你已经有了 `score`。但 longshort 系统还需要回答一个更具体的问题：

```text
每只股票应该占组合多少权重？
```

这里先不考虑 VWAP、股数、资金等约束，只完成排序系统自身的最后一步。

### 先用语言解释

请先填空：

```text
如果某只股票的 score 高于当天平均 score，
它的 centered_score 应该是 ________ 数，
所以 weighted_score 应该偏 ________。

如果某只股票的 score 低于当天平均 score，
它的 centered_score 应该是 ________ 数，
所以 weighted_score 应该偏 ________。
```

### 小片段 4：先算去均值分数

```python
score = rows["score"]

score_mean = score.________(skipna=True)
rows["centered_score"] = score - score_mean

print(rows[["stkcd", "score", "centered_score"]].head())
```

检查问题：

1. `centered_score` 是否有正有负？
2. 原始 `score` 最高的股票，`centered_score` 是否通常也为正？
3. 如果所有 `centered_score` 都是 0，说明什么？

### 小片段 5：把强弱归一化为权重

现在要让所有股票的权重加在一起具有可比性。思路是：

```text
每只股票的最终权重 = 它距离平均分的距离 / 全市场总距离
```

请补全下面这段代码：

```python
rows["abs_centered_score"] = rows["centered_score"].______()

gross = rows["abs_centered_score"].sum(skipna=True)
rows["weighted_score"] = rows["centered_score"] / gross

rows["side"] = "flat"
rows.loc[rows["weighted_score"] > 0, "side"] = "long"
rows.loc[rows["weighted_score"] < 0, "side"] = "short"
```

检查问题：

1. `weighted_score` 有没有正数？
2. `weighted_score` 有没有负数？
3. 正数是否对应 `side = long`？
4. 负数是否对应 `side = short`？

### 小片段 6：检查你的权重表是否合理

不要凭感觉说“应该对了”，用代码来验证：

```python
weights = rows["weighted_score"].fillna(0.0)

print("long sum:", weights[weights > 0].sum())
print("short sum:", weights[weights < 0].sum())
print("gross:", weights.abs().sum())
print("long count:", (weights > 0).sum())
print("short count:", (weights < 0).sum())
```

你期望看到的结果是：

- `long sum` 为正数；
- `short sum` 为负数；
- `gross` 接近 1；
- `long count` 和 `short count` 都大于 0。

如果结果不是这样，先不要继续，回头检查：

- `score` 是否全部相同；
- `score` 是否全部缺失；
- `gross` 是否为 0；
- 是否在除法前处理了异常值。

---

## Goal 4：打印 top 20 / bottom 20，但不要只看它们

top 20 和 bottom 20 只是给人看的窗口，并不代表完整组合。

你可以这样打印：

```python
display_cols = [
    "stkcd",
    "side",
    "score",
    "centered_score",
    "weighted_score",
    "raw_vwap",
    "clsprc",
]

top20 = rows.sort_values("score", ascending=False).head(20)
bottom20 = rows.sort_values("score", ascending=True).head(20)

print(top20[display_cols])
print(bottom20[display_cols])
```

思考：

1. top 20 的 `weighted_score` 是否基本为正？
2. bottom 20 的 `weighted_score` 是否基本为负？
3. 有没有股票分数很高，但数据看起来异常？为什么？

如果你想把股票简称、行业、省市等信息也合并进来，先想清楚几个问题：

- 基本信息表中的股票代码列叫什么名字？
- 日行情表中的股票代码列叫什么名字？
- 两边的代码格式是否都是 6 位？

给你一个方向，但不给完整答案：

```python
company = pd.read_csv("___/basic/company_info.csv")

company["code"] = company["stkcd"].astype(str).str.zfill(6).str[-6:]
rows["code"] = rows["stkcd"].astype(str).str.zfill(6).str[-6:]

merged = rows.merge(
    company[["code", "stknme", "indnme", "province", "city"]],
    on="code",
    how="left",
)
```

---

## 最重要的边界：这里还没有乘以 VWAP

本练习到此为止：

```text
score -> centered_score -> weighted_score
```

还没有进入以下环节：

- `weighted_score * capital`；
- 用 VWAP 计算可以买/卖多少股；
- 交易成本；
- 涨跌停无法成交；
- 今日 VWAP 到今日收盘的收益。

你现在完成的是**排序系统**，不是完整的回测系统。

先把排序系统做清楚，再进入成交系统。这样以后调试策略时，你才能知道问题出在哪里：

- 如果 top/bottom 不符合直觉，问题在 `score`；
- 如果正负权重不对，问题在 `weighted_score`；
- 如果权重正确但收益不对，再去看 VWAP、成交限制和回测引擎。

---

## 提交前自查清单

完成练习后，请回答以下问题：

1. 我用了哪一天的数据？
2. 我保留了哪些 `markettype`？
3. 我的 `score` 越高代表什么？
4. 我的 `centered_score` 为什么会有正有负？
5. 我的 `weighted_score` 的正数总和、负数总和、绝对值总和分别是多少？
6. 我的 top 20 和 bottom 20 是否符合我的因子逻辑？
7. 我有没有不小心进入“乘以 VWAP 成交”的阶段？

如果这 7 个问题你都能说清楚，那么你已经完成了从原始数据到 longshort 排序权重的核心训练。
