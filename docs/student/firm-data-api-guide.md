# firm 财务报表数据与平台 API 使用指南

这是一份补充文档，不属于正式章节阅读顺序。它专门讲 `distribute/firm` 目录里的财务报表数据，以及怎样在 `generate_signals(data, date)` 里通过平台 API 调用这些数据。

如果你只想先跑通第一个策略，请先看 [第一个策略](./01-first-strategy.md) 和 [数据包接口](./02-data-bundle-api.md)。这份文档更适合已经会写基础 `score`，想把资产负债表、利润表、现金流量表放进策略里的同学。

---

## 1. `distribute/firm` 里面有什么

原始数据目录是：

```text
new_data/distribute/firm/
```

构建学习数据集后，学生策略实际读取的是：

```text
data_releases/learning/distribute/firm/
```

你在策略里不要直接写本地文件路径。平台已经把这些文件登记进数据目录，你只需要在 `generate_signals(data, date)` 里写数据集 ID，例如：

```python
balance = data.latest("firm.balance_sheet")
```

`firm` 目录里当前有四张可以通过平台 API 调用的表：

| 数据集 ID | 对应文件 | 表含义 | 学习数据行数 | 列数 | 日期列 | 股票代码列 |
|---|---|---|---:|---:|---|---|
| `firm.balance_sheet` | `distribute/firm/balance_sheet.parquet` | 资产负债表 | 420110 | 154 | `accper` | `stkcd` |
| `firm.income_statement` | `distribute/firm/income_statement.parquet` | 利润表 | 420091 | 81 | `accper` | `stkcd` |
| `firm.cashflow_direct` | `distribute/firm/cashflow_direct.parquet` | 现金流量表，直接法 | 420050 | 72 | `accper` | `stkcd` |
| `firm.cashflow_indirect` | `distribute/firm/cashflow_indirect.parquet` | 现金流量表，间接法 | 178958 | 35 | `accper` | `stkcd` |

旁边的 `财务报表 数据库说明书.pdf` 是 CSMAR 原始说明书。它解释字段编码和字段含义。平台里真正可读的列名，以 parquet 文件和 `data_catalog.json` 为准。

> **市场范围过滤提示**
>
> `firm` 财报表本身没有 `markettype` 列，平台默认的市场过滤不会直接作用于这四张表。平台默认交易 `[1, 4, 16, 32, 64]` 对应的沪深主板、创业板、科创板和北交所 A 股，这个范围来自 `config/platform.yaml` 的 `execution.allowed_market_types`。
>
> 因此，写策略时通常先把 `stock.daily_returns` 作为当天股票池（它已经按上述 A 股范围过滤），再把 `firm` 表合并上去。这样得到的投资范围才和平台回测一致。

### 1.1 原始目录和平台 API 的关系

可以把关系理解成三层：

| 层级 | 位置 | 作用 | 学生策略里要不要直接碰 |
|---|---|---|---|
| 原始分发目录 | `new_data/distribute/firm/` | 老师或平台构建数据集时的来源 | 不要 |
| 学习数据集 | `data_releases/learning/distribute/firm/` | 平台给学生回测使用的数据切片 | 一般不要直接碰 |
| 平台 API | `data.load/current/history/latest(...)` | `generate_signals` 里读取数据的正式入口 | 要 |

策略上传到网页端后，平台不会知道你电脑上的 `new_data` 路径。因此，策略代码应该只依赖 `data` 这个参数，而不是依赖本地绝对路径。

---

## 2. 四张 firm 表分别怎么理解

四张表的共同字段基本一致：

| 字段 | 含义 | 使用建议 |
|---|---|---|
| `stkcd` | 股票代码 | 与日行情的 `stkcd` 合并前，建议统一补成 6 位字符串 |
| `shortname` | 证券简称 | 只适合展示，通常不要参与打分 |
| `accper` | 统计截止日期，也就是财报报告期 | 平台用它做日期边界 |
| `typrep` | 报表类型 | `A` 通常表示合并报表，`B` 通常表示母公司报表 |
| `ifcorrect` | 是否发生差错更正 | 数据已经是修正后的版本，入门策略通常不用它 |
| `declaredate` | 差错更正披露日期 | 不是普通财报发布日期，不要把它当作年报/季报公告日 |

特别注意：平台当前对这四张表的日期限制使用 `accper`。也就是说，`data` 会保证你不能读取绑定日期之后的 `accper`，但它不是按普通公告发布日期过滤财报。学习平台的目标是先让大家安全使用日期绑定 API；如果你要做非常严格的公告日可得性研究，需要另外的数据表支持。

### 2.1 `firm.balance_sheet`：资产负债表

资产负债表描述一家公司在某个报告期末的资产、负债和所有者权益。它回答的问题是：公司现在拥有什么、欠了什么、净资产是多少。

常用字段：

| 字段 | 含义 | 常见用途 |
|---|---|---|
| `a001101000` | 货币资金 | 现金充足度 |
| `a001100000` | 流动资产合计 | 流动资产规模 |
| `a001123000` | 存货净额 | 存货压力、周转相关因子 |
| `a001212000` | 固定资产净额 | 资本密集度 |
| `a001000000` | 资产总计 | 分母，常用于 ROA、杠杆率 |
| `a002101000` | 短期借款 | 短期债务压力 |
| `a002100000` | 流动负债合计 | 短期负债规模 |
| `a002201000` | 长期借款 | 长期债务 |
| `a002000000` | 负债合计 | 资产负债率 |
| `a003105000` | 未分配利润 | 留存收益 |
| `a003100000` | 归属于母公司所有者权益合计 | 常用于 ROE 分母 |
| `a003000000` | 所有者权益合计 | 净资产规模 |
| `a004000000` | 负债与所有者权益总计 | 通常应接近资产总计 |

常见因子例子：

```python
debt_ratio = balance["a002000000"] / balance["a001000000"]
cash_ratio = balance["a001101000"] / balance["a001000000"]
```

### 2.2 `firm.income_statement`：利润表

利润表描述公司在一个会计期间赚了多少收入、付了多少成本费用、最后留下多少利润。它回答的问题是：公司这段时间经营得怎么样。

常用字段：

| 字段 | 含义 | 常见用途 |
|---|---|---|
| `b001100000` | 营业总收入 | 收入规模 |
| `b001101000` | 营业收入 | 非金融公司常用收入字段 |
| `b001200000` | 营业总成本 | 成本费用总量 |
| `b001201000` | 营业成本 | 毛利率相关 |
| `b001209000` | 销售费用 | 费用率 |
| `b001210000` | 管理费用 | 费用率 |
| `b001216000` | 研发费用 | 研发投入 |
| `b001211000` | 财务费用 | 融资成本 |
| `b001302000` | 投资收益 | 非经营性收益影响 |
| `b001300000` | 营业利润 | 主体经营利润 |
| `b001000000` | 利润总额 | 税前利润 |
| `b002000000` | 净利润 | 整体净利润 |
| `b002000101` | 归属于母公司所有者的净利润 | A 股策略里常用的净利润口径 |
| `b003000000` | 基本每股收益 | EPS |
| `b004000000` | 稀释每股收益 | 稀释 EPS |

常见因子例子：

```python
gross_margin = (income["b001101000"] - income["b001201000"]) / income["b001101000"]
net_margin = income["b002000101"] / income["b001101000"]
```

### 2.3 `firm.cashflow_direct`：现金流量表，直接法

直接法现金流量表按现金流入、现金流出列示经营活动、投资活动、筹资活动。它回答的问题是：现金是从哪里进来的，又流到哪里去了。

常用字段：

| 字段 | 含义 | 常见用途 |
|---|---|---|
| `c001001000` | 销售商品、提供劳务收到的现金 | 主营业务现金收入 |
| `c001013000` | 收到的其他与经营活动有关的现金 | 其他经营现金流入 |
| `c001100000` | 经营活动现金流入小计 | 经营流入合计 |
| `c001014000` | 购买商品、接受劳务支付的现金 | 主营业务现金支出 |
| `c001020000` | 支付给职工以及为职工支付的现金 | 人工现金支出 |
| `c001021000` | 支付的各项税费 | 税费现金支出 |
| `c001200000` | 经营活动现金流出小计 | 经营流出合计 |
| `c001000000` | 经营活动产生的现金流量净额 | 经营现金流净额 |
| `c002000000` | 投资活动产生的现金流量净额 | 投资现金流净额 |
| `c003000000` | 筹资活动产生的现金流量净额 | 筹资现金流净额 |
| `c005000000` | 现金及现金等价物净增加额 | 现金变化 |
| `c006000000` | 期末现金及现金等价物余额 | 期末现金余额 |

常见因子例子：

```python
cash_sales_ratio = cashflow["c001001000"] / income["b001101000"]
operating_cashflow_to_assets = cashflow["c001000000"] / balance["a001000000"]
```

### 2.4 `firm.cashflow_indirect`：现金流量表，间接法

间接法现金流量表从净利润出发，调整折旧、摊销、减值、营运资本变化等项目，推导经营活动现金流。它回答的问题是：利润为什么和经营现金流不一样。

常用字段：

| 字段 | 含义 | 常见用途 |
|---|---|---|
| `d000101000` | 净利润 | 利润起点 |
| `d000118000` | 信用减值损失 | 减值影响 |
| `d000102000` | 资产减值准备 | 减值影响 |
| `d000103000` | 固定资产折旧、油气资产折耗、生产性生物资产折旧 | 非现金费用 |
| `d000104000` | 无形资产摊销 | 非现金费用 |
| `d000105000` | 长期待摊费用摊销 | 非现金费用 |
| `d000113000` | 存货的减少 | 营运资本变化 |
| `d000114000` | 经营性应收项目的减少 | 营运资本变化 |
| `d000115000` | 经营性应付项目的增加 | 营运资本变化 |
| `d000100000` | 经营活动产生的现金流量净额 | 经营现金流净额 |
| `d000200000` | 现金及现金等价物净增加额 | 现金变化 |

在很多质量类因子里，`d000100000` 比净利润更有用，因为它更接近公司真实收到的现金。

---

## 3. 字段编码怎么读

财报字段名看起来像 `a001000000`、`b002000101`。这些字段来自 CSMAR 的编码规则。平台 parquet 里统一使用小写列名。

第一个字母可以快速判断它属于哪张表：

| 前缀 | 表 |
|---|---|
| `a...` | 资产负债表 |
| `b...` | 利润表 |
| `c...` | 现金流量表，直接法 |
| `d...` | 现金流量表，间接法 |

中间的行业标记可以帮助你判断字段是不是所有行业都适用：

| 标记 | 大致含义 |
|---|---|
| `00` | 一般行业也适用 |
| `0f` | 金融行业相关 |
| `0b` | 银行业相关 |
| `0d` | 证券业相关 |
| `0i` | 保险业相关 |

例如：

| 字段 | 读法 |
|---|---|
| `a001000000` | `a` 开头，资产负债表字段，含义是资产总计 |
| `b002000101` | `b` 开头，利润表字段，含义是归属于母公司所有者的净利润 |
| `c001000000` | `c` 开头，直接法现金流字段，含义是经营活动现金流净额 |
| `d000100000` | `d` 开头，间接法现金流字段，含义也是经营活动现金流净额 |

---

## 4. `generate_signals(data, date)` 里能调用哪些接口

平台每天会调用一次你的策略函数：

```python
def generate_signals(data, date):
    ...
```

`data` 是日期绑定数据视图，只能看到 `date` 当天以及之前的数据。对于 `firm` 表，平台用 `accper` 作为日期列。绑定日期之后的 `accper` 不能读取。

在学生策略里，`data` 可以调用这些接口：

| 接口 | 作用 | 适合 firm 表吗 | 示例 |
|---|---|---|---|
| `data.list_datasets()` | 列出所有数据集 ID | 可以，用来探索 | `data.list_datasets()` |
| `data.describe(dataset)` | 查看数据集元信息 | 可以，用来确认日期列、股票代码列 | `data.describe("firm.balance_sheet")` |
| `data.load(dataset, start=None, end=None, columns=None, numeric_columns=None)` | 读取一段时间内的数据 | 很适合，用于先筛 `typrep == "A"` 再取最新报告 | `data.load("firm.income_statement", columns=[...])` |
| `data.current(dataset, columns=None, numeric_columns=None)` | 只读绑定日期当天数据 | 不太适合 firm 表，因为财报不是日频表 | `data.current("stock.daily_returns", ...)` |
| `data.history(dataset, start=None, lookback_days=None, columns=None, numeric_columns=None)` | 读取过去一段历史 | 可以，用于最近几年财报窗口 | `data.history("firm.income_statement", lookback_days=800, ...)` |
| `data.latest(dataset, by=None, columns=None, numeric_columns=None)` | 截至当天，每组取最新一条 | 适合快速拿每只股票最近财报 | `data.latest("firm.balance_sheet", by="stkcd", ...)` |

`columns=[...]` 表示只读取你需要的列。`numeric_columns=[...]` 表示把这些列转成数字，无法转换的值会变成 `NaN`。财报表很宽，强烈建议每次只读需要的列。

### 4.1 `data.latest` 的快速用法

如果你只想拿每只股票截至当前日期最新一条资产负债表：

```python
balance = data.latest(
    "firm.balance_sheet",
    by="stkcd",
    columns=["stkcd", "accper", "typrep", "a001000000", "a002000000"],
    numeric_columns=["a001000000", "a002000000"],
)
```

这段代码的含义：

- `firm.balance_sheet`：读取资产负债表。
- `by="stkcd"`：每只股票分别取最新一条。
- `columns=[...]`：只要股票代码、报告期、报表类型、资产总计、负债合计。
- `numeric_columns=[...]`：把资产总计、负债合计转成数字。

### 4.2 更推荐的 consolidated 报表写法

`typrep` 里通常 `A` 表示合并报表，`B` 表示母公司报表。很多策略更希望用合并报表。由于同一报告期可能同时存在 `A` 和 `B`，想稳定使用 `A` 时，建议自己先过滤再取最新：

```python
import pandas as pd


def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]


def latest_report(data, dataset, columns, numeric_columns):
    frame = data.load(
        dataset,
        columns=columns,
        numeric_columns=numeric_columns,
    )
    frame = frame[frame["typrep"].eq("A")].copy()
    frame["code"] = normalize_code(frame["stkcd"])
    frame["accper"] = pd.to_datetime(frame["accper"], errors="coerce")
    frame = frame.dropna(subset=["code", "accper"])
    frame = frame.sort_values(["code", "accper"])
    return frame.groupby("code", as_index=False, sort=False).tail(1)
```

这个 helper 做了四件事：

1. 用平台 API 读取当前日期以前的财报。
2. 只保留合并报表 `typrep == "A"`。
3. 把股票代码统一成 6 位字符串。
4. 每只股票只保留最新报告期。

---

## 5. 在策略里使用 firm 数据的标准流程

财报表里包含很多已经退市或当天不可交易的股票。写策略时，建议先读当天日行情作为股票池，再把财报合并上去。

标准流程是：

1. 用 `data.current("stock.daily_returns", ...)` 读取当天可交易或可观察的股票池。
2. 用 `data.load(...)` 或 `data.latest(...)` 读取 firm 财报字段。
3. 把 firm 表里的 `stkcd` 规范成 6 位字符串。
4. 按 `stkcd` / `code` 合并到当天股票池。
5. 用财报字段算 `score`。
6. 返回 `pd.Series(score.values, index=today["stkcd"])`。

代码骨架：

```python
import pandas as pd


def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]


def latest_report(data, dataset, columns, numeric_columns):
    frame = data.load(dataset, columns=columns, numeric_columns=numeric_columns)
    frame = frame[frame["typrep"].eq("A")].copy()
    frame["code"] = normalize_code(frame["stkcd"])
    frame["accper"] = pd.to_datetime(frame["accper"], errors="coerce")
    frame = frame.dropna(subset=["code", "accper"])
    frame = frame.sort_values(["code", "accper"])
    return frame.groupby("code", as_index=False, sort=False).tail(1)


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd", "limitstatus"],
        numeric_columns=["dretwd", "dnvaltrd", "limitstatus"],
    )
    today = today.copy()
    today["code"] = normalize_code(today["stkcd"])

    balance = latest_report(
        data,
        "firm.balance_sheet",
        columns=["stkcd", "accper", "typrep", "a001000000", "a002000000"],
        numeric_columns=["a001000000", "a002000000"],
    )

    merged = today.merge(
        balance[["code", "a001000000", "a002000000"]],
        on="code",
        how="left",
    )

    debt_ratio = merged["a002000000"] / merged["a001000000"]
    score = -debt_ratio

    return pd.Series(score.values, index=today["stkcd"])
```

这个策略的意思是：资产负债率越低，分数越高。

---

## 6. 三个完整财报因子示例

下面的例子不是“标准答案”，只是展示 firm 表和平台 API 如何组合。你可以从这些例子开始改自己的 `score`。

### 6.1 低杠杆 + 高现金因子

用资产负债表：

```python
import pandas as pd


def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]


def latest_report(data, dataset, columns, numeric_columns):
    frame = data.load(dataset, columns=columns, numeric_columns=numeric_columns)
    frame = frame[frame["typrep"].eq("A")].copy()
    frame["code"] = normalize_code(frame["stkcd"])
    frame["accper"] = pd.to_datetime(frame["accper"], errors="coerce")
    frame = frame.dropna(subset=["code", "accper"])
    frame = frame.sort_values(["code", "accper"])
    return frame.groupby("code", as_index=False, sort=False).tail(1)


def generate_signals(data, date):
    today = data.current("stock.daily_returns", columns=["stkcd"])
    today = today.copy()
    today["code"] = normalize_code(today["stkcd"])

    balance = latest_report(
        data,
        "firm.balance_sheet",
        columns=[
            "stkcd",
            "accper",
            "typrep",
            "a001101000",  # 货币资金
            "a001000000",  # 资产总计
            "a002000000",  # 负债合计
        ],
        numeric_columns=["a001101000", "a001000000", "a002000000"],
    )

    merged = today.merge(
        balance[["code", "a001101000", "a001000000", "a002000000"]],
        on="code",
        how="left",
    )

    cash_ratio = merged["a001101000"] / merged["a001000000"]
    debt_ratio = merged["a002000000"] / merged["a001000000"]
    score = cash_ratio - debt_ratio

    return pd.Series(score.values, index=today["stkcd"])
```

### 6.2 盈利质量因子

用利润表、资产负债表和间接法现金流量表：

```python
import pandas as pd


def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]


def latest_report(data, dataset, columns, numeric_columns):
    frame = data.load(dataset, columns=columns, numeric_columns=numeric_columns)
    frame = frame[frame["typrep"].eq("A")].copy()
    frame["code"] = normalize_code(frame["stkcd"])
    frame["accper"] = pd.to_datetime(frame["accper"], errors="coerce")
    frame = frame.dropna(subset=["code", "accper"])
    frame = frame.sort_values(["code", "accper"])
    return frame.groupby("code", as_index=False, sort=False).tail(1)


def generate_signals(data, date):
    today = data.current("stock.daily_returns", columns=["stkcd"])
    today = today.copy()
    today["code"] = normalize_code(today["stkcd"])

    income = latest_report(
        data,
        "firm.income_statement",
        columns=[
            "stkcd",
            "accper",
            "typrep",
            "b001101000",  # 营业收入
            "b001201000",  # 营业成本
            "b002000101",  # 归母净利润
        ],
        numeric_columns=["b001101000", "b001201000", "b002000101"],
    )
    balance = latest_report(
        data,
        "firm.balance_sheet",
        columns=["stkcd", "accper", "typrep", "a001000000"],
        numeric_columns=["a001000000"],
    )
    cashflow = latest_report(
        data,
        "firm.cashflow_indirect",
        columns=["stkcd", "accper", "typrep", "d000100000"],
        numeric_columns=["d000100000"],
    )

    merged = today.merge(
        income[["code", "b001101000", "b001201000", "b002000101"]],
        on="code",
        how="left",
    )
    merged = merged.merge(balance[["code", "a001000000"]], on="code", how="left")
    merged = merged.merge(cashflow[["code", "d000100000"]], on="code", how="left")

    gross_margin = (merged["b001101000"] - merged["b001201000"]) / merged["b001101000"]
    roa = merged["b002000101"] / merged["a001000000"]
    cash_roa = merged["d000100000"] / merged["a001000000"]

    score = gross_margin + roa + cash_roa
    return pd.Series(score.values, index=today["stkcd"])
```

这个因子的直觉是：毛利率高、净利润相对资产高、经营现金流也相对资产高的公司，质量更好。

### 6.3 现金流覆盖利润因子

用利润表和直接法现金流量表：

```python
import pandas as pd


def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]


def latest_report(data, dataset, columns, numeric_columns):
    frame = data.load(dataset, columns=columns, numeric_columns=numeric_columns)
    frame = frame[frame["typrep"].eq("A")].copy()
    frame["code"] = normalize_code(frame["stkcd"])
    frame["accper"] = pd.to_datetime(frame["accper"], errors="coerce")
    frame = frame.dropna(subset=["code", "accper"])
    frame = frame.sort_values(["code", "accper"])
    return frame.groupby("code", as_index=False, sort=False).tail(1)


def generate_signals(data, date):
    today = data.current("stock.daily_returns", columns=["stkcd"])
    today = today.copy()
    today["code"] = normalize_code(today["stkcd"])

    income = latest_report(
        data,
        "firm.income_statement",
        columns=["stkcd", "accper", "typrep", "b002000101"],
        numeric_columns=["b002000101"],
    )
    cashflow = latest_report(
        data,
        "firm.cashflow_direct",
        columns=["stkcd", "accper", "typrep", "c001000000"],
        numeric_columns=["c001000000"],
    )

    merged = today.merge(income[["code", "b002000101"]], on="code", how="left")
    merged = merged.merge(cashflow[["code", "c001000000"]], on="code", how="left")

    score = merged["c001000000"] / merged["b002000101"]
    return pd.Series(score.values, index=today["stkcd"])
```

这个因子的直觉是：如果经营现金流能覆盖净利润，利润质量可能更扎实。实际使用时，还可以加上收入规模、成交额、涨跌停过滤等条件。

---

## 7. 常见坑

### 7.1 不要直接读 `new_data/distribute/firm`

错误写法：

```python
pd.read_parquet("new_data/distribute/firm/balance_sheet.parquet")
```

原因：

- 上传到网页端后，这个路径不一定存在。
- 这绕过了平台的日期绑定，容易读到未来数据。
- 这绕过了市场范围过滤和学习数据切片。

正确写法：

```python
balance = data.load("firm.balance_sheet", columns=[...], numeric_columns=[...])
```

### 7.2 firm 表不是日频表，不要优先用 `current`

`data.current("firm.balance_sheet")` 只会读取 `accper == date` 的行。大多数交易日并不是财报报告期末，所以结果经常是空表。

财报更常用：

```python
data.latest("firm.balance_sheet", by="stkcd", columns=[...])
```

或者：

```python
data.load("firm.balance_sheet", columns=[...])
```

再自己过滤 `typrep == "A"`、排序、取每只股票最新一条。

### 7.3 代码格式要统一

日行情里的 `stkcd` 通常已经是 `"000001"` 这样的字符串，firm 表里的 `stkcd` 可能读出来是数字。合并前建议统一：

```python
def normalize_code(series):
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6).str[-6:]
```

### 7.4 用 `numeric_columns`，少手写清洗

财报数值字段很多。只要字段后面要参与除法、加减、排序，就放进 `numeric_columns`：

```python
income = data.latest(
    "firm.income_statement",
    by="stkcd",
    columns=["stkcd", "accper", "b001101000", "b002000101"],
    numeric_columns=["b001101000", "b002000101"],
)
```

平台会把无法转换的值变成 `NaN`。返回的 `score` 里出现 `NaN` 是允许的，表示这只股票没有有效信号。

### 7.5 不要一次读取全部列

`firm.balance_sheet` 有 154 列。策略每天都要运行，如果每次都读全表，会很慢。

推荐：

```python
columns=["stkcd", "accper", "typrep", "a001000000", "a002000000"]
```

不推荐：

```python
data.load("firm.balance_sheet")
```

### 7.6 `accper` 是报告期，不等于交易日

`accper` 是类似 `2022-03-31`、`2022-06-30` 这样的财务报告期。它不是股票交易日期，也不是普通公告发布日期。用财报做日频策略时，通常要把“截至今天最新的报告期”合并到当天股票池上，而不是要求 `accper` 等于当天。

---

## 8. 如何在本地探索所有字段

在策略文件里不要做大量探索。探索适合放在临时 notebook 或临时脚本中。

查看四张 firm 表的元信息：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")

for name in [
    "firm.balance_sheet",
    "firm.income_statement",
    "firm.cashflow_direct",
    "firm.cashflow_indirect",
]:
    spec = bundle.describe(name)
    print(name)
    print("path:", spec.relative_path)
    print("date:", spec.primary_asof_column)
    print("symbol:", spec.symbol_column)
    print("rows:", spec.row_count)
```

查看实际 parquet 列名：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

sample = data.load(
    "firm.balance_sheet",
    columns=["stkcd", "accper", "typrep", "a001000000", "a002000000"],
    numeric_columns=["a001000000", "a002000000"],
)

print(sample.head())
print(sample.dtypes)
```

如果你想完整看某张表所有列，可以在本地研究脚本里这样做：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
path = bundle.path("firm.balance_sheet")

print(path)
```

然后用 pandas 或其他工具检查这个 parquet 文件。上传策略时不要使用 `bundle.path(...)` 或本地文件路径；上传策略只应该使用 `data.load/current/history/latest`。

---

## 9. 速查表

### 9.1 想要什么数据，用哪张表

| 你想要 | 数据集 |
|---|---|
| 资产、负债、所有者权益 | `firm.balance_sheet` |
| 收入、成本、费用、利润、EPS | `firm.income_statement` |
| 经营/投资/筹资现金流入和流出 | `firm.cashflow_direct` |
| 从净利润调整到经营现金流 | `firm.cashflow_indirect` |

### 9.2 常见财务因子怎么取字段

| 因子想法 | 需要字段 | 可能公式 |
|---|---|---|
| 资产负债率 | `a002000000`, `a001000000` | `负债合计 / 资产总计` |
| 现金资产比 | `a001101000`, `a001000000` | `货币资金 / 资产总计` |
| ROA | `b002000101`, `a001000000` | `归母净利润 / 资产总计` |
| 毛利率 | `b001101000`, `b001201000` | `(营业收入 - 营业成本) / 营业收入` |
| 净利率 | `b002000101`, `b001101000` | `归母净利润 / 营业收入` |
| 经营现金流资产比 | `c001000000` 或 `d000100000`, `a001000000` | `经营现金流净额 / 资产总计` |
| 现金流利润覆盖 | `c001000000` 或 `d000100000`, `b002000101` | `经营现金流净额 / 归母净利润` |

### 9.3 firm 表最常用 API

| 目标 | 推荐接口 |
|---|---|
| 每只股票最新财报 | `data.latest("firm.balance_sheet", by="stkcd", ...)` |
| 只用合并报表 `A` | `data.load(...)` 后过滤 `typrep == "A"`，再按 `stkcd` 取最新 |
| 取最近两年财报 | `data.history("firm.income_statement", lookback_days=800, ...)` |
| 和当天股票池合并 | 先 `data.current("stock.daily_returns", ...)`，再 `merge` |
| 查看平台有哪些表 | `data.list_datasets()` |
| 查看表的日期列、代码列 | `data.describe("firm.balance_sheet")` |

---

## 10. 最重要的记忆点

- `firm` 目录有四张财报表：资产负债表、利润表、直接法现金流量表、间接法现金流量表。
- 策略里不要直接读取 `new_data/distribute/firm`，要通过 `data.load/current/history/latest`。
- firm 表的日期边界是 `accper`，它是报告期，不是交易日。
- firm 表的股票代码合并前建议统一成 6 位字符串。
- `typrep == "A"` 通常是合并报表，很多策略优先使用它。
- 只读需要的列，并把参与计算的列放进 `numeric_columns`。
- 财报表不是日频表，最常见用法是“取截至当天最新报告，再合并到当天股票池”。
- `generate_signals` 最后返回 `pd.Series(score.values, index=today["stkcd"])` 就可以交给平台处理。
