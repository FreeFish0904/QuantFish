# 回测与评价指标

到这一步，你已经写好了 `generate_signals`（策略函数），平台也知道每天该给每只股票打多少分。接下来平台要把这些分数变成“真的”买卖动作，并告诉你这个策略在历史上表现如何。这个过程就叫**回测**（backtest）。

读完本章，你会明白：

- 平台怎样把你的分数列表变成每日收益。
- `config/platform.yaml` 里哪些设置会影响你的成绩。
- `summary.csv`（回测结束后生成的 CSV 指标表）和 `graph_data.json`（给图表用的 JSON 数据文件）里的指标、图表分别是什么意思。

---

## 1. 从分数列表到每日收益

你可以把回测想象成一条流水线。你每天交给平台一组股票分数。最简写法是返回一个 Series：

```python
return pd.Series(score.values, index=today["stkcd"])
```

平台会把它整理成内部的两列表：

| code（六位股票代码） | score（信号分数） |
|---|---|
| 000001 | 1.2 |
| 000002 | -0.5 |

分数越高，表示策略当天越看好这只股票；分数越低或负数，表示越不看好。

平台拿到这张表后，会按下面的顺序处理：

```text
你的策略函数 generate_signals(data, date)
        ↓
返回一张包含 code 和 score 的表格
        ↓
平台把所有分数转换成“权重”（weight）
        ↓
第二天开盘用 front_vwap（官方执行价）模拟成交
        ↓
当天收盘用 front_close（官方收盘价/结算价）计算持仓市值
        ↓
扣除交易成本（手续费 + 滑点）
        ↓
得到这一天的组合收益
```

也就是说：**你今天给的分数，决定的是明天持有什么**；明天的价格波动，才产生今天的收益或亏损。

下面用 [`examples/hello_strategy.py`](./examples/hello_strategy.py) 做例子，它每天返回当天跌幅越大的股票分数越高（短期反转）。平台会在第二天按这些分数调仓，并观察后续表现。

---

## 2. 回测设置：`config/platform.yaml`

平台的行为由 `config/platform.yaml` 文件里的 `backtest` 和 `execution` 两段配置控制。你不需要修改它，但要读懂它，因为里面直接决定了你的成绩怎么算。

下面这段代码可以打印出配置文件里的关键字段，方便你查看：

```python
# 这里只是展示配置里的字段，不是要你改代码
import yaml

with open("config/platform.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

backtest = config["backtest"]
execution = config["execution"]

print("数据开始日期:", backtest["data_start"])
print("算分开始日期:", backtest["scoring_start"])
print("算分结束日期:", backtest["scoring_end"])
print("初始资金:", backtest["capital"])
print("回测模式:", "只做多" if execution.get("long_only") else "多空")
print("分组数量:", backtest["group_count"])
print("行业中性化:", backtest["industry_neutralization"])
print("手续费率:", execution["commission_rate"])
print("滑点率:", execution["slippage_rate"])
print("卖出印花税率:", execution["sell_stamp_duty_rate"])
print("A 股市场范围:", execution["allowed_market_types"])
if execution.get("long_only"):
    print("单票权重上限:", execution.get("max_position_weight"))
    print("最小上市天数:", execution.get("min_listing_days"))
```

**这行在做什么**：

- `yaml.safe_load` 把 YAML 配置文件读成 Python 字典，这样可以用 `config["backtest"]` 这种写法查看里面的值。
- 这段代码只是**读取并打印**配置，不会修改 `config/platform.yaml` 文件本身。
- 我们只看和学生成绩直接相关的字段，下一节逐个解释含义。

**运行这段代码前请确保：**

- 已经激活 `QuantFish` 环境。
- 当前目录是项目根目录（`config/platform.yaml` 就在当前目录下）。

下面是这些字段的具体含义：

| 字段 | 含义 | 例子 |
|---|---|---|
| `data_start` | 回测最早能用到的日期。平台会从这个日期开始加载行情，建立仓位。 | `2010-01-01` |
| `scoring_start` | 真正开始计算成绩的日期。在此之前只是“热身”。 | `2023-01-01` |
| `scoring_end` | 成绩计算的最后日期。 | `2025-12-31` |
| `capital` | 初始资金，单位是元。用于人民币图表和按成交额计算的流动性上限。 | `1000000` |
| `execution.long_only` | 回测模式开关。`false` 表示多空模式，可以同时做多和做空；`true` 表示只做多模式，只能买入股票。 | `true` |
| `execution.long_only_weighting` | 只做多模式的权重算法。`rank_equal` 表示入选且分数为正的股票等权，`score_proportional` 表示按正分比例分配；0 分和负分都不会买。 | `rank_equal` |
| `execution.long_only_target_count` | 只做多模式最多买入多少只股票，是硬上限；同分时按平台原始顺序先到先得。 | `50` |
| `execution.max_position_weight` | 只做多模式下单只股票的权重上限。例如 `0.05` 表示任何一只股票的权重最高为 5%。 | `0.05` |
| `execution.min_listing_days` | 只做多模式下，上市天数不足该值的股票会被排除在投资范围外。 | `60` |
| `group_count` | 分组数。平台会把股票按分数分成多少组，用来检查分数是否单调有效。 | `5` |
| `industry_neutralization` | 行业中性化开关。开启后，平台会在同一天、同一个行业内把每只股票的 `score` 减去该行业平均分，再把处理后的分数转成仓位；没有行业分类的股票分数会设为 `0`。 | `true` |
| `commission_rate` | 手续费率，按买卖换手率双边扣除。 | `0.0003` |
| `slippage_rate` | 滑点率，按买卖换手率双边扣除。 | `0.0005` |
| `sell_stamp_duty_rate` | A 股卖出印花税率，只对卖出换手率扣除。 | `0.0005` |
| `max_leverage` | 最大杠杆。`1.0` 表示总仓位不能超过初始资金。 | `1` |
| `top_k` | 多空模式每边最多选择多少只股票，是硬上限；`null` 表示不限制。 | `null` |
| `allowed_market_types` | 允许进入策略和回测的 CSMAR 市场类型。默认覆盖沪深主板、创业板、科创板和北交所 A 股。 | `[1, 4, 16, 32, 64]` |
| `max_participation_rate` | 单只股票单日最多成交其当天成交金额的多少比例，用来限制仓位变化量。 | `0.10` |
| `terminal_stale_position_policy` | 评分末日仍持有但没有有效收盘价的仓位如何处理。历史学习轨道固定使用 `carry`：沿用最后一个有效收盘价，不虚构平仓或成本，并记录诊断；`hidden_test` 继续使用严格的 `reject`。 | `reject`（基础配置；学习轨道运行时覆盖为 `carry`） |
| `submission_timeout_seconds` | 平台运行你策略的超时时间。当前默认配置为 1200 秒且开关打开，超过会报错。具体值以运行时的 `config/platform.yaml` 为准。 | `1200` |

> **注意**：当前默认配置中 `industry_neutralization` 为 `true`，也就是说平台默认会打开行业中性化。它会先把同一天、同一行业内每只股票的 `score` 减去该行业平均分，再转成仓位；没有行业分类的股票会被置为 `0` 分。如果你发现自己的多空敞口被“压平”了很多，可以先检查是不是这个开关在起作用。

### 只做多模式的可投资股票池

如果你开启 `execution.long_only`，平台还会先做一次**可投资股票池过滤**，再把你策略返回的分数转成仓位。这主要包括三条规则（源码见 `backend/src/quantfish/backtest/runner.py`）：

1. **只用信号日信息选股票**：信号日必须 `tradable == True`，`front_close`、`front_vwap` 和成交金额 `dnvaltrd` 都大于 0。平台不会偷看下一交易日的可交易状态来替换候选；下一日无法成交时由执行层保留现金或原仓位。
2. **上市时间过滤**：上市天数也按信号日计算。由 `execution.min_listing_days` 控制，默认 `60` 天。平台缺少 `basic.company_info` 或有效上市日期列时会直接拒绝回测；只有个别股票缺少上市日期时，这些股票会被排除并计入诊断信息。
3. **单票权重上限**：由 `execution.max_position_weight` 控制，默认 `0.05`。某只股票超限时，超出的权重会优先重新分配给其他已入选且仍有容量的股票；只有所有入选股票的总容量不足时才保留现金。

也就是说，只做多模式下的“入选”不是只看分数高低：股票还必须满足流动性、上市时间和单票权重限制。如果你发现持仓数量总是比 `long_only_target_count` 少，可以先检查是不是被这几条规则过滤掉了。

---

## 3. Warmup 期和 Scoring 期

回测会分成两段：

- **Warmup 期（热身期）**：从 `data_start` 到 `scoring_start` 之前。这段时间平台会正常买卖、建立仓位，但**不算成绩**。它的作用是让策略有时间“进入状态”，比如需要历史均值、滚动窗口的策略能积累足够的数据。
- **Scoring 期（评分期）**：从 `scoring_start` 到 `scoring_end`。这段时间的收益和指标才会进入 `summary.csv` 和排名。

打个比方：运动员比赛前有热身时间，热身时的表现不计入正式成绩；只有发令枪响之后才算。`scoring_start` 就是发令枪。

如果你的策略需要 60 天的历史数据，而 `data_start` 到 `scoring_start` 的时间不够长，策略在 warmup 期可能会因为数据不足而表现异常。

在当前的默认配置里：

- `data_start` 是 `2010-01-01`。
- `scoring_start` 是 `2023-01-01`。

中间隔了好多年，这段时间就是 Warmup 期，足够策略积累历史数据、进入状态。`summary.csv` 和 `graph_data.json` 里的所有指标只统计 Scoring 期，不会包含 Warmup 期。

在本地做 smoke test 时，你可能不想等好几年 warm-up。这时可以在代码里临时把 `data_start` 改到评分窗口前刚好够用的时间，例如只保留 `scoring_start` 前一两个月。注意：这只适合本地快速验证，正式提交时不要改动平台配置。

---

## 4. 流动性限制

真实市场里，一只股票一天的成交金额有限，你不可能想买多少就买多少。平台用下面的规则模拟这个限制：

```text
max_daily_change = max_participation_rate * dnvaltrd / capital
```

这个公式的意思是：

- `dnvaltrd` 是这只股票当天的成交金额（日价值交易额）。
- `capital` 是你的初始资金。
- `max_participation_rate` 是平台允许你一天最多参与该股票成交额的比例，默认 `0.10`，也就是最多用当天成交金额的 10% 来成交。
- 算出来的 `max_daily_change` 是这只股票当天允许增加或减少的最大仓位变化量。
- 如果你的目标调仓量超过这个比例，平台会按上限截断。

例如，你的初始资金是 100 万元，某只股票今天成交了 500 万元：

```text
0.10 × 5,000,000 / 1,000,000 = 0.5
```

这只股票当天最多只能增加或减少 50% 仓位。如果策略给出的调仓量更高，平台会自动压低到 50%。

这个限制会让高分的“小盘股”或“低流动性股票”不会被过度买入，避免回测结果过于乐观。流动性上限是**硬约束**：如果某只股票只能成交到一部分目标仓位，平台会保留这个较低仓位，不会为了凑满总敞口再把它或其他受限仓位放大。因此，策略在低流动性或交易受限的日子可能会低于满仓。

---

## 5. 涨跌停保护

A 股不同板块的涨跌停幅度不同。平台优先使用数据源给出的每日涨跌停状态或涨跌停价格；字段缺失时，才按板块和日期回退到约 10%、20% 或 30% 的阈值。如果目标方向无法成交，平台会跳过对应交易：

- 你想**买入**某只股票，但它当天已经**涨停**，平台不会买。
- 你想**卖出**某只股票，但它当天已经**跌停**，平台不会卖。

回退判断使用当天 `front_close` 相对前一有效 `front_close` 的变化，并结合 `market_type` 和交易日期选择板块阈值。

如果数据源面板里存在 `limitstatus` / `limit_status` 或官方涨跌停价格，平台优先相信这些每日字段：正向受限阻止买入，负向受限阻止卖出。

`trdsta` / `TradingStatus` 会保留在数据里，方便你自己分析交易状态，但平台执行层不会单独用它来禁止交易。实际能不能成交，取决于有效价格、成交金额/成交量、`limitstatus`/`limit_status` 和涨跌停阈值。

这项保护叫**涨跌停保护**。它避免你的策略在回测里“捡便宜”——比如假装能买到涨停股，这在真实市场里几乎不可能。

---

## 6. 分组收益：你的分数有没有说服力？

平台会把每一天的股票按分数排序，然后平均分成 `group_count` 组：

- `group_1`：分数最低的一组。
- `group_2`：分数次低的一组。
- …
- `group_N`：分数最高的一组。

然后分别计算每组的累计收益，并画成**分组累计收益**图。这里的收益是**可执行分组收益**：平台只统计下一交易日有有效 `front_close` / `front_vwap`、可交易且未按官方字段或板块回退规则触发涨跌停的股票。其他股票会从当日分组平均值里剔除，而不是按 0% 收益参与平均。

一个好的策略，通常会让分数高的组收益也高，分数低的组收益也低。也就是说，从 `group_1` 到 `group_N`，收益应该是**单调上升**的。

如果你的 `group_5` 收益最高、`group_1` 收益最低，而且中间大致递增，说明你的分数真的能区分“好股票”和“坏股票”。

如果各组收益杂乱无章，说明你的分数和真实收益关系不大，需要重新审视策略逻辑。

---

## 7. 看懂 `summary.csv` 里的指标

回测结束后，平台会生成一个 `summary.csv` 文件，里面是一行数字，代表你的策略在 scoring 期的整体表现。下面是每个指标的含义，以及“高了/低了代表什么”。

| 指标 | 含义 | 高了/低了代表什么 |
|---|---|---|
| `total_return` | 整个 scoring 期的算术累计收益，等于每天的 `daily_return` 直接相加。 | **越高越好**。比如 0.3 表示按初始资金累计赚了 30%。 |
| `all_return` | 评分期的算术累计收益。当前实现中它和 `total_return` 完全相同，都只覆盖评分期（scoring window），不包含 Warmup 期。 | **越高越好**。 |
| `annual_return` | 把算术累计收益按 252 个交易日线性年化后的收益率。 | **越高越好**。方便和银行存款、基金等比较。 |
| `trading_days` | 评分期内的交易日天数。 | 用于理解策略运行了多少天；本身不衡量好坏。 |
| `average_year_return` | 各自然年收益的平均值。 | **越高越好**。反映策略每年大概能赚多少。 |
| `worst_year_return` | 所有自然年中收益最差的那一年。 | **越高越好**。负很多说明某一年亏得很惨。 |
| `sharpe` | 夏普比率，衡量每承担一单位风险能获得多少超额收益。 | **越高越好**。通常大于 1 就算不错。 |
| `max_drawdown` | 最大回撤，净值从最高点跌到最低点的最大幅度。 | **越低越好**。比如 0.2 表示最多亏过 20%。 |
| `average_turnover` | 平均换手率，每天交易金额占组合价值的比例。 | **适中最好**。太高会吃掉成本；太低可能策略没充分表达。 |
| `long_total_return` | 多头仓位的累计收益（多空模式下）。 | **越高越好**。只做多模式下通常接近 `total_return`。 |
| `short_total_return` | 空头仓位的累计收益（多空模式下）。 | 多空策略中，**过高**的空头正收益会在综合评分中被惩罚；对只做多模式通常为 0。 |
| `annualized_short_profit` | 空头收益的年化正值（`max(年化空头收益, 0)`）。 | 仅在多空模式下有意义；综合评分公式中它是一项 100 权重的惩罚项。 |
| `win_rate` | 盈利天数占总交易日的比例。 | **越高越好**。但 win_rate 高不一定总收益高，还要看盈亏大小。 |
| `average_long_exposure` | 平均每天多头仓位占总资金的比例。 | 只做多模式下接近 1 正常；多空模式下反映做多倾向。 |
| `average_short_exposure` | 平均每天空头仓位占总资金的比例。 | 仅多空模式有意义；只做多模式下通常为 0。 |
| `average_gross_exposure` | 平均每天总敞口，等于多头加空头的绝对值之和。 | **太高**意味着杠杆和风险都大。 |
| `average_net_exposure` | 平均每天净敞口，等于多头加空头（空头为负值）。 | 反映策略整体偏多看涨还是偏空看跌。 |
| `average_position_count` | 平均每天持仓的股票数量。 | 反映分散程度；太少容易受单只股票影响。 |
| `calmar` | 年化收益除以最大回撤，衡量收益和回撤的性价比。没有最大回撤时该值为空，而不是 0。 | **越高越好**。表示每承担一单位最大回撤能带来多少年化收益。 |
| `stale_position_days` | 评分期内存在持仓但当天没有有效收盘价可标记的天数。 | **越低越好**。高了说明组合里有较多无法正常盯市的持仓。 |
| `max_stale_gross_exposure` | 单日最大无法正常盯市持仓的总敞口。 | **越低越好**。 |
| `average_stale_gross_exposure` | 平均每天无法正常盯市持仓的总敞口。 | **越低越好**。 |
| `terminal_stale_position_count` | 评分末日仍没有有效收盘价的持仓数量。 | 历史学习轨道允许非零，但应结合敞口判断影响。 |
| `terminal_stale_gross_exposure` | 评分末日无法正常盯市持仓的总敞口。 | 历史学习轨道会按最后有效收盘价保留并披露。 |
| `fitness` | 综合指标，综合考虑夏普、年化收益和换手率。 | **越高越好**。平台排名时常用这个指标做综合参考。 |

这些指标会一起决定你的策略排名。不要只看 `total_return`，因为一个收益很高但回撤巨大的策略，通常不如收益稳定、夏普高的策略。

### 算术口径与复利口径：为什么同一份结果有两套数字

上面表格里的 `total_return`、`annual_return`、`max_drawdown`、`calmar` 用的是**算术口径**：每天的 `daily_return` 直接相加，年化就是「累计收益 × 252 ÷ 交易日数」。这是历史评分一直使用的口径，评分权重（`config/platform.yaml` 里的 `sharpe_weight`、`annual_return_weight` 等）也是按它调好的，所以它不会变，排行榜也不会因为口径调整而出现前后不可比的情况。

但算术年化是线性外推，忽略了一个事实：**亏损之后要更大的涨幅才能回本**（波动拖累）。所以从某个版本开始，`summary.csv` 里在同一行结果旁边额外输出一组**复利口径**的指标，用来回答“如果按复利真实滚动，这条曲线到底年化多少”：

| 字段 | 公式 | 说明 |
|---|---|---|
| `compounded_total_return` | `∏(1 + r_i) − 1` | 复利累计收益。 |
| `cagr` | `(∏(1 + r_i))^(252 / n) − 1` | 年化复合增长率。提交详情页第二张 KPI 卡显示的就是它。 |
| `compounded_max_drawdown` | 复利净值（从 1.0 起算）的峰谷最大跌幅。 | 波动越大，它通常比 `max_drawdown` 更深。 |
| `compounded_calmar` | `cagr / compounded_max_drawdown`。 | 复利口径的收益回撤比。 |
| `volatility` | `std(daily_return) × sqrt(252)`。 | 年化波动率。 |
| `sortino` | `sqrt(252) × mean(r − rf_d) / DD`，`DD = sqrt(mean(min(r − rf_d, 0)²))` | 只惩罚下行波动的收益风险比；`rf_d = long_only_risk_free_rate / 252`（默认 1.75%）。 |
| `t_stat` | `mean(r) / std(r) × sqrt(n)` | 日收益均值的 t 值，用来判断「收益是不是运气」。 |
| `t_stat_p_value` | `erfc(abs(t) / sqrt(2))` | 正态近似的双侧 p 值。 |

几条容易踩到的边界（这些字段取 `null` 而不是硬凑一个 0 或无穷大）：

- 交易日不足 2 天：`volatility`、`sortino`、`t_stat`、`t_stat_p_value` 为空。
- 任何一天收益 ≤ −100%（净值归零）：`cagr`、`compounded_total_return`、`compounded_max_drawdown`、`compounded_calmar` 为空，算术字段照常输出。
- 全程零收益：`cagr = 0`，但 `sortino` 和 `t_stat` 为空（分母为 0）。
- 推荐看盘顺序：先用算术口径对比排名（与评分一致），再用 `cagr` / `compounded_max_drawdown` 判断这条曲线在真实复利下是否仍然漂亮。完整定义见 `docs/metrics-definitions.md`。

`performance_by_year.csv` 的年度回撤现在也使用与 `summary.csv` 相同的相对回撤定义：先构造 `1 + 累计收益`，再计算相对历史峰值的跌幅，避免同一个结果页出现两套不兼容的回撤口径。

### 只做多模式：主动收益与 `raw_*` / `active_*` 字段

如果你开启 `execution.long_only`，平台不会直接用原始组合收益打分，而是会计算**相对沪深 300 的主动收益**（active return）。具体流程如下（源码见 `backend/src/quantfish/backtest/active_returns.py`）：

1. 先算组合每天的原始收益 `portfolio_return`、沪深 300 收益 `benchmark_return`，以及日无风险收益 `risk_free_return = long_only_risk_free_rate / 252`。默认年化无风险利率是 `1.75%`。
2. 用超额收益的协方差/方差估算组合的 **beta**：

   ```text
   beta = cov(portfolio_return - risk_free_return, benchmark_return - risk_free_return)
          / var(benchmark_return - risk_free_return)
   ```

3. 主动收益 = 组合超额收益 − beta × 基准超额收益：

   ```text
   active_return = (portfolio_return - risk_free_return)
                   - beta * (benchmark_return - risk_free_return)
   ```

4. 所有“打分用”指标（`total_return`、`annual_return`、`sharpe`、`max_drawdown`、`calmar`）都基于 `active_return` 计算。因此，只做多模式下的 `sharpe` 本质上就是主动收益的**信息比率（Information Ratio）**。

5. 同时，`summary.csv` 还会输出原始组合表现和主动风险指标，供你对比：

   | 字段 | 含义 |
   |---|---|
   | `raw_total_return` / `raw_max_drawdown` / `raw_calmar` | 原始组合收益（未扣除 beta 影响）。 |
   | `raw_sharpe` | 原始组合收益减去无风险收益后的夏普。 |
   | `risk_free_rate` / `risk_free_daily_return` | 年化/日度无风险收益参数。 |
   | `active_total_return` / `active_annual_return` / `active_max_drawdown` | 主动收益对应的累计/年化/最大回撤。 |
   | `beta` | 组合相对沪深 300 的 beta。 |
   | `tracking_error` | 主动收益的年化跟踪误差，等于 `std(active_return) * sqrt(252)`。 |
   | `information_ratio` | 年化主动收益 / 跟踪误差。 |
   | `active_observations` | 用于计算 beta 和主动收益的有效天数。 |

> **注意**：只做多模式下的排名看的是主动收益指标，而不是 `raw_*`。这意味着一个“跟着大盘涨”的策略，原始收益可能很高，但主动收益和信息比率可能很低。

> **历史学习轨道的临时例外**：`learning`、`learning_1`、`learning_2` 和 `learning_3` 当前设置为 `long_only_benchmark: none`，因为早期窗口没有完整的沪深 300 数据。这些轨道仍按只做多规则执行交易，但直接用 `portfolio_return` 计算评分指标；指数若存在只用于结果图。`hidden_test` 仍严格使用沪深 300 主动收益评分。

---

## 8. 看懂 `graph_data.json` 里的图

`graph_data.json` 是平台用来画图的原始数据。你可以把它理解成“图表版的 `summary.csv`”。里面主要包含以下几类图：

### 累计收益曲线（equity / equity_cny）

- 横轴是日期，纵轴是按初始资金累计出来的收益曲线。
- `equity` 等于 `1 + daily_return.cumsum()`，1.5 表示按初始资金累计赚了 50%。
- `equity_cny` 是换算成人民币后的累计收益金额，等于 `equity * capital`。
- 这张图最直观：曲线向上说明赚钱，向下说明亏钱。
- 只做多模式下，这张 `equity` 图仍使用原始组合收益，便于看真实持仓表现；页面上的主动收益 KPI 和 `alpha` 曲线使用 beta 调整后的主动收益。

### 回撤（drawdown）

- 横轴是日期，纵轴是回撤比例。
- 0 表示当前净值就是历史新高；`-0.15` 表示相比前期高点下跌了 15%。
- 曲线越深、持续时间越长，说明策略波动越大、持有体验越差。

### 日收益（daily_returns / daily_pnl）

- `daily_returns` 是每天的收益率。
- `daily_pnl` 是每天盈亏的人民币金额。
- 柱状图通常用来观察收益是否稳定：如果柱子忽高忽低，说明策略波动大。

### 换手率（turnover / trade_volume）

- `turnover` 是每天的总换手率。
- `trade_volume` 细分为买入金额（`buy_cny`）和卖出金额（`sell_cny`）。
- 用来判断策略交易是否过于频繁。

### 多空敞口（exposure）

- 包含 `long_exposure`（多头敞口）、`short_exposure`（空头敞口）、`gross_exposure`（总敞口）、`net_exposure`（净敞口）和 `position_count`（持仓数量）。
- 如果持仓股票当天没有有效 `front_close`，平台会继续沿用原有 PnL 逻辑保留仓位，但会在图表数据里记录 `stale_position_count` 和 `stale_gross_exposure`，提醒你这部分持仓当天无法正常盯市。
- 若缺价发生在历史学习轨道的评分末日，平台不会虚构一次无法成交的卖出，而是按最后有效收盘价继续标记，并在摘要中记录 `terminal_stale_position_count` 与 `terminal_stale_gross_exposure`。隐藏测试仍会拒绝评分末日存在这类仓位的结果。
- 用来观察你的策略是偏多头、偏空头，还是风险敞口过大。

### 分组累计收益（group_cumulative）

- 把股票按分数分组后，每组从回测开始到每一天的算术累计收益。分组收益只统计下一交易日可执行的股票。
- 理想情况下，`group_1` 最低，`group_N` 最高，中间单调上升。
- 这张图是判断你的分数是否有“区分度”的重要依据。

### 基准与超额（benchmark / alpha）

- `benchmark` 是沪深 300 等基准指数的算术累计收益曲线，用来和你的策略对比。
- `alpha` 是超额收益的算术累计曲线。
  - **多空模式**：`alpha` 等于策略累计收益减去基准累计收益。
  - **只做多模式**：`alpha` 基于 **无风险利率和 beta 调整后的主动收益**（`(portfolio_return - risk_free_return) - beta × (benchmark_return - risk_free_return)`），所以只做多时它衡量的是剔除现金收益和大盘 beta 后的超额能力。
- 如果你的策略长期跑赢基准，`alpha` 曲线会稳定向上。

> **图表数据源提醒**：
> - **多空模式**：`equity`、`drawdown`、`daily_pnl`、`daily_returns` 都基于原始组合收益（`portfolio_return`）；`alpha` 等于策略累计收益减基准累计收益。
> - **只做多模式**：`equity`、`drawdown`、`daily_pnl` 和图表内的 `daily_returns` 使用原始组合收益（`portfolio_return`）；`alpha` 使用 beta 调整后的主动收益。页面会把两类口径明确标为“策略原始表现”和“主动表现”。导出的 `daily_returns.parquet` 与 `net_value.parquet` 则是评分口径的主动收益序列。

---

## 9. 一句话总结

回测就是平台用历史数据模拟你的策略真实交易的过程。

具体来说：它会把你的分数变成仓位，用官方执行价买卖，用官方收盘价结算，再扣除成本，最后给出 `summary.csv` 里的各项指标和 `graph_data.json` 里的各种图表。看懂这些，你就能判断自己的策略到底好不好、哪里还能改进。

---

## 本章要点

- 回测把分数变成权重，延迟一天用 `front_vwap` 成交、`front_close` 结算并扣除成本。
- `config/platform.yaml` 里的 `backtest` 和 `execution` 配置决定回测行为。
- Warmup 期用于建仓和预热，Scoring 期才真正计入成绩。
- 流动性限制和涨跌停保护让回测结果更接近真实交易。
- 综合 `summary.csv` 指标和 `graph_data.json` 图表评估策略好坏。

上一步：[示例策略逐行讲解](./05-example-strategies-walkthrough.md) | 下一步：[在本地运行](./07-running-locally.md)
