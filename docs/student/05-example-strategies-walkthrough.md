# 示例策略逐行讲解

`examples/strategies/` 下面的每个策略示例 `.py` 文件都是可以直接上传或复制修改的完整策略。它们的共同结构是：

```text
读数据 -> 算一个或多个因子 -> 合成 score -> 返回 Series
```

这些示例里用到了 `_zscore`，它是把不同因子的数值缩放到同一尺度的工具。例如市值可能是几千万，收益率只是 0.01，直接相加会让市值“欺负”收益率；先用 `_zscore` 转换后，两者才能公平比较。`_zscore` 的具体写法可以参考 [Cookbook](./10-cookbook.md) 的第 1 节。

这些示例文件都在 `examples/strategies/` 文件夹里，你可以用 VS Code / Cursor 打开对照。读示例时不要先背代码，先问自己一句话：**这个策略为什么给这只股票更高分？**

---

## 1. `price_volume_momentum.py`：价格动量

一句话：当天涨得多、成交更活跃的股票，分数更高。

核心代码：

```python
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "dretwd", "dnvaltrd"],
    numeric_columns=["dretwd", "dnvaltrd"],
)
day_return = today["dretwd"]
liquidity = np.log1p(today["dnvaltrd"])
score = _zscore(day_return) + 0.20 * _zscore(liquidity)
return pd.Series(score.values, index=today["stkcd"])
```

解释：

- `dretwd` 是当天日收益率，越高越偏动量。
- `dnvaltrd` 是成交金额，取 `log1p` 是为了压缩极端大成交额。
- `numeric_columns` 让平台把收益率和成交金额转成数字，异常文本或空值变成 `NaN`。
- `0.20` 表示成交活跃度只是辅助，不是主因子。

---

## 2. `short_term_reversal.py`：短期反转

一句话：当天跌得多的股票，分数更高。

核心代码：

```python
score = -1.00 * _zscore(day_return) + 0.15 * _zscore(liquidity)
```

解释：

- 负号表示“越低越好”。
- 当天收益低，`_zscore(day_return)` 也低；乘负号后分数变高。
- 这个策略和价格动量刚好方向相反。

---

## 3. `low_liquidity_premium.py`：低流动性溢价

一句话：成交金额越低，分数越高。

核心代码：

```python
liquidity = np.log1p(today["dnvaltrd"])
score = -1.00 * _zscore(liquidity)
```

解释：

- 成交金额越高，`liquidity` 越高。
- 前面加负号后，成交金额低的股票得到更高分。
- 真实交易里低流动性股票不一定容易成交，所以执行限制由平台回测层处理。

---

## 4. `small_cap_reversal.py`：小市值反转

一句话：小市值、当天跌、成交较低的股票，分数更高。

核心代码：

```python
score = (
    -0.65 * _zscore(market_cap)
    - 0.25 * _zscore(day_return)
    - 0.10 * _zscore(liquidity)
)
```

解释：

- 市值权重最大：`-0.65`。
- 短期反转其次：`-0.25`。
- 低流动性只给轻微权重：`-0.10`。
- 系数越大，表示这个因子在总分里越重要。

---

## 5. `forecast_revision_momentum.py`：业绩预告动量

一句话：已经公开的业绩预告越积极，分数越高。

它比前面几个复杂一点，因为它要把两张表合在一起：

1. `stock.daily_returns`：当天股票池和当天收益。
2. `BF_FORECAST`：截至当天已经公开的最新业绩预告。

关键接口：

```python
latest = data.latest("BF_FORECAST", by="Stkcd", columns=[...])
```

`latest` 会自动过滤未来公告，所以不会偷看未来。

这个文件里有 `_code_for_merge`，只是为了在 pandas merge 时让两张表的股票代码对齐。平台最终仍然会自动整理你返回的股票代码。

---

## 6. `macd_factor.py`：MACD 趋势

一句话：短期均线强于长期均线，并且趋势继续改善的股票，分数更高。

它用到了历史数据：

```python
history = data.history(
    "stock.daily_returns",
    lookback_days=90,
    columns=["stkcd", "trddt", "clsprc", "dnvaltrd"],
    numeric_columns=["clsprc", "dnvaltrd"],
)
```

解释：

- `data.history` 只读到当前日期，不会读未来。
- 每只股票单独按日期排序，计算 MACD 指标：
  - `EMA12`：过去 12 天的指数移动平均（短期趋势）。
  - `EMA26`：过去 26 天的指数移动平均（长期趋势）。
  - `DEA9`：MACD 的 9 天信号线，用来判断趋势是否继续改善。
- 历史价格不足时，策略给中性分 0，而不是硬算。

---

## 7. 怎么改这些示例

最推荐的改法是只改 `score = ...` 那一行。

### 改方向

动量：

```python
score = _zscore(day_return)
```

反转：

```python
score = -_zscore(day_return)
```

### 改权重

把成交活跃度从 20% 提到 50%：

```python
score = _zscore(day_return) + 0.50 * _zscore(liquidity)
```

### 加一个因子

先算新因子，再加到 score：

```python
score = old_score + 0.30 * _zscore(new_factor)
```

---

## 8. 重要提醒

这些示例是课堂例题，不是投资建议。它们的目标是教你：

- 怎样读取数据；
- 怎样把金融想法写成 `score`；
- 怎样把多个因子加权合成；
- 怎样避免偷看未来。

真正比赛时，关键不是把示例背下来，而是想清楚：**为什么这个 score 应该能区分好股票和坏股票？**

---

## 本章要点

- 简单策略通常只有几行核心代码。
- 最常见的返回方式是 `pd.Series(score.values, index=today["stkcd"])`。
- `_zscore` 用来把不同量纲的因子放到同一尺度。
- 多表策略才需要额外的 merge helper。
- 改策略时优先小步修改 `score` 的方向和权重。

上一步：[策略函数深入解析](./04-generate-signals-deep-dive.md) | 下一步：[回测与评价指标](./06-backtest-and-metrics.md)
