# Raw Findings from Documentation Audit Swarm

This document contains the unedited reports from the four read-only explore agents that audited the student docs against the QuantFish source code. Findings are grouped by agent scope. The lead editor will triage these into `docs/audit/fix-checklist.md`.

---

## Agent 0: Student documentation inventory and cross-cutting gaps

**Scope:** `docs/student/` all Markdown documents and example files.

### 1. 文档清单与目标受众

#### 1.1 文件列表

| 路径 | 性质 | 主要内容 |
|---|---|---|
| `docs/student/README.md` | 入口/目录 | 阅读顺序、快速开始、环境检查 |
| `docs/student/00-before-you-start.md` | 入门 | 环境安装、Conda、数据构建、基础命令行 |
| `docs/student/00a-environment-kit.md` | 离线包指南 | 离线安装包、启动脚本、常见问题 |
| `docs/student/01-first-strategy.md` | 入门 | 最小策略 `generate_signals`、返回 Series |
| `docs/student/02-data-bundle-api.md` | API 教程 | `DataBundle`、`current`/`load`/`history`/`latest` |
| `docs/student/03-dataset-catalog.md` | 数据目录 | 数据集 ID/别名、常用表、字段速查 |
| `docs/student/04-generate-signals-deep-dive.md` | 核心机制 | 输入输出、`score` 语义、返回格式、常见错误 |
| `docs/student/05-example-strategies-walkthrough.md` | 示例讲解 | 动量、反转、市值、MACD 等示例思路 |
| `docs/student/06-backtest-and-metrics.md` | 回测与指标 | 配置字段、流动性、涨跌停、`summary.csv` 指标 |
| `docs/student/07-running-locally.md` | 本地运行 | `full_local_run.py`、输出文件、调试 |
| `docs/student/08-submitting-on-web.md` | Web 提交 | 启动平台、提交状态、排行榜、下载入口 |
| `docs/student/09-common-errors.md` | 排错手册 | 常见报错与修复示例 |
| `docs/student/10-cookbook.md` | 代码片段 | z-score、过滤、合并预告、多因子合成 |
| `docs/student/11-backtest-engine-explained.md` | 引擎揭秘 | 完整链路、分数→权重、价格、收益拆分、指标公式 |
| `docs/student/12-raw-factor-ranking-lab.md` | 实验课 | 从原始数据到 longshort 权重 |
| `docs/student/12b-raw-factor-ranking-guided-lab.md` | 引导练习 | 填空式 longshort 权重练习 |
| `docs/student/13-datago-data-guide.md` | 专题 | DataGo 舆情表读取与策略示例 |
| `docs/student/dataframe-field-guide.md` | 字段参考 | `stock.daily_returns`、`BF_FORECAST` 等字段 |
| `docs/student/firm-data-api-guide.md` | 专题 | 四张财务报表数据与平台 API |
| `docs/student/glossary.md` | 术语表 | 核心概念解释 |
| `docs/student/examples/` | 示例代码 | `hello_strategy.py`、`full_local_run.py`、`limit_guard.py` 等 |

#### 1.2 目标受众

文档明确面向**零基础学生**。语言通俗，步骤拆解较细，从 Conda 安装、命令行概念到 Python 函数返回值都有覆盖。整体路径合理：先跑通示例 → 理解数据接口 → 修改信号 → 本地回测 → Web 提交。

### 2. 覆盖度评估

| 主题 | 覆盖情况 | 评价 |
|---|---|---|
| 环境安装（Conda/离线包） | 完整 | `00`、`00a`、`README` 均覆盖 |
| `generate_signals` 写法 | 完整 | `01`、`04`、`10` 多角度讲解 |
| 数据接口（current/load/history/latest） | 完整 | `02`、`dataframe-field-guide` 配合示例 |
| 数据集与字段 | 较完整 | `03`、`dataframe-field-guide`、`firm-data-api-guide`、`13-datago` 覆盖主要表 |
| 回测机制与指标 | 较完整 | `06`、`11` 覆盖核心机制 |
| 本地运行 | 完整 | `07` + `examples/full_local_run.py` |
| Web 提交 | 基本完整 | `08` 覆盖提交流程与状态 |
| 常见错误 | 较完整 | `09` 覆盖主要报错 |
| 高级主题（原始数据实验、DataGo、财报） | 有专题 | `12`、`12b`、`13`、`firm-data-api-guide` |

**明显缺口**：
1. **排行榜/综合评分公式**：`08-submitting-on-web.md` 只粗略列出参与指标，未给出具体 clamp 公式，也未提及 `annualized_short_profit` 惩罚项。
2. **长仓模式（long-only）的真实评分方式**：`06-backtest-and-metrics.md` 仍按“原始组合收益”讲解 `total_return`/`sharpe`，未说明 long-only 模式下平台实际使用 **HS300 beta 调整后的 active return** 计算这些指标，且 `summary.csv` 会出现 `raw_*`、`active_*`、`beta`、`tracking_error`、`information_ratio` 等字段。
3. **行业中性化默认开启**：`06-backtest-and-metrics.md` 表中说 `industry_neutralization` 默认 `false`，但当前 `config/platform.yaml` 为 `true`，学生若按文档理解“默认关闭”，会对组合行为产生误判。
4. **`max_position_weight` 与 `min_listing_days`**：配置中存在，文档未提及。
5. **`allowed_market_types` 的平台级过滤**：文档仅在 `12-raw-factor-ranking-lab.md` 提到 `markettype 1,4`，未说明这是平台运行时的硬过滤，研究脚本用 `DataBundle(...)` 不过滤。
6. **提交冷却与 `hidden_test_enabled` 开关**：未说明。
7. **离线包文件名不一致**：`00a-environment-kit.md` 使用 `generate_signals.py`，其余文档使用 `strategy.py`，且离线包结构未与学生下载的实际结构交叉验证。

### 3. 文档与源码不一致项（带路径/行号）

#### 3.1 行业中性化默认状态

- **文档**：`docs/student/06-backtest-and-metrics.md:103`
  > `industry_neutralization` | 行业中性化开关。开启后…… | `false`
- **源码/配置**：`config/platform.yaml:17` 为 `industry_neutralization: true`；`src/quantfish/backtest/runner.py:62-64` 从配置读取。
- **影响**：学生以为默认不关，实际运行时平台会按行业去均值，缺少行业分类的股票会被置 0 分。
- **建议**：将文档表格默认值改为 `true`，并强调“这会改变你的分数分布”。

#### 3.2 Long-only 模式评分基于 beta 调整后的 active return

- **文档**：`docs/student/06-backtest-and-metrics.md:203-224` 的指标表把 `total_return`、`sharpe`、`max_drawdown`、`calmar` 解释为“组合收益/风险”。
- **源码**：`src/quantfish/backtest/runner.py:129-165` 在 `mode == "longonly"` 时调用 `calculate_long_only_active_returns`，用 `portfolio_return - beta * hs300_return` 作为 `scored_daily_return`，再用它计算指标；原始组合指标存为 `raw_total_return`、`raw_sharpe` 等。
- **配置**：`config/platform.yaml:21-22` 明确 `long_only_benchmark: hs300`、`long_only_min_beta_observations: 20`。
- **影响**：学生在 long-only 模式下优化“原始收益”可能 irrelevant；排行榜/结果页上的 `total_return` 实为 active return。
- **建议**：在 `06-backtest-and-metrics.md` 和 `11-backtest-engine-explained.md` 中新增 long-only 指标解释章节，说明 `raw_*` 与 `active_*` 的区别，以及 `beta`、`tracking_error`、`information_ratio` 的含义。

#### 3.3 超时开关与超时时间

- **文档**：`docs/student/11-backtest-engine-explained.md:66-67`
  > 配置里 `submission_timeout_seconds` 默认值是 120 秒，但当前 `config/platform.yaml` 把 `submission_timeout_enabled` 设成了 `false`，所以目前不会强制终止。
- **配置**：`config/platform.yaml:46-47` 实际为
  ```yaml
  submission_timeout_seconds: 1200
  submission_timeout_enabled: true
  ```
- **文档**：`docs/student/08-submitting-on-web.md:105` 也说默认 120 秒。
- **影响**：学生可能低估实际超时限制；文档说“当前不强制终止”与事实相反。
- **建议**：更新两处为当前配置值 `1200` 秒且 `enabled: true`，并注明“具体以运行时的 `config/platform.yaml` 为准”。

#### 3.4 Hidden test 可能被禁用

- **文档**：`docs/student/08-submitting-on-web.md:53`、`11-backtest-engine-explained.md:373` 均把 `hidden_test` 描述为“正式/排行榜轨道”。
- **源码/配置**：`config/platform.yaml:44` 为 `hidden_test_enabled: false`；`src/quantfish/submissions/service.py:142-143` 会检查该开关并抛出 `Submissions are disabled`。
- **影响**：若管理员未开启 `hidden_test_enabled`，学生按文档默认提交到 `hidden_test` 会直接报错，文档未解释该开关。
- **建议**：在 `08-submitting-on-web.md` 提交页说明如果 `hidden_test` 无法提交，应检查管理员是否启用了该轨道。

#### 3.5 排行榜综合评分公式

- **文档**：`docs/student/08-submitting-on-web.md:121-130`
  > 综合评分是把下面几个指标按权重组合起来：`total_return`、`sharpe`、`max_drawdown`、`average_year_return`、`worst_year_return`、`average_turnover`……
- **源码**：`src/quantfish/leaderboard/ranking.py:208-287` 实际公式为：
  ```text
  score = clamp(sharpe / 2.0, -1, 1) * 40
        + clamp(annual_return / 0.30, -1, 1) * 60
        - clamp(abs(max_drawdown) / 0.30, 0, 1) * 15
        - clamp(average_turnover / 3.0, 0, 1) * 5
        - clamp(annualized_short_profit / 0.30, 0, 1) * 100
  ```
  其中 `annualized_short_profit` 是源码中新增、文档未提及的惩罚项（权重 100）。
- **影响**：学生不知道 `short_profit` 会被重罚，也不清楚各项指标有 target/limit 阈值。
- **建议**：替换为源码中的精确公式与权重，并解释 `annualized_short_profit` 在多空模式下的含义。

#### 3.6 `max_position_weight` 与 `min_listing_days` 未文档化

- **配置**：`config/platform.yaml:51` `max_position_weight: 0.05`；`config/platform.yaml:53` `min_listing_days: 60`。
- **源码**：`src/quantfish/backtest/runner.py:109-113` 仅在 long-only 模式下应用 `max_position_weight`；`src/quantfish/backtest/runner.py:384-465` 用 `min_listing_days` 过滤 long-only 可投资股票池。
- **文档**：`06-backtest-and-metrics.md` 的配置表中未出现这两个字段。
- **影响**：long-only 学生不知道单只股票权重上限 5%，也不知道新股/次新股会被剔除。
- **建议**：在 `06-backtest-and-metrics.md` 和 `glossary.md` 中补充。

#### 3.7 离线包入口文件名不一致

- **文档**：`docs/student/00a-environment-kit.md:200`
  > 你**只需要修改一个文件**：`generate_signals.py`。
- **文档**：`docs/student/README.md:39`、`01-first-strategy.md:13` 均使用 `strategy.py`。
- **影响**：离线包用户按 `00a` 找不到 `generate_signals.py` 会困惑；按其余文档准备 `strategy.py` 又与离线包结构不符。
- **建议**：统一命名或在 `00a` 中明确“离线包入口文件名为 `generate_signals.py`，等价于在线文档中的 `strategy.py`”。

#### 3.8 `DataBundle` 研究与平台运行的市场范围差异

- **文档**：`docs/student/02-data-bundle-api.md`、`03-dataset-catalog.md` 中 `DataBundle("data_releases/learning")` 示例未说明市场过滤。
- **源码**：`src/quantfish/data/bundle.py:46-58`、`src/quantfish/market_types.py:19`；平台运行时使用 `DEFAULT_ALLOWED_MARKET_TYPES = (1, 4)`（`src/quantfish/backtest/runner.py:42` 从配置读取）。
- **影响**：学生研究时看到创业板/科创板等股票，提交后平台只保留 `markettype 1/4`，策略表现可能不同。
- **建议**：在 `02-data-bundle-api.md` 或 `03-dataset-catalog.md` 增加提示框，说明平台默认仅交易 `markettype 1,4`；研究脚本如需一致应手动过滤。

#### 3.9 `score = 0` 在 long-only 与 longshort 中的含义

- **文档**：`docs/student/04-generate-signals-deep-dive.md:71` 说 `0` 是中性信号；`11-backtest-engine-explained.md:121` 补充“longonly 模式下 0 是中性，longshort 模式下真正的中性是当天平均分”。
- **源码**：`src/quantfish/backtest/panel.py:146-158`，longshort 中去均值后 `0` 会对应接近 0 的权重（因为平均分被减掉），但并非严格的“当天平均分等于中性”。文档表述在 longshort 下容易引起误解，因为学生返回的 `0` 经过 demean 后确实接近中性，但“真正的中性是分数等于当天所有股票的平均分”这句话与 demean 逻辑一致，基本正确。

#### 3.10 输出文件 `performance_by_year.csv`

- **文档**：`docs/student/07-running-locally.md:225-236` 的输出文件表列出 7 个文件，未包含 `performance_by_year.csv`。
- **源码**：`src/quantfish/backtest/report_writer.py:24` 实际会写出该文件。
- **建议**：补充到输出文件表。

### 4. 未文档化但学生应知的重要行为

#### 4.1 综合评分中的 `annualized_short_profit` 惩罚（多空模式）

源码 `src/quantfish/leaderboard/ranking.py:265-276` 对空头年化收益设有 100 权重的惩罚。这意味着：
- 多空策略如果空头侧盈利较高，会在 composite score 中被大幅扣分。
- 学生若以为“空头赚钱越多越好”，与排行榜逻辑相反。

#### 4.2 Long-only 下单只权重上限 5%

`max_position_weight: 0.05` 会在 `src/quantfish/backtest/simulator.py:128` 和 `src/quantfish/backtest/runner.py:109-113` 被 clip。等权买入 50 只时，每只理想权重 2%，通常不会触发；但若 `long_only_target_count` 调小或某只 score 极高，学生应知道存在 5% 上限。

#### 4.3 新股/次新股过滤（long-only）

`min_listing_days: 60` 会基于 `basic.company_info` 的 `listdt` 过滤上市不足 60 日的股票。做 long-only 时，打新/次新股策略会被系统排除。

#### 4.4 行业中性化实际作用

虽然文档描述准确，但**默认开启**意味着：
- 同一天同一行业内的 score 会被减去行业均值。
- 缺少行业分类的股票 score 被强制置 0（`src/quantfish/backtest/industry_neutralization.py:86`）。
- 如果学生用行业轮动思路，会被系统中和掉。

#### 4.5 提交冷却（cooldown）

`src/quantfish/submissions/service.py:68` 默认 `submission_cooldown_seconds: 2.0`。连续快速提交会收到“Please wait N seconds…”错误，文档未提及。

#### 4.6 结果 Stale 的判定条件

文档说“平台设置、执行环境指纹、引擎版本或数据集发生变更”会 stale。源码 `src/quantfish/submissions/staleness.py:105-123`、`src/quantfish/submissions/runners.py:147-153` 实际比对：
- config SHA256（注意 `scoring` 节被排除，但 `backtest`/`execution` 参与）
- hidden catalog SHA256
- engine version
- data track
- strategy file SHA256

重新提交同一文件**不会**改变 `strategy_sha256`，因此如果只有策略文件不变而平台配置/数据变化，re-submit 会刷新；但若只是策略文件修改而平台未变，新提交本身就不会 stale。

#### 4.7 `data.current` 在 `start == end` 时使用精确日期匹配

源码 `src/quantfish/data/bundle.py:170-178` 在 `start_date == end_date` 时走 `rows_for_date`，按主日期列精确匹配。对非日频表（如财报 `accper`），`data.current("firm.balance_sheet")` 通常返回空，因为当天不是报告期末。`firm-data-api-guide.md` 已提示不要用 `current` 读财报，这是文档做得好的地方。

#### 4.8 `limitstatus` 非 0 的禁止交易逻辑

文档 `06-backtest-and-metrics.md:165-175` 描述基本正确，但源码 `src/quantfish/backtest/simulator.py:107-126` 还综合了：
- `tradable`（成交量/额 > 0）
- `valid_close & valid_vwap`
- 涨跌停阈值 ±9.95%
- `limit_status`（面板列名支持 `limit_status`/`limitstatus`/`LimitStatus`/`Limitstatus`/`涨跌停状态`）

学生如果只在信号层把 `limitstatus != 0` 的股票 score 置 0，与执行层禁止交易是冗余但无害的。

#### 4.9 分组收益只统计“下一交易日可执行”股票

文档 `06-backtest-and-metrics.md:189`、`11-backtest-engine-explained.md:188` 描述与源码 `src/quantfish/backtest/runner.py:510-614` 一致，但很多学生没意识到：分组收益图 ≠ 真实组合收益，只是信号单调性检验。

#### 4.10 Web 启动脚本支持 `--mode verify`

文档 `08-submitting-on-web.md` 只提到 `scripts/start-quantfish.sh` 启动前后端。实际上该脚本还支持 `--mode setup|dev|prod|verify`（见脚本 `scripts/start-quantfish.sh:15-47`），其中 `verify` 会跑测试与构建。对教师/助教有用，可补充。

---

## Agent 1: Strategy execution and data API code path

**Scope:** `src/quantfish/factor_execution/strategy_execution.py`, `src/quantfish/data/bundle.py`, `examples/strategies/`, `docs/student/02-data-bundle-api.md`, `docs/student/04-generate-signals-deep-dive.md`.

### 1. `generate_signals` 实际能用的数据接口

平台最终传给策略函数的不是文档里写的裸 `DatedDataBundle`，而是一个包装对象 `StudentDataView`（`src/quantfish/factor_execution/strategy_execution.py:176-251`）。它实际暴露的方法：

| 方法 | 是否可用 | 说明 |
|---|---|---|
| `data.current(...)` | ✅ | 读绑定日期当天 |
| `data.load(...)` | ✅ | 读区间 |
| `data.history(...)` | ✅ | 读过去 N 天 |
| `data.latest(...)` | ✅ | 每只股票取最新一条 |
| `data.list_datasets()` | ✅ | 列数据集 |
| `data.describe(...)` | ✅ | 看元信息 |
| `data.path(...)` | ❌ | 不存在于 `StudentDataView` |
| `data.load_raw(...)` | ❌ | 不存在 |
| `data.at(...)` | ❌ | 不存在 |

### 2. 数据包 `DataBundle` / `DatedDataBundle` 实际提供的能力

`DataBundle` 加载 `data_catalog.json`（`bundle.py:52`），通过 `at(date)` 生成 `DatedDataBundle`（`bundle.py:108`）。核心行为：

- `current` = `load(start=date, end=date)`（`bundle.py:192-205`）
- `history` = 计算 `date - lookback_days` 后调 `load`（`bundle.py:207-229`）
- `latest` 按 `by` 列或 `spec.symbol_column` 分组取每组最后一条（`bundle.py:231-271`）
- `numeric_columns` 通过 `pd.to_numeric(..., errors="coerce")` 转换（`bundle.py:347-359`）
- 日期绑定检查：任何 `start` 或 `end` 大于绑定日期都会抛 `FutureDataAccessError`（`bundle.py:161-168`）
- 所有读取都会根据 `allowed_market_types` 过滤 `markettype` / `Markettype` / `MarketType` / `market_type` 列（`bundle.py:78-86`、`market_types.py:57-68`）

### 3. 文档与代码的明确不一致

#### 3.1 传给 `generate_signals` 的对象被包装过，能力比 `DatedDataBundle` 少

- 文档：`02-data-bundle-api.md:3` 和 `04-generate-signals-deep-dive.md:50` 把 `data` 描述为 `DatedDataBundle`。
- 代码：实际传入的是 `StudentDataView`（`strategy_execution.py:176-251`），它只代理了部分方法。
- 后果：学生在策略里写 `data.path(...)` 或 `data.load_raw(...)` 会 `AttributeError`。

#### 3.2 默认 silently 过滤市场类型，文档完全未提

- 代码：`DEFAULT_ALLOWED_MARKET_TYPES = (1, 4)`（`market_types.py:19`），`config/platform.yaml:40-42` 也是 `[1, 4]`。`DataBundle._load_raw_for_dated_access` 会按 `markettype` 类列过滤（`bundle.py:78-86`）。
- 文档：`02`/`04` 均未提及 `allowed_market_types`。
- 后果：学生 `data.current("stock.daily_returns")` 默认只返回上证 A 股（不含科创板）和深证 A 股（不含创业板）。创业板（16）、科创板（32）、B 股、北交所等会被悄悄剔除。若策略依赖完整股票池，结果会与预期不符。

#### 3.3 评分交易日由硬编码的 `stock.daily_returns` 推导，不是“每个交易日”

- 代码：`CANONICAL_PANEL_DATASET = "stock.daily_returns"`（`strategy_execution.py:17`），`_trading_dates` 取该表日期列在 `[data_start, scoring_end]` 范围内的唯一值（`strategy_execution.py:333-348`）。
- 文档：`04-generate-signals-deep-dive.md:17` 说“平台每天都会调用一次你的策略函数”。
- 后果：若 `stock.daily_returns` 缺少某些交易日，则这些日期不会生成信号；学生无法通过策略代码改变这个 canonical panel。

#### 3.4 `generate_signals` 参数检测只认位置参数 / 可变参数

- 代码：`_compile_generate_signals_call` 只统计 `POSITIONAL_ONLY` 和 `POSITIONAL_OR_KEYWORD` 参数（`strategy_execution.py:299-318`）。如果写成 `def generate_signals(data, *, date)`，`date` 是 keyword-only，平台会只传一个参数。
- 文档：`04-generate-signals-deep-dive.md:10-16` 只说明两参数和单参数两种写法，未提及 keyword-only。

#### 3.5 股票代码规范化会截断超过 6 位的代码

- 代码：`_normalize_code` 执行 `code.zfill(6)[-6:]`（`strategy_execution.py:391-399`）。
- 文档：`04-generate-signals-deep-dive.md:101` 只说“统一整理成六位字符串”，未说明长代码会被从右侧截断（例如 `"1234567"` → `"234567"`）。

#### 3.6 `history` 的额外约束未在文档中说明

- 代码：`start` 和 `lookback_days` 同时传入会抛 `ValueError`；`lookback_days` 为负也会抛 `ValueError`（`bundle.py:216-221`）。
- 文档：`02-data-bundle-api.md:105-133` 只说用 `lookback_days` 方便，未提这些限制。

#### 3.7 `FutureDataAccessError` 也会在 `start` 越界时触发

- 代码：`bundle.py:161-164` 对 `start_date > self.date` 也抛错。
- 文档：`02-data-bundle-api.md:249-280` 只展示了 `end` 越界的例子。

#### 3.8 静态/无日期表不受绑定日期限制

- 代码：若数据集 `primary_asof_column is None`，`load(...)` 返回整张表，`latest(...)` 也返回整张表（`bundle.py:155-157`、`bundle.py:241-246`）。
- 文档：`02-data-bundle-api.md` 强调“绑定日期之后的都是未来，不能读取”，但未说明该规则对没有主日期列的静态表不生效。

#### 3.9 `latest(by=None)` 的兜底行为文档描述不完整

- 代码：先取 `by or spec.symbol_column`；若数据集没有 symbol 列，则返回整张表的最新行（`bundle.py:239-246`）。
- 文档：`02-data-bundle-api.md:164` 说“会尝试用数据集中默认的股票代码列来分组”，未说明无 symbol 列时的全表 fallback。

### 4. 重要但未在文档中说明的平台行为

1. **默认市场过滤**：见 3.2。这是对学生影响最大的未记录行为。
2. **交易日历来自 `stock.daily_returns`**：见 3.3。学生应知道不是所有自然日都会被调用。
3. **策略里不能访问 `path` / `load_raw` / `at`**：只能使用 `StudentDataView` 代理的方法。
4. **代码规范化细节**：去除 `.0` 后缀、去空白、右截断到 6 位。
5. **CSV 损坏自动修复**：`bundle.py:362-467` 在 CSV 解析失败时会尝试 CSMAR 风格的字段合并修复，学生无感但可能影响边缘数据。
6. **空信号不报错**：若某天返回空 Series/DataFrame，平台只是不产生该行分数（`strategy_execution.py:353-354`），不会中断回测。
7. **`numeric_columns` 中列名必须存在**：会抛清楚 `KeyError`（`bundle.py:354-356`），这一点文档已说明，但值得一提。
8. **`execute_student_strategy` 使用缓存层 `CachedDataBundle`**（`strategy_execution.py:38-145`）：对策略结果无影响，但解释了为什么重复读取同一数据集很快。
9. **模块导入名是哈希生成的**（`strategy_execution.py:324`）：策略文件里的全局副作用会被执行，但不应依赖模块名。

### 5. 示例策略与文档的一致性

`examples/strategies/README.md` 和示例文件均只使用 `data.current` / `data.history` / `data.latest`，与 `StudentDataView` 暴露的接口一致，没有调用 `path` 或 `load_raw`。示例中也未提醒市场类型过滤，因此学生在复制示例到真实回测时可能忽略该过滤。

**结论**：文档在接口用法、返回值格式、`NaN` 与 `0` 的语义、未来数据保护等方面的描述与代码基本一致。最大的缺口是：**默认 `allowed_market_types=(1,4)` 的市场过滤、评分交易日历由 `stock.daily_returns` 唯一决定、以及 `generate_signals` 收到的是受限的 `StudentDataView` 而非完整 `DatedDataBundle`**。建议补充到 `02-data-bundle-api.md` 和 `04-generate-signals-deep-dive.md` 中，避免学生因股票池不完整或日期行为与预期不符而困惑。

---

## Agent 2: Submission flow

**Scope:** `src/quantfish/submissions/service.py`, `src/quantfish/submissions/routes.py`, `frontend/src/features/submissions/`, `docs/student/08-submitting-on-web.md`.

### 1. How a student actually submits

#### Backend entry points

- **`src/quantfish/submissions/routes.py`** `POST /api/submissions` (lines 59-109) accepts a multipart form with:
  - `team_name` + `password` **or** an existing participant session cookie.
  - `data_track` (`hidden_test` or `learning`).
  - `file` (`UploadFile`, required).
- The route resolves the data track through `ensure_public_data_track_enabled` (`src/quantfish/submissions/track_visibility.py:21-28`), which rejects `hidden_test` when `execution.hidden_test_enabled` is false.
- It then calls either:
  - `SubmissionService.submit_strategy()` (credentials path) at `service.py:82-104`, or
  - `SubmissionService.submit_strategy_for_team()` (session path) at `service.py:106-123`.

#### Submission service (`src/quantfish/submissions/service.py`)

`_submit_strategy_for_team()` (lines 133-169) does the following:
1. Loads a config snapshot and checks `execution.submissions_enabled` (lines 141-143; helper `_submissions_enabled` at 193-197).
2. Checks the team cohort’s `team_submissions_enabled` flag (lines 144-148).
3. Enforces a per-team submission cooldown (`_enforce_submission_cooldown`, lines 176-190; default `submission_cooldown_seconds=2.0`).
4. Generates a UUID, stores the strategy file, prepares a report directory, creates a `Submission` record with status `QUEUED`, and triggers the scoring dispatcher via `pump()`.

#### Frontend flow

- Feature is at `frontend/src/features/submissions/` (not `frontend/src/features/submit-strategy`; that path does not exist).
- `view.tsx` supports **two authentication modes**:
  - If a participant session exists (`/api/session` returns `authenticated: true`), the form hides the team/password fields and shows “Submitting as {team}” (lines 146-175).
  - Otherwise it shows team name and password inputs.
- The file input accepts `.py` only (line 179).
- Default selected track is **“learning”** (line 38), not hidden_test.
- After a successful submit it shows an accepted dialog, clears the file input, and blocks resubmission for **2 seconds** (lines 89-98, 274-279; constant `SUBMISSION_COOLDOWN_MS = 2000`).

### 2. Validation performed on the uploaded file

All validation happens server-side in `SubmissionStorage.validate_strategy_upload()` at `src/quantfish/submissions/storage.py:55-71`:

| Check | Error message | Docs claim | Match |
|---|---|---|---|
| Extension is `.py` (case-insensitive) | `strategy upload must be a Python .py file` | “必须是 `.py` 文件” | ✅ |
| Size ≤ `max_upload_bytes` (default `1_000_000`) | `strategy upload exceeds 1000000 bytes` | “不能超过 1 MB（1,000,000 字节）” | ✅ |
| Content is non-empty | `strategy upload cannot be empty` | “不能是空文件” | ✅ |
| Decodes as UTF-8 | `strategy upload must be UTF-8 text` | “必须使用 UTF-8 编码” | ✅ |
| Compiles with `compile(text, filename, "exec")` | `invalid Python strategy: {exc.msg}` | “必须能被 Python 正常编译” | ✅ |

**Important nuance:** the backend does **not** verify at upload time that the file defines `generate_signals` or that it returns a valid Series/DataFrame. Those checks occur later inside the scoring worker (`src/quantfish/factor_execution/strategy_execution.py:260-262, 387`). So the docs’ claim that non-compliance “会立刻报错，不会进入排队” is only true for the syntactic/upload checks, not for semantic strategy errors.

The frontend performs **no size, content, or encoding validation** before upload; it only restricts the file picker to `.py` files.

### 3. Status model mismatch: `stale` is not a status

`SubmissionStatus` in `src/quantfish/submissions/models.py:17-21` has only four values:

```python
QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
```

`stale` is **a computed boolean flag**, not a status. It is derived in:
- `routes.py` `_submission_stale()` (lines 350-362) from admin stale marks or zero-result staleness.
- `routes.py` `_submission_summary_payload()` (lines 303-313) exposes `stale` and `has_raw_error`.

**Docs mismatch:** `08-submitting-on-web.md` §5 lists `stale` alongside `queued`, `running`, `completed`, `failed` as one of “五种” submission statuses. This is inaccurate; stale submissions still carry a status of `completed` (or less commonly `failed`), plus `stale: true`.

### 4. Important undocumented or mismatched behavior

#### A. Hidden test track may be closed by default

- `config/platform.yaml` line 44 sets `hidden_test_enabled: false`.
- `src/quantfish/submissions/track_visibility.py:31-38` reads `config.execution.hidden_test_enabled`; when false, `public_data_tracks()` returns only `["learning"]` and the frontend hides the hidden_test option.
- The docs describe `hidden_test` as the formal/leaderboard track but do **not** mention that it can be disabled by the administrator or that it is disabled in the shipped default config.

#### B. Submission timeout default is 1200 s, not 120 s

- `08-submitting-on-web.md` §5 says: “默认 120 秒”.
- `config/platform.yaml` line 46: `submission_timeout_seconds: 1200`.
- `src/quantfish/submissions/runners.py:117-120` reads this value when `submission_timeout_enabled` is true.
- **Mismatch:** docs state 120 s; shipped config is 1200 s.

#### C. Per-team cooldown is undocumented

- Backend enforces `submission_cooldown_seconds` (default 2.0 s) in `service.py:176-190`.
- Frontend independently enforces a 2-second cooldown in `view.tsx:31, 89-98`.
- Docs do not mention this throttle.

#### D. Default selected track in UI is `learning`, not `hidden_test`

- Frontend `view.tsx:38` initializes `dataTrack` to `"learning"`.
- Docs §3 describe the two tracks but imply the student actively chooses; they do not state the default.

#### E. Two ways to authenticate

- Docs §3 describe filling in team name/password on the submit page.
- The platform also supports a participant session cookie (`/api/session/login`), after which the submit page hides credentials. This is not documented in §3, although the session login page exists at `frontend/src/features/session/`.

#### F. Saved filename is always `generate_signals.py`

- `storage.py:37` writes the uploaded bytes to `…/generate_signals.py`, discarding the original filename except for the extension check and `original_filename` metadata.
- Docs do not mention this; they only say the student’s file “必须定义策略函数 `generate_signals`”.

#### G. `generate_signals` signature flexibility is correct

- `src/quantfish/factor_execution/strategy_execution.py:299-318` accepts both `generate_signals(data, date)` and `generate_signals(data)` (and `*args`).
- Docs §8 check item 5 is accurate.

#### H. Composite score ingredients differ from docs

- Docs §7 list: total_return, sharpe, max_drawdown, average_year_return, worst_year_return, average_turnover.
- Actual scoring config (`config/platform.yaml:23-34` and `src/quantfish/web_app/response_models.py:283-294`) uses: `sharpe`, `annual_return`, `drawdown`, `turnover`, `short_profit`.
- With `long_only: true`, the short-profit component may be irrelevant; the docs predate the long-only A-share scoring changes (recent commits).

#### I. Long-only mode behavior is undocumented

- The recent commit history shows the backend now computes raw/active metrics (beta, tracking error, IR, active returns) for long-only mode.
- `08-submitting-on-web.md` does not describe long-only mode, active metrics, or the fact that the admin can toggle `long_only` and related settings.

#### J. Participant session cookie lifetime

- `src/quantfish/submissions/participant_session.py:16` sets `PARTICIPANT_SESSION_SECONDS = 7 * 24 * 60 * 60` (7 days).
- Undocumented in the student docs.

### 5. Summary table: docs vs. code

| Topic | Docs claim | Code reality | Severity |
|---|---|---|---|
| File checks at upload | “立刻报错，不会进入排队” | Syntactic checks are immediate; semantic `generate_signals` checks happen during scoring | Minor |
| `stale` as a status | Listed as one of five statuses | `stale` is a boolean flag; status remains `completed`/`failed` | Significant |
| Timeout default | 120 s | 1200 s in `config/platform.yaml` | Significant |
| Hidden test availability | Always available as formal track | Can be disabled via `hidden_test_enabled`; disabled by default | Significant |
| Submission cooldown | Not mentioned | 2 s enforced in backend and frontend | Minor |
| Default UI track | Not stated | `learning` | Minor |
| Auth methods | Team/password on submit page only | Also supports `/api/session/login` cookie | Minor |
| Saved filename | Student’s `.py` file | Renamed to `generate_signals.py` internally | Minor |
| Score components | total_return, sharpe, max_drawdown, average_year_return, worst_year_return, average_turnover | sharpe, annual_return, drawdown, turnover, short_profit; plus active metrics in long-only | Significant |
| Long-only / active metrics | Not documented | Present and scored | Significant |

### 6. Recommended doc updates for `docs/student/08-submitting-on-web.md`

1. Clarify that `stale` is a flag, not a status, and that stale rows still show as `completed`.
2. Correct the default submission timeout from 120 s to 1200 s (or note that it is configurable by the admin).
3. Explain that `hidden_test` may be closed by the administrator and that the default config has it closed.
4. Mention the 2-second submission cooldown.
5. Document the participant session login flow as an alternative to entering credentials on every submit.
6. Update the composite-score ingredient list to match the current scoring config.
7. Add a section on long-only mode and the active-return metrics if the course uses it.
8. Note that semantic strategy validation (`generate_signals` existence/return type) happens during scoring, not at upload time.

---

## Agent 3: Backtest engine and metrics

**Scope:** `src/quantfish/backtest/simulator.py`, `src/quantfish/backtest/metrics.py`, `src/quantfish/backtest/runner.py`, `docs/student/06-backtest-and-metrics.md`, `docs/student/11-backtest-engine-explained.md`.

### 1. 平台提交后的完整链路（`runner.py`）

学生上传 `strategy.py` 后，实际入口是 `run_student_backtest`（`runner.py:37`）。主要步骤如下：

1. **配置解析**：读取 `config["backtest"]` 与 `config["execution"]`。`data_start` 默认回退到 `scoring_start`，`scoring_start` 默认回退到 `data_start`（`runner.py:44-53`）。
2. **策略执行**：`execute_student_strategy` 逐日调用 `generate_signals`，返回 `date/code/score` 表格。
3. **数据面板**：从 `stock.daily_returns` 与 `factor_benchmark.adj_factor` 构建前复权面板（`front_close`、`front_vwap`、`tradable`、`limit_status` 等）。
4. **模式判断**：`execution.long_only` 为 `true` 时进入 `longonly`，否则 `longshort`（`runner.py:74`）。
5. **长仓可投资宇宙过滤**（仅 long-only）：剔除不可交易、价格/成交量无效、上市天数不足 `min_listing_days` 的标的（`runner.py:384-465`）。
6. **行业中性化**（可选）：在同日同行业内部去均值，缺失行业分类的股票分数置 `0`（`industry_neutralization.py:86`）。
7. **模拟回测**：`simulate_backtest` 计算日收益、持仓、交易成本等。
8. **分组收益**：`_calculate_group_returns` 计算可执行分组收益（`runner.py:510-614`）。
9. **截取评分期**：`_scoring_result` 把日收益、持仓、分组收益全部裁剪到 `[scoring_start, scoring_end]`（`runner.py:617-643`）。
10. **基准与指标**：
    - 先计算 **raw metrics**（原始组合收益指标）。
    - long-only 模式下，再用 `calculate_long_only_active_returns` 做 HS300 beta 调整，得到 `scored_daily_return`，并重新计算指标（`runner.py:129-165`）。
11. **图表与报告**：生成 `summary.csv`、`graph_data.json`、`performance_by_year.csv` 等（`report_writer.py:12-28`）。

### 2. 核心计算逻辑

#### 2.1 信号 → 权重（`panel.py:112-161`）

| 模式 | 公式 |
|---|---|
| `longshort` | `centered = score - mean(score)`，然后 `weight = centered / sum(|centered|)` |
| `longonly` + `rank_equal` | 选 `score > 0` 的股票，等权分配 |
| `longonly` + `score_proportional` | `clipped = max(score, 0)`，然后 `weight = clipped / sum(clipped)` |

- `top_k` / `long_only_target_count` 在归一化**之前**截断（`panel.py:143-145`）。
- `max_leverage`、`max_position_weight` 在 `simulator.py` 中应用（`simulator.py:128-129`）。

#### 2.2 日收益拆分（`simulator.py:131-155`）

```text
close_to_vwap = Σ previous_position * (front_vwap_today / front_close_yesterday - 1)
vwap_to_close = Σ current_position  * (front_close_today / front_vwap_today - 1)
portfolio_return = close_to_vwap + vwap_to_close - transaction_cost
```

- 若当天 VWAP 缺失但收盘价有效，持仓的 close→VWAP 段会用收盘价涨幅替代（`simulator.py:136-139`）。
- 若当天收盘价缺失，持仓继续保留，当日 PnL 记为 0，并记录 `stale_position_count` / `stale_gross_exposure`（`simulator.py:165-167`）。

#### 2.3 限制规则（`simulator.py:107-129`）

- **涨跌停**：`close_return > 0.0995` 禁止买入；`< -0.0995` 禁止卖出。`limit_status != 0` 也禁止交易。
- **流动性**：单票当日仓位变化上限 `max_participation_rate * dnvaltrd / capital`。
- **再平衡**：`_rescale_gross_exposure` **只缩不放**——当总敞口超过 `max_leverage` 时整体压缩，不会因部分股票受限而放大已成交仓位（`simulator.py:251-255`）。

#### 2.4 指标公式（`metrics.py`）

- `annual_return = all_return * 252 / trading_days`（`metrics.py:258-261`）。
- `sharpe = sqrt(252) * mean(returns) / std(returns, ddof=1)`（`metrics.py:264-270`）。
- `equity = 1 + returns.cumsum()`；`drawdown = equity / cummax(equity) - 1`，峰值基准 clamp 在 `1.0`（`equity.py:6-15`）。
- `max_drawdown = abs(min(drawdown))`（`metrics.py:51`）。
- `calmar = annual_return / max_drawdown`，若 `max_drawdown == 0` 则为 `None`（`metrics.py:78`）。
- `fitness = sharpe * sqrt(abs(annual_return) / max(average_turnover, 0.125))`（`metrics.py:313-314`）。
- `annualized_short_profit = max(annualized(short_total_return), 0)`（`metrics.py:56`）。

#### 2.5 Long-only 的 beta 调整（`active_returns.py:20-100`）

```text
beta = cov(strategy, benchmark) / var(benchmark)
active_return = strategy_return - beta * benchmark_return
tracking_error = std(active_return) * sqrt(252)
information_ratio = mean(active_return) * 252 / tracking_error
scored_daily_return = active_return
```

- 要求评分期内**每一天**都有基准数据，否则报错（`active_returns.py:63-64`）。

#### 2.6 年度表现表（`metrics.py:88-141`）

`performance_by_year.csv` 使用**另一套 legacy 公式**（`_legacy_sharpe`、`_legacy_drawdown`、`_legacy_fitness`、`_legacy_calmar`，`metrics.py:193-221`），与 `summary.csv` 的主指标不完全等价。例如 legacy drawdown 是绝对累计落差，而非相对回撤。

### 3. 文档与实际代码的不一致

#### 3.1 `all_return` 并不包含 Warmup 期

- **文档声称**（`06-backtest-and-metrics.md:206`）：`all_return` 覆盖整个回测区间（包含 warmup），`total_return` 仅覆盖评分期。
- **实际代码**：`run_student_backtest` 先调用 `_scoring_result` 把模拟结果裁剪到评分期（`runner.py:123`、`_scoring_result:617-643`），再传给 `calculate_backtest_metrics`。因此 `all_return` 与 `total_return` 都是评分期累计收益——`total_return` 在 `_summary_frame` 中直接被赋值为 `all_return`（`runner.py:648`）。
- **结论**：文档对 `all_return` 的描述错误。Warmup 期收益不进入 `summary.csv`，也不进入 `graph_data`（图表同样基于 `scoring_result` 构建）。

#### 3.2 Long-only 模式的评分指标来自 beta 调整后的主动收益

- **文档问题**：`06-backtest-and-metrics.md` 第 7 节列出的 `total_return`、`annual_return`、`sharpe`、`max_drawdown`、`calmar` 等指标，未说明在 long-only 模式下实际计算的是 **HS300 beta 调整后的主动收益**。
- **实际代码**：`runner.py:129-165` 在 long-only 模式下先用 `calculate_long_only_active_returns` 生成 `scored_daily_return`，再用它重新计算指标。测试也断言 `summary["sharpe"] ≈ summary["information_ratio"]`（`tests/test_backtest_runner.py:483`）。
- **后果**：学生在 long-only 下看到的 `sharpe` 实际上是信息比率（IR），而 `raw_sharpe`、`raw_total_return` 等字段才是原始组合表现。文档完全未提及这些 `raw_*` / `active_*` / `beta` / `tracking_error` / `information_ratio` 字段。

#### 3.3 配置默认值与文档描述不符

| 字段 | 文档描述 | `config/platform.yaml` 实际值 |
|---|---|---|
| `industry_neutralization` | 默认 `false`（`06-backtest-and-metrics.md:103`） | `true`（第 17 行） |
| `submission_timeout_seconds` | 默认 120 秒（`06-backtest-and-metrics.md:109`；`11-backtest-engine-explained.md:67`） | `1200`（第 46 行） |
| `submission_timeout_enabled` | 文档称当前设为 `false`（`11-backtest-engine-explained.md:67`） | `true`（第 47 行） |

#### 3.4 `max_position_weight` 仅在 long-only 模式下生效

- **文档问题**：`06-backtest-and-metrics.md` 配置表未列出 `max_position_weight`；`11-backtest-engine-explained.md` 也未明确限制。
- **实际代码**：`runner.py:109-113` 仅在 `mode == "longonly"` 时传入 `max_position_weight`，`longshort` 模式下始终为 `None`。

#### 3.5 主指标 Sharpe 在退化情况下返回 `0.0`，但年度表返回 `None`

- **文档问题**：未提及该差异。
- **实际代码**：`metrics.py:264-270` 的 `_sharpe` 在样本不足或标准差非正时返回 `0.0`；而 `_legacy_sharpe`（`metrics.py:193-199`）在同样情况下返回 `None`。这会影响 `summary.csv` 与 `performance_by_year.csv` 的可比性。

#### 3.6 `annualized_short_profit` 被 clamp 到零

- **文档问题**：`06-backtest-and-metrics.md` 与 `11-backtest-engine-explained.md` 均未列出或解释该字段。
- **实际代码**：`metrics.py:56` 取 `max(annualized_short_profit, 0.0)`，空头亏损时不会显示为负。

#### 3.7 `simulate_backtest` 默认 `long_only_weighting` 与平台默认相反

- **文档问题**：`06-backtest-and-metrics.md:100` 与 `config/platform.yaml:49` 均说明 long-only 默认 `rank_equal`。
- **实际代码**：`simulate_backtest` 函数签名默认是 `long_only_weighting="score_proportional"`（`simulator.py:38`）。由于 `runner.py` 总是显式传入配置值，生产链路不受影响，但独立调用函数时行为会与文档预期相反。

### 4. 重要但未在文档中说明的行为

#### 4.1 Long-only 可投资宇宙过滤

仅 long-only 模式下会执行额外过滤（`runner.py:384-465`）：
- 剔除 `tradable == False`、收盘价/VWAP/成交额非正的股票。
- 根据 `basic.company_info` 的上市日期剔除 `age_days < min_listing_days`（默认 60 天）的股票。
- 该过滤在**行业中性化之前**进行。

#### 4.2 行业中性化对 long-only 的影响

开启行业中性化后，缺失行业分类的股票分数会被置 `0`（`industry_neutralization.py:86`）。对 `rank_equal` 来说，`0` 分意味着不会被买入，可能直接空仓。

#### 4.3 分组收益只统计下一交易日可执行股票

`_calculate_group_returns`（`runner.py:510-614`）要求下一交易日同时具备有效 `front_close`、有效 `front_vwap`、`tradable == True`、`limit_status == 0`、且未触发 ±9.95% 阈值。不可执行的票从当日组内平均中剔除，而不是按 0% 收益稀释。

#### 4.4 基准数据必须完整覆盖 long-only 评分期

`calculate_long_only_active_returns` 要求评分期内每个交易日都有 HS300 基准收益，缺失任意一天即报错（`active_returns.py:63-64`）。

#### 4.5 图表中 `equity`/`drawdown` 与 `alpha` 的数据源不同

- `equity`、`drawdown`、`daily_pnl` 使用原始 `portfolio_return`（`graph.py:20-22`、`70-78`）。
- `alpha` 在 long-only 模式下使用 beta 调整后的 `active_return`（`graph.py:134-135`）。
- 学生在 long-only 下看到：summary 里的最大回撤/夏普是基于主动收益，但净值曲线/回撤图仍是原始组合。文档未说明这一区分。

#### 4.6 年度表现表使用独立公式

`performance_by_year.csv` 不是简单地把 `summary.csv` 按年拆分，而是使用 legacy 公式（`metrics.py:193-221`）。legacy drawdown 是绝对落差，legacy sharpe 在单一年份不足两天时返回 `None`。

#### 4.7 Stale position 的三种场景

1. 持仓股票当天收盘价缺失：PnL 记 0，记录 stale（`simulator.py:165-167`）。
2. 持仓股票 VWAP 缺失但收盘价有效：close→VWAP 段用收盘价收益率近似，VWAP→close 段为 0（`simulator.py:136-139`）。
3. 信号中的股票在面板中缺失（sparse panel）：已持仓股票继续保留，也记为 stale（`tests/test_backtest_simulator.py:744-808`）。

#### 4.8 价格策略硬编码

`runner.py:326-332` 强制校验：
- `price_policy` 必须为 `front_adjusted`
- `execution_price` 必须为 `vwap`
- `mark_price` 必须为 `close`

配置若写其他值会直接报错，文档仅说明默认行为。

### 5. 建议优先修正的文档点

1. **删除或修正 `all_return` 包含 warmup 的描述**；说明 warmup 期收益不进入任何学生可见的指标/图表。
2. **新增 long-only 评分机制说明**：beta 调整、主动收益、信息比率、以及 `summary.csv` 中 `raw_*` / `active_*` / `beta` / `tracking_error` / `information_ratio` 字段的含义。
3. **更新 `config/platform.yaml` 默认值描述**，包括 `industry_neutralization`、`submission_timeout_seconds`、`submission_timeout_enabled`。
4. **说明 `max_position_weight` 仅对 long-only 生效**。
5. **解释 `summary.csv` 与 `performance_by_year.csv` 公式不一致**，尤其是 drawdown 与 sharpe 的处理差异。
6. **说明 long-only 下图表 equity/drawdown 仍基于原始收益，而 alpha 基于主动收益**。
7. **补充 long-only 可投资宇宙过滤规则**（上市天数、流动性、市场类型等）。
