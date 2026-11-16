# 回测引擎揭秘：学生策略的完整一生

读完《第一个策略》和《回测与评价指标》之后，你已经知道怎么写 `generate_signals`，也知道平台会吐出 `summary.csv`。但你可能仍然好奇：**我点下“上传”之后，到底发生了什么？我的分数是怎么变成仓位的？为什么收盘价和 VWAP 要分开算？**

这一章把平台当成一条透明流水线，带你看懂策略从上传、打分、配权、成交到算收益的完整生命周期。

读完本章，你会理解：

- 文件上传到打分完成的全部链路。
- `generate_signals` 的输入输出长什么样。
- 平台怎么把分数变成“买多少、卖多少”。
- 官方执行价 `front_vwap` 和官方结算价 `front_close` 是怎么来的。
- 一天的收益为什么拆成“隔夜段 + 日内段”。
- 交易成本、涨跌停、流动性限制是怎么扣分的。
- 各项指标到底在说什么。
- Learning 数据和 Hidden 数据有什么不同。

> 如果你还没读过，可以先看 [第一个策略](./01-first-strategy.md)、[回测与评价指标](./06-backtest-and-metrics.md) 和 [策略函数深入解析](./04-generate-signals-deep-dive.md)。

---

## 1. 上传后发生了什么

你可以把整个流程想象成“把一道菜谱交给后厨”：

- 你上传 `strategy.py` = 交上一张菜谱。
- 平台帮你采购食材、控制火候、计算成本、端出成绩单。

具体链路是这样的：

```text
网页上传 strategy.py
        │
        ▼
src/quantfish/submissions/routes.py
        │  接收 HTTP 请求，取出文件和参数
        ▼
service.py
        │  校验队伍密码、保存策略文件、创建任务记录
        ▼
dispatcher.py
        │  从任务队列里取出等待打分的提交
        ▼
runners.py
        │  启动一个独立子进程
        ▼
score_worker.py
        │  加载配置，调用回测引擎
        ▼
factor_execution/strategy_execution.py
        │  逐日调用你的 generate_signals(data, date)
        ▼
backtest/runner.py + backtest/simulator.py
        │  组合构建 + 模拟成交 + 计算指标
        ▼
report_dir/summary.csv
report_dir/graph_data.json
report_dir/*.parquet   (日收益、净值、换手率、分组收益等)
report_dir/diagnostics.json
```

（上图只列出主要产物，完整产物还包括若干 Parquet 诊断文件。）

几个关键细节：

- **子进程隔离**：`runners.py` 用 `subprocess.Popen` 启动 `score_worker.py`。你的策略代码如果崩溃或超时，只会影响这一个 Worker，不会把网页端拖垮。
- **超时保护**：当前默认配置为 `submission_timeout_enabled: true`，`submission_timeout_seconds: 1200`（20 分钟）。如果策略运行超过这个时间，Worker 会被强制终止。具体值以运行时的 `config/platform.yaml` 为准。
- **数据目录由上传时决定**：提交时可以选择完整 `learning`、三个历史学习窗口（`learning_1` / `learning_2` / `learning_3`）或 `hidden_test`，后续打分用的就是对应目录里的数据。所有轨道的引擎完全相同，只是“食材”和评分日期不同。

---

## 2. `generate_signals(data, date)` 的输入与输出

平台每天收盘后会问你一次：“今天每只股票打几分？”你要回答的就是 `generate_signals`。

### 输入

```python
def generate_signals(data, date):
    ...
```

| 参数 | 含义 |
|---|---|
| `data` | 日期绑定视图。只能看到**当前交易日及之前**的数据，看不到未来。 |
| `date` | 当前交易日，例如 `2023-06-30`。 |

`data` 有三个常用接口：

| 接口 | 用途 |
|---|---|
| `data.current(...)` | 读取当天数据。 |
| `data.history(...)` | 读取过去一段历史。 |
| `data.latest(...)` | 每只股票取截至当天最新的一条记录。 |

如果你试图读取当前日期之后的数据，平台会抛出 `FutureDataAccessError`。具体例子可以参考 [常见错误速查](./09-common-errors.md)。

### 输出

你必须返回以下两种格式之一：

**格式 A：pandas Series（最推荐）**

```python
return pd.Series(score_values, index=stock_codes)
```

- `index` 是股票代码。
- `values` 是分数。

**格式 B：包含 `code` 和 `score` 两列的 DataFrame**

```python
return pd.DataFrame({"code": stock_codes, "score": score_values})
```

注意：

- **学生只能返回分数，不能返回权重。** 你不能告诉平台“买 30% 的茅台”，你只能告诉平台“茅台今天分数很高”。
- `NaN` 表示“这只股票今天没有信号”。
- 在 `longonly` 模式下，`0` 是中性信号；在 `longshort` 模式下，真正的中性是分数等于当天所有股票的平均分，而不是 `0`。
- 分数越高，平台越倾向于做多或排进多头前列；分数越低，在多空模式下越可能进入空头。

---

## 3. 从分数到权重：平台怎么决定买多少

这一步就像在餐厅里给所有菜打分，然后决定每道菜夹多少筷子。

你的策略只负责“打分”，平台负责“夹菜”。核心规则写在 `src/quantfish/backtest/panel.py` 的 `preprocess_signals` 里。

### 3.1 多空模式 `longshort`

平台先把分数**去均值**（demean），再除以**绝对值之和**，得到权重。

```text
 centered = score - mean(score)
 weight   = centered / sum(|centered|)
```

结果大致是：

- 多头侧总权重 ≈ +0.5
- 空头侧总权重 ≈ −0.5
- 总敞口（多头绝对值 + 空头绝对值）≈ 1.0（乘以 `max_leverage` 之前）

> `config/platform.yaml` 里的 `execution.max_leverage` 默认是 1。如果管理员把它改成 2，上面的权重会先乘以 2，总敞口也会变成约 2.0。

打个比方：你给 10 道菜打分后，平台把分数高于平均分菜的夹到盘子的“做多区”，低于平均分的夹到“做空区”，两边盘子总重量差不多。

### 3.2 只做多模式 `longonly`

只做多模式不会做空。平台会先选出分数最高的一批股票，再根据 `execution.long_only_weighting` 决定怎么分配权重：

```text
rank_equal:
  只买 score > 0 的入选股票，入选股票等权

score_proportional:
  clipped = max(score, 0)
  weight  = clipped / sum(clipped)
```

结果：

- 所有权重 ≥ 0。
- 0 分和负分表示中性/现金，不会成为买入候选。
- 默认 `rank_equal` 下，分数只决定能否入选；入选且分数为正的股票等权。
- `score_proportional` 下，正分越高，权重越大。

只做多模式还会额外做三件事（源码见 `src/quantfish/backtest/runner.py` 和 `src/quantfish/backtest/simulator.py`）：

1. **可投资股票池过滤**：平台只用信号日已知的信息，剔除 `tradable == False`、缺失有效 `front_close` / `front_vwap` / 成交金额、在信号日上市天数不足 `min_listing_days`（默认 60 天）、或缺少上市日期的股票。如果启用了上市天数过滤但整个 `basic.company_info` 数据源不可用，回测会直接失败。下一交易日能否成交不会反过来改变入选名单。
2. **单票权重上限**：由 `max_position_weight`（默认 `0.05`）控制。超出的权重会在其他已入选且仍有容量的股票之间重新分配；总容量不足时才留现金。
3. **主动收益评分**：确定权重和模拟成交后，平台会用 `portfolio_return - beta * hs300_return` 计算每天的主动收益，所有打分指标（`total_return`、`sharpe`、`max_drawdown`、`calmar` 等）都基于主动收益。详情见下文第 7 节。

### 3.3 `top_k`：最多持有几只

- 多空模式使用 `execution.top_k`，默认 `null`，表示“所有有分数的股票都参与”。
- 只做多模式使用 `execution.long_only_target_count`，默认 50。
- 在 `longshort` 模式下，平台会保留分数最高的 `top_k` 只和最低的 `top_k` 只。
- 在 `longonly` 模式下，只保留分数最高的 `long_only_target_count` 只。
- 这个数量是硬上限；同分时按平台原始顺序先到先得，不会因为并列而多选。
- 注意：截断发生在“归一化之前”。也就是说，先选人，再决定每人夹多少。

### 3.4 `group_count` 只是分组图用的

`group_count` 是 `config/platform.yaml` 里的 `backtest.group_count`，例如 5。它的作用是：

- 把每天所有股票按分数排序，平均分成 5 组。
- 分别计算每组的累计收益，画出**分组累计收益图**。
- **它不参与真实组合构建。** 你把它改成 10 或 3，不会影响你的仓位和收益。

分组图里的收益是“可执行分组收益”：平台只把下一交易日有有效收盘价、有效 VWAP、可交易且未按官方字段或板块回退规则触发涨跌停的股票纳入当日分组平均。不能成交或不能正常定价的股票会被剔除，不会当作 0% 收益稀释分组。

> 想看分组图怎么解读，可以参考 [回测与评价指标](./06-backtest-and-metrics.md) 的第 6 节。

---

## 4. 用什么价格成交

平台只使用**前复权价格**（front_adjusted）。它从两张表合成官方价格：

- `stock.daily_returns` 里的原始收盘价 `clsprc`、成交量 `dnshrtrd`、成交额 `dnvaltrd`。
- `factor_benchmark.adj_factor` 里的累计前复权因子 `cumulatefwardfactor`。

官方价格的计算方式是：

```text
raw_vwap    = dnvaltrd / dnshrtrd
front_close = clsprc * cumulatefwardfactor
front_vwap  = raw_vwap * cumulatefwardfactor
```

其中：

- `front_close` 是**官方结算价**（mark price）。
- `front_vwap` 是**官方执行价**（execution price）。

平台默认的成交模型是：

> **昨天收盘后决定信号 → 今天按 VWAP 成交 → 今天收盘按收盘价结算。**

为什么这样设计？因为 VWAP（Volume-Weighted Average Price，成交量加权均价）比开盘价或收盘价更接近“真实能成交的价格”，而收盘价是当天结束后的公允价值。

---

## 5. 一天里的收益怎么算

一天的收益被拆成两段，原因是仓位会隔夜变化。

### 5.1 两段收益的直觉

想象你昨天收盘时已经持有一些仓位：

1. **隔夜段（close → VWAP）**：昨天收盘到今天开盘/上午，股价从昨天的收盘价跳到了今天的 VWAP。这段收益由**昨天的仓位**承担。
2. **日内段（VWAP → close）**：今天 VWAP 到今天收盘，股价继续波动。这段收益由**今天调仓后的仓位**承担。

然后平台再扣除交易成本，得到当天的组合收益。

### 5.2 公式

用符号写出来：

```text
r_close_to_vwap = Σ  previous_position * (front_vwap_today / front_close_yesterday - 1)
r_vwap_to_close = Σ  current_position  * (front_close_today / front_vwap_today - 1)

daily_return = r_close_to_vwap + r_vwap_to_close - transaction_cost
```

其中：

- `previous_position` 是昨天收盘后的仓位。
- `current_position` 是今天按 VWAP 调仓后的仓位。
- `transaction_cost` 是交易费用，下一节会讲。

为了让结果更容易解释，平台展示和评分里的总收益使用**算术累计收益**：每天的 `daily_return` 都按初始资金口径直接相加，而不是一天天复利滚动。

```text
cumulative_return_today = cumulative_return_yesterday + daily_return
equity_today = 1 + cumulative_return_today
equity_cny_today = capital * equity_today
```

> **注意**：多空模式下 `daily_return` 是原始组合收益；只做多模式下 `daily_return` 是 beta 调整后的主动收益（`scored_daily_return`），所以图表和 `summary.csv` 里的 `raw_*` 指标可能不同步。

---

## 6. 交易成本与涨跌停等限制

真实交易不是想成交就能成交，平台会帮你模拟这些限制。

### 6.1 交易成本

交易成本来自三部分：

- **手续费** `commission_rate`
- **滑点** `slippage_rate`
- **卖出印花税** `sell_stamp_duty_rate`（只对卖出收取）

它们都按**换手率**收取：

```text
transaction_cost = turnover * (commission_rate + slippage_rate)
                 + sell_turnover * sell_stamp_duty_rate
```

`turnover` 是当天所有股票仓位变化量绝对值的总和。当前配置分别使用 `0.0003` 手续费、`0.0005` 滑点和 `0.0005` 卖出印花税；它们是课堂模拟假设，不是券商报价。

### 6.2 涨跌停保护

A 股不同板块的涨跌停幅度不同。平台优先使用数据源提供的每日 `limit_status` 或涨跌停价格；这些字段缺失时，才按板块和日期回退：沪深主板约 10%，注册制后的创业板和科创板约 20%，北交所约 30%。

买入遇到涨停、卖出遇到跌停时，对应方向不会成交。多空诊断路径会保守地排除任何涨跌停股票。

### 6.3 流动性限制

单只股票当天的**仓位变化量**不能超过平台允许参与的日成交额比例：

```text
max_daily_change = max_participation_rate * dnvaltrd / capital
```

默认 `max_participation_rate = 0.10`，表示单只股票一天最多用其当天成交金额的 10% 来成交。如果平台算出的目标变化量超过这个上限，就会按上限截断。注意这限制的是“当天买卖多少”，而不是“总共持有多少”——如果前一天已经持仓且今天不交易，持仓可以保留。这防止了“小盘股随便买”的不真实乐观。

流动性上限是硬约束：被截断后的仓位不会被重新放大来凑满 `max_leverage`。所以在流动性很差、涨跌停或无法成交的日期，组合可能低于满仓，这是更接近真实交易的结果。

### 6.4 不可交易状态

如果某天股票缺失有效价格、成交量/成交金额为 0、或者被标记为不可交易（`tradable == False`），平台会跳过这只股票的调仓。`trdsta` / `TradingStatus` 会保留在数据里供你分析，但它本身不是平台执行层的禁止交易条件；执行层主要看有效价格、流动性、`limitstatus`/`limit_status` 和涨跌停阈值。

如果一只已经持有的股票当天没有有效收盘价，平台不会强行清仓，也不会用当天 VWAP 强行标记收益；它会继续保留仓位，当天这部分持仓记为 0 PnL，并在每日记录里标出 `stale_position_count` 和 `stale_gross_exposure`，让你知道有多少仓位当天无法正常盯市。

短暂停牌后重新出现有效价格可以继续回测，并一次性反映相对最后有效收盘价的价格变化。历史学习轨道在评分末日使用 `carry`：保留仓位、沿用最后有效收盘价、当日记 0 PnL，不虚构成交或成本，同时披露期末缺价持仓数量与敞口。`hidden_test` 继续使用严格的 `terminal_stale_position_policy: reject`。

> 想了解更多限制细节，可以参考 [回测与评价指标](./06-backtest-and-metrics.md) 的第 4、5 节，以及 [DataFrame 字段速查](./dataframe-field-guide.md) 里的 `limitstatus` 和 `dnvaltrd` 说明。

---

## 7. 指标解释（收益率、夏普、最大回撤、换手率、敞口）

平台最后会生成 `summary.csv`。这些指标都是基于**评分期（scoring window）**的每日收益算出来的。

| 指标 | 含义 | 好坏方向 |
|---|---|---|
| `total_return` | 评分期算术累计收益，等于评分期每天的 `daily_return` 相加。 | 越高越好 |
| `annual_return` | 把算术累计收益按 252 个交易日线性年化后的收益率。 | 越高越好 |
| `sharpe` | 夏普比率，年化收益 / 年化波动。衡量每承担一单位风险获得多少收益。 | 越高越好，通常 > 1 不错 |
| `max_drawdown` | 最大回撤，净值从高点跌到最低点的最大幅度。 | 越低越好 |
| `average_turnover` | 平均每天换手率。 | 适中最好 |
| `win_rate` | 盈利天数占比。 | 越高越好 |
| `average_long_exposure` | 平均多头仓位。 | 只做多时接近 1 正常 |
| `average_short_exposure` | 平均空头仓位。 | 仅多空模式有意义 |
| `average_gross_exposure` | 平均总敞口 = 多头 + \|空头\|。 | 太高意味着杠杆和风险大 |
| `average_net_exposure` | 平均净敞口 = 多头 + 空头（空头为负）。 | 反映整体偏多还是偏空 |
| `average_position_count` | 平均每天持仓股票数量。 | 反映分散程度 |
| `calmar` | 年化收益 / 最大回撤。 | 越高越好 |
| `fitness` | 综合指标，等于 `sharpe * sqrt(abs(annual_return) / max(average_turnover, 0.125))`。 | 越高越好 |

### 只做多模式下的“主动收益”指标

在 `longonly` 模式下，上表里的 `total_return`、`annual_return`、`sharpe`、`max_drawdown`、`calmar` 并不是直接基于原始组合收益，而是基于**主动收益**（active return）。计算过程如下（源码见 `src/quantfish/backtest/active_returns.py`）：

```text
rf_daily = long_only_risk_free_rate / 252
beta = cov(portfolio_return - rf_daily, hs300_return - rf_daily)
       / var(hs300_return - rf_daily)
active_return = (portfolio_return - rf_daily) - beta * (hs300_return - rf_daily)
```

然后：

```text
tracking_error = std(active_return) * sqrt(252)
information_ratio = mean(active_return) * 252 / tracking_error
```

因此，只做多模式下的 `sharpe` 本质上就是信息比率。`summary.csv` 会同时给出：

- `raw_total_return`、`raw_max_drawdown`、`raw_calmar`：原始组合表现；
- `raw_sharpe`：原始组合收益减去无风险收益后的夏普；
- `active_total_return`、`active_annual_return`、`active_max_drawdown`：主动收益表现；
- `risk_free_rate`、`risk_free_daily_return`、`beta`、`tracking_error`、`information_ratio`、`active_observations`：主动风险指标。

### 几个关键公式的记忆点

- **年化**：平台假设一年有 252 个交易日。

  ```text
  annual_return = total_return * 252 / trading_days
  ```

- **夏普**：

  ```text
  sharpe = sqrt(252) * mean(daily_return) / std(daily_return)
  ```

- **回撤**：

  ```text
  drawdown_t = equity_t / max(equity_1..equity_t) - 1
  max_drawdown = |min(drawdown)|
  ```

> 想看这些指标在图表里长什么样，可以参考 [回测与评价指标](./06-backtest-and-metrics.md) 的第 7、8 节。

> **图表数据来源提醒**：
> - **多空模式**：`equity`、`drawdown`、`daily_pnl`、`daily_returns` 基于原始组合收益（`portfolio_return`）；`alpha` 等于策略累计收益减基准累计收益。
> - **只做多模式**：`equity`、`drawdown`、`daily_pnl` 和图表内的 `daily_returns` 基于原始组合收益（`portfolio_return`），`alpha` 基于 beta 调整后的主动收益。页面的 KPI 会明确标注主动口径；导出的 `daily_returns.parquet` 和 `net_value.parquet` 使用评分口径。

---

## 8. Learning 数据与 Hidden 数据的区别

平台提供完整学习数据、三个历史学习窗口和一个正式隐藏窗口：

| 轨道 | 用途 | 时间窗口 | 目录 | 学生可见 |
|---|---|---|---|---|
| `learning` | 完整学习范围、调试策略 | 2010-01-02 至 2022-12-31 | `data_releases/learning` | 是 |
| `learning_1` | 历史稳定性检查 | 2010-01-02 至 2015-12-31 | `data_releases/learning_1` | Web 提交可选 |
| `learning_2` | 历史稳定性检查 | 2015-01-01 至 2020-12-31 | `data_releases/learning_2` | Web 提交可选 |
| `learning_3` | 历史稳定性检查 | 2020-01-01 至 2022-12-31 | `data_releases/learning_3` | Web 提交可选 |
| `hidden_test` | 排行榜打分、正式排名 | 2023-01-01 至 2025-12-31 | `data_releases/hidden_test` | 原始数据不可见，只能提交后打分 |

2015 和 2020 分别位于相邻的两个历史窗口中，因此这些窗口不是互斥分区。

**核心结论**：所有轨道用的是同一套回测引擎、同一套评分规则，只是**时间窗口和目录不同**。

- 你在 Learning 上调试好的策略，上传到 Hidden 后会用未来的真实数据打分。
- 如果 Learning 上表现很好但 Hidden 上表现差，说明策略可能过拟合了 Learning 数据。
- 提交时选择 `data_track=learning` 只是练习，不会进入正式排名；默认提交到 Hidden。

---

## 9. 一句话总结

你点下上传后，平台会：

1. 把你的策略文件交给一个独立 Worker。
2. 在每个交易日调用 `generate_signals(data, date)` 收集分数。
3. 按 `longshort` 或 `longonly` 规则把分数变成权重。
4. 用前复权的 `front_vwap` 成交、`front_close` 结算。
5. 扣除交易成本、涨跌停和流动性限制后，计算每日收益。
6. 最后生成指标和图表。

Learning 和 Hidden 用的引擎一模一样，只是数据和时间不同。看懂这条流水线，你就能更有针对性地调试策略，而不是只盯着最终分数猜原因。

---

## 本章要点

- 上传链路：`routes.py → service.py → dispatcher.py → runners.py → score_worker.py → strategy_execution.py`。
- `generate_signals` 返回 Series 或含 `code`/`score` 的 DataFrame；学生不能返回权重。
- `longshort` 去均值后按绝对值和归一化；`longonly` 截断负数后按总和归一化。
- `top_k` 限制持仓数量，`group_count` 只影响分组图。
- 官方价格只有前复权：`front_close = clsprc * cumulatefwardfactor`，`front_vwap = (dnvaltrd / dnshrtrd) * cumulatefwardfactor`。
- 日收益 = 隔夜段（close→VWAP）+ 日内段（VWAP→close）− 交易成本。
- 交易成本、涨跌停、流动性、不可交易状态都会限制最终成交。
- 指标基于评分期日收益计算，年化按 252 个交易日。
- `longonly` 模式会过滤可投资股票池（流动性、上市天数），限制单票权重，并用主动收益（`portfolio_return - beta * benchmark_return`）计算评分指标。
- Learning 和 Hidden 是同一引擎、不同数据窗口。

上一步：[Cookbook](./10-cookbook.md) | 下一步：[术语表](./glossary.md)
