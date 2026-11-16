# 原始数据因子排序实验：从 raw data 到完整 longshort 权重

这一章是一节本地练习课。它不要求你先写 `generate_signals`，也不要求你马上上传策略。我们先离开平台 API，直接用 `pandas` 和 `numpy` 读取 `new_data/distribute` 里的原始分发数据，亲手完成一遍：

```text
读取原始数据 -> 计算因子 score -> 变成正负 weighted_score -> 打印 top/bottom 20
```

读完并跑通本章，你应该能做到三件事：

1. 从 `new_data/distribute` 找到日行情表和股票基本信息表。
2. 用 `pandas` / `numpy` 算出自己的横截面因子 `score`。
3. 自己实现完整的 longshort `weighted_score` 列表：有正数、有负数，并停在 VWAP 执行之前。

> 这章的脚本是研究练习脚本，不是上传到网页端的策略文件。网页端正式提交仍然要写 `generate_signals(data, date)`，后面会讲怎么迁移。

---

## Goal 1：先把一天的股票截面读出来

我们先从两张最基础的原始表开始：

| 原始文件                                              | 用途                  |
| ------------------------------------------------- | ------------------- |
| `new_data/distribute/stock/daily_returns.parquet` | 个股日行情、收益率、成交额、涨跌停状态 |
| `new_data/distribute/basic/company_info.csv`      | 股票简称、公司名、行业、省市等基本信息 |

如果你用的是学生下载包，里面可能没有完整的 `new_data`，但会有学习数据：

```text
data_releases/learning/distribute/stock/daily_returns.parquet
data_releases/learning/distribute/basic/company_info.csv
```

本章脚本会优先读取 `new_data/distribute`；如果找不到，就自动改读 `data_releases/learning/distribute`。

日行情表里最常用的列包括：

| 列名 | 含义 |
|---|---|
| `stkcd` | 股票代码 |
| `trddt` | 交易日 |
| `opnprc` | 开盘价 |
| `clsprc` | 收盘价 |
| `dnshrtrd` | 成交股数 |
| `dnvaltrd` | 成交金额 |
| `dretwd` | 考虑现金红利再投资的日收益率 |
| `markettype` | 市场类型 |
| `limitstatus` | 涨跌停/交易限制状态 |

练习脚本在这里：

```text
docs/student/examples/raw_factor_ranking_top_bottom.py
```

运行：

```bash
conda activate QuantFish
python docs/student/examples/raw_factor_ranking_top_bottom.py
```

默认情况下，脚本会自动选择可用日行情表里最新的交易日，并只保留 `markettype` 为 `1,4` 的股票。这个范围和当前平台默认主板 A 股范围一致。脚本还会把完整的权重列表保存到：

```text
output/raw_factor_weighted_scores.csv
```

如果你想指定保存位置：

```bash
python docs/student/examples/raw_factor_ranking_top_bottom.py --output output/my_weights.csv
```

如果你想看所有市场，可以运行：

```bash
python docs/student/examples/raw_factor_ranking_top_bottom.py --market-types all
```

如果你想指定某一天：

```bash
python docs/student/examples/raw_factor_ranking_top_bottom.py --date 2026-05-29
```

这一关要理解的是：**股票排序永远先从某一天的一张截面表开始。** 这一天有很多只股票，每一行是一只股票，我们要给每一行算一个分数。

---

## Goal 2：用 pandas / numpy 算自己的因子 score

脚本里的教学因子不是投资建议，只是为了展示完整流程。它用了三个直觉：

1. `raw_vwap = dnvaltrd / dnshrtrd`
   用成交金额除以成交股数，得到当天成交均价。
2. `vwap_close_gap = raw_vwap / clsprc - 1`
   如果 VWAP 高于收盘价，说明收盘价低于全天成交均价；这个例子把它当作一个短期反转候选信号。
3. `liquidity_log = np.log1p(dnvaltrd)`
   成交额越高，流动性越好。用 `log1p` 是为了压缩极端大成交额。

核心代码长这样：

```python
rows["raw_vwap"] = rows["dnvaltrd"] / rows["dnshrtrd"]
rows["vwap_close_gap"] = rows["raw_vwap"] / rows["clsprc"] - 1.0
rows["intraday_return"] = rows["clsprc"] / rows["opnprc"] - 1.0
rows["liquidity_log"] = np.log1p(rows["dnvaltrd"])

rows["score"] = (
    zscore(rows["vwap_close_gap"])
    + 0.20 * zscore(rows["liquidity_log"])
    - 0.10 * zscore(rows["intraday_return"].abs())
)
```

这里有一个非常重要的技巧：`zscore(...)`。

不同因子的数值范围不一样。收益率可能是 `-0.10` 到 `0.10`，成交额可能是几百万到几十亿。如果直接相加，成交额会把其他因子“压扁”。所以我们先做横截面标准化：

```text
zscore = (value - mean(value)) / std(value)
```

它的意思是：这只股票的某个指标，比当天所有股票平均水平高/低多少个标准差。

这一关要理解的是：**因子不是神秘公式，它就是一列数字。** 你可以用价格、成交额、收益率、财报字段、公告字段组合出自己的 `score`。

---

## Goal 3：从 score 算出完整 weighted_score 列表

有了 `score` 之后，我们不要只停在 top 20 / bottom 20。真正的 longshort 排序系统需要给**当天所有有效股票**都算一个最终权重。这个权重在脚本里叫 `weighted_score`。

它不是原始因子分数，而是已经归一化后的多空目标权重：

```python
centered_score = score - score.mean()
abs_centered_score = centered_score.abs()
weighted_score = centered_score / abs_centered_score.sum()
```

这里每一列的含义是：

| 列名                   | 含义                                             |
| -------------------- | ---------------------------------------------- |
| `score`              | 你自己设计的原始因子分数                                   |
| `centered_score`     | 原始分数减去当天平均分                                    |
| `abs_centered_score` | `centered_score` 的绝对值，用来计算总强度                  |
| `weighted_score`     | 最终多空权重；正数偏做多，负数偏做空                             |
| `side`               | 根据 `weighted_score` 标记 `long`、`short` 或 `flat` |

脚本里的实现是：

```python
weights = longshort_weight_table(rows["score"])
rows["centered_score"] = weights["centered_score"]
rows["abs_centered_score"] = weights["abs_centered_score"]
rows["weighted_score"] = weights["weighted_score"]
```

而 `longshort_weight_table(...)` 的核心就是：

```python
centered = score - score.mean(skipna=True)
gross = centered.abs().sum(skipna=True)
weighted = centered / gross
```

这个公式会自然产生一整列正负权重：

- `weighted_score > 0`：这只股票在多头侧。
- `weighted_score < 0`：这只股票在空头侧。
- `weighted_score = 0`：这只股票接近中性。

如果所有股票都有有效分数，一般会看到：

```text
sum(positive weighted_score) ≈ +0.5
sum(negative weighted_score) ≈ -0.5
sum(abs(weighted_score))     ≈  1.0
```

这就是完整的多空仓位表。它已经回答了“每只股票在组合里应该占多少权重”。

### 这一章停在哪里

本章停在 `weighted_score`。也就是说，我们还没有进入成交层：

```text
code + score + weighted_score
```

到这里为止，还没有计算：

- 买卖多少股；
- 用多少钱成交；
- VWAP 成交价；
- 今日 VWAP 到今日收盘的收益；
- 交易成本和涨跌停限制。

如果后面要模拟真实成交，才会把这个权重和今天的 VWAP、资金规模、交易限制放在一起。当前这节课先不要跨过去，否则学生会把“排序系统”和“成交系统”混在一起。

### top/bottom 20 只是展示窗口

完整列表会保存到 CSV，top/bottom 20 只是终端里方便观察的窗口。脚本会打印两张表：

- `Top 20`：分数最高的 20 只股票，也就是多头候选。
- `Bottom 20`：分数最低的 20 只股票，也就是空头候选。

完整 CSV 里会有所有股票，例如：

```text
rank, code, 股票简称, 行业, score, centered_score, weighted_score, raw_vwap, clsprc, ...
```

你可以这样读这张表：

| 情况 | 在 longshort 里意味着什么 |
|---|---|
| `score` 高于当天平均分 | `weighted_score` 为正，偏做多 |
| `score` 低于当天平均分 | `weighted_score` 为负，偏做空 |
| `score` 接近当天平均分 | `weighted_score` 接近 0 |

这就是平台里“给股票打分 -> 排序 -> 高分做多、低分做空”的核心直觉。

---

## 把这个练习迁移回平台策略

上面的脚本直接读取 `new_data/distribute`，适合本地研究和课堂演示。正式上传到 QuantFish 平台时，不要在策略文件里直接读本地路径，而要用平台提供的 `data.current(...)`。

同一个因子思路可以改成这样：

```python
import numpy as np
import pandas as pd


def zscore(values):
    numeric = pd.Series(values, copy=False).replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "opnprc", "clsprc", "dnshrtrd", "dnvaltrd"],
        numeric_columns=["opnprc", "clsprc", "dnshrtrd", "dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype="float64")

    raw_vwap = today["dnvaltrd"] / today["dnshrtrd"]
    vwap_close_gap = raw_vwap / today["clsprc"] - 1.0
    intraday_return = today["clsprc"] / today["opnprc"] - 1.0
    liquidity_log = np.log1p(today["dnvaltrd"])

    score = (
        zscore(vwap_close_gap)
        + 0.20 * zscore(liquidity_log)
        - 0.10 * zscore(intraday_return.abs())
    )
    return pd.Series(score.values, index=today["stkcd"])
```

这个版本才是可以放进 `strategy.py` 的形状。你仍然只返回 `score`，平台会继续负责：

- 整理股票代码；
- 处理 `NaN` / 无穷值；
- 把 `score` 转成 longshort 权重；
- 用 VWAP / 收盘价模拟成交和结算；
- 计算收益、Sharpe、回撤和排行榜分数。

换句话说：

- 在本章研究脚本里，你可以自己算 `weighted_score`，用来理解 longshort 排序系统。
- 在正式平台提交里，你仍然只返回 `score`，不要返回 `weighted_score`。

---

## 你可以继续改什么

先不要急着写很复杂的模型。建议按这个顺序改：

1. 只改 `score` 方向：把 `+ zscore(vwap_close_gap)` 改成 `- zscore(vwap_close_gap)`，观察 top/bottom 是否反过来。
2. 只改权重：把 `0.20` 或 `0.10` 改大/改小，观察排名变化。
3. 加一个新因子：例如用 `dretwd` 做短期反转，或用 `dsmvosd` 做市值风格。
4. 再迁移到 `generate_signals`，跑一次本地学习数据回测。

最重要的是每次只改一个地方。这样你才知道排名变化是哪个想法带来的。
