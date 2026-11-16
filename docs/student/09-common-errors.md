# 常见错误速查

本章是一本“错题本”。你在写策略、本地运行、或者网页端提交时，如果看到报错，可以直接按 `Ctrl+F`（或 `Command+F`）搜索报错信息，找到对应的解决办法。

在阅读本章之前，你需要知道几个词：

- **`DataFrame`**：pandas 里的“表格”，有行、有列，类似 Excel 工作表。
- **`Series`**：pandas 里的“一列数据”。
- **`generate_signals`**：策略函数，平台每天会调用它一次，问它“今天每只股票打几分”。
- **`data`**：日期绑定视图，你在策略函数里拿到它，只能看到“今天及今天之前”的数据。
- **六位股票代码**：比如 `000001`、`600000`，平台会自动把各种格式统一成 6 位字符串。
- **`score`**：信号分数，越高表示越看好这只股票。
- **`NaN`**：Not a Number 的缩写，表示“这里没数字”，在 pandas 里常用来表示缺失值。

---

## 平台报错类错误

下面这张表是“总览”，后面每个错误都有更详细的错误示例和修正示例。

| 错误现象 | 为什么会这样 | 怎么修 |
|---|---|---|
| `StrategySignalError: student strategy must define callable generate_signals` | 策略文件里没有名为 `generate_signals` 的函数，或者名字写错了、缩进不对、定义成了别的类型。 | 检查文件名是不是 `.py`，函数名是不是 `generate_signals`，并且写在文件最外层。 |
| `StrategySignalError: generate_signals must return a pandas Series or DataFrame of scores` | 策略函数返回了列表、字典、数字等，而不是 pandas 的 `DataFrame` 或 `Series`。 | 把返回值改成 `pd.DataFrame({"code": ..., "score": ...})` 或 `pd.Series`。 |
| `StrategySignalError: signals must include code and score columns` | 返回的 `DataFrame` 里没有 `code` 列或 `score` 列。 | 确保返回的表格包含且只包含 `code` 和 `score` 这两列。 |
| `StrategySignalError: signal scores must be numeric` | `score` 列里出现了无法转换成数字的内容（如文字、空字符串）。 | 读取平台数据时给数值字段加 `numeric_columns=[...]`，让异常文本和空值变成 `NaN`；显式返回 `NaN` 表示“无信号”，是被允许的。 |
| `StrategySignalError: duplicate signal codes: [...]` | 同一只股票在返回值里出现了两次或更多次。 | 检查是否有重复股票代码，去重后再返回。 |
| `FutureDataAccessError: end date ... is after bound date ...` | 策略函数试图读取当前交易日之后的数据。 | 不要写死未来的 `end`；用 `data.current`、`data.history`，或者让 `end` 默认为当前日期。 |
| `AttributeError: 'StudentDataView' object has no attribute 'bundle'` | 在策略函数里写了 `data.bundle.xxx`，但 `data` 并没有这个属性。 | 用 `data.current`、`data.load`、`data.history`、`data.latest` 读取数据。 |
| `strategy upload must be a Python .py file` | 网页端上传的文件不是 `.py` 结尾。 | 把策略文件重命名为 `.py` 文件再上传。 |
| `strategy upload exceeds 1000000 bytes` | 策略文件超过 1 MB（1 000 000 字节）。 | 删掉文件里的大段注释、嵌入数据、无关代码，只保留策略逻辑。 |
| Timeout / `submission_timeout_seconds` | 策略运行时间超过平台限制（默认 1200 秒）。 | 避免死循环、睡眠、耗时循环，改用 pandas 向量化计算。 |
| `Submissions are disabled` | 平台暂时关闭了提交功能，或 `hidden_test` 赛道未开启。 | 切换到 `learning` 赛道练习；正式赛道开放后老师/助教会通知。 |
| `Please wait N seconds before submitting again` | 两次提交间隔太短，触发了提交冷却。 | 等待倒计时结束后再提交；频繁提交不会加快评分。 |
| Long-only 回测报 “requires at least ... aligned benchmark observations” | 沪深 300 等基准数据在评分窗口内缺失或不足。 | 检查评分窗口是否包含有效交易日；确认数据发布里包含 `market.index_daily` 或 `TRD_Index`。 |
| Long-only 回测可投资股票池为空（`long_only_universe.final_rows: 0`） | 所有股票都被过滤掉（不交易、价格异常、上市天数不足）。 | 检查信号日期和 `stock.daily_returns` 日期是否对齐；确认 `min_listing_days` 设置。 |
| 运行显示 “Stale” / `staleResultNotice` | 该运行完成后，平台设置、数据发布、执行引擎或指纹发生了变更。 | 重新提交一次策略即可。 |
| 运行成功但 `summary.csv` 里所有指标都是 `0.0`，`trading_days=0` | 默认 scoring window 和学习数据日期不重叠。 | 参考 [`07-running-locally.md`](./07-running-locally.md) 里的“如何临时调整评分窗口”代码，把 `scoring_start`/`scoring_end` 改到学习数据范围内。 |

---

### 1. `StrategySignalError: student strategy must define callable generate_signals`

平台在导入你的策略文件时，没找到可以调用的 `generate_signals` 函数。

#### 导致错误的示例代码

```python
# wrong_name.py
import pandas as pd


def make_signals(data, date):  # 函数名写错了，不是 generate_signals
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "limitstatus"],
        numeric_columns=["dretwd", "limitstatus"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.strip()
    codes = codes.str.replace(r"\.0$", "", regex=True)
    codes = codes.str.zfill(6).str[-6:]

    score = -today["dretwd"]
    return pd.DataFrame({"code": codes, "score": score})
```

**这行在做什么：**

- `def make_signals(data, date):`：你写了一个函数，但平台只认名字叫 `generate_signals` 的函数，所以这个函数不会被调用。

#### 修正后的代码

```python
# correct_name.py
import pandas as pd


def generate_signals(data, date):  # 函数名必须完全一致
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "limitstatus"],
        numeric_columns=["dretwd", "limitstatus"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.strip()
    codes = codes.str.replace(r"\.0$", "", regex=True)
    codes = codes.str.zfill(6).str[-6:]

    score = -today["dretwd"]
    return pd.DataFrame({"code": codes, "score": score})
```

**这行在做什么：**

- `def generate_signals(data, date):`：函数名和参数都符合平台要求，平台才会在每个交易日调用它。

---

### 2. `StrategySignalError: generate_signals must return a pandas Series or DataFrame of scores`

策略函数返回了平台不认识的数据类型，比如 Python 列表、字典或单个数字。

#### 导致错误的示例代码

```python
# wrong_return_type.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
    )
    if today.empty:
        return []  # 返回了一个空列表，平台不认识

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    # 返回了一个 Python 字典，不是 DataFrame
    return {"codes": codes.tolist(), "scores": scores.tolist()}
```

**这行在做什么：**

- `return []`：当没有数据时返回空列表，平台期望返回空 `DataFrame`。
- `return {"codes": ..., "scores": ...}`：字典虽然看起来有代码和分数，但平台只接受 pandas 的表格或一列数据。

#### 修正后的代码

```python
# correct_return_type.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})  # 空表格

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})  # 平台要求的格式
```

**这行在做什么：**

- `return pd.DataFrame({"code": [], "score": []})`：没有数据时返回一个列名正确、但行数为 0 的空表格。
- `return pd.DataFrame({"code": codes, "score": scores})`：返回包含 `code` 和 `score` 两列的表格。

---

### 3. `StrategySignalError: signals must include code and score columns`

返回了 `DataFrame`，但列名不对，缺了 `code` 或 `score`。

#### 导致错误的示例代码

```python
# wrong_columns.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    # 列名用了中文，平台不认识
    return pd.DataFrame({"股票代码": codes, "分数": scores})
```

**这行在做什么：**

- `return pd.DataFrame({"股票代码": codes, "分数": scores})`：列名不是 `code` 和 `score`，平台找不到需要的列。

#### 修正后的代码

```python
# correct_columns.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `return pd.DataFrame({"code": codes, "score": scores})`：列名必须正好是 `code`（六位股票代码）和 `score`（信号分数）。

---

### 4. `StrategySignalError: signal scores must be numeric`

`score` 列里含有无法被强制转换为数字的值，例如文字或空字符串。

**重要区别**：`NaN` 是合法的，平台会把它理解为“这只股票今天没有信号”。如果分母为 0 导致 score 变成 `inf` 或 `-inf`，平台也会在后台把它整理成 `NaN`。只有当某个非空值无法被当作数字理解时（比如字符串 `"高"`），才会报这个错误。

#### 导致错误的示例代码

```python
# wrong_score_type.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]

    # 错误：把缺失值填成了字符串，导致 score 列里出现无法转成数字的内容
    score = today["dretwd"].fillna("N/A")

    return pd.DataFrame({"code": codes, "score": score})
```

**这行在做什么：**

- `score = today["dretwd"].fillna("N/A")`：把 `dretwd` 里的缺失值替换成字符串 `"N/A"`。返回的 `score` 列里混有 `"N/A"` 这类文字，平台无法把它转成数字，于是报错。

#### 修正后的代码

```python
# correct_score_type.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]

    # numeric_columns 已经把 dretwd 转成数字，无法转换的变成 NaN（表示无信号）
    score = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": score})
```

**这行在做什么：**

- `numeric_columns=["dretwd"]`：读取数据时就把 `dretwd` 转成数字；能转的转，转不了的变成 `NaN`。
- `score = -today["dretwd"]`：取负数，表示“跌得越多，分数越高”的短期反转思路。
- 返回结果里如果有 `NaN`，平台会认为这只股票当天没有信号，不会报错。

---

### 5. `StrategySignalError: duplicate signal codes: [...]`

同一只股票在返回值里出现了多次。

#### 导致错误的示例代码

```python
# duplicate_codes.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    # 把同一列复制了一份，导致每只股票出现两次
    duplicated_codes = pd.concat([codes, codes], ignore_index=True)
    duplicated_scores = pd.concat([scores, scores], ignore_index=True)

    return pd.DataFrame({"code": duplicated_codes, "score": duplicated_scores})
```

**这行在做什么：**

- `pd.concat([codes, codes], ignore_index=True)`：把代码列自己拼接了一遍，结果 `000001` 会出现两次，平台不知道用哪个分数。

#### 修正后的代码

```python
# unique_codes.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    # 按股票代码分组，只保留每组第一条记录
    result = pd.DataFrame({"code": codes, "score": scores}).drop_duplicates(subset=["code"])

    return result
```

**这行在做什么：**

- `.drop_duplicates(subset=["code"])`：把重复的股票代码去掉，保证每只股票只有一行。

---

### 6. `FutureDataAccessError: start date ... / end date ... is after bound date ...`

策略函数指定的日期范围越界，被平台拦住了。`start` 或 `end` 晚于当前绑定日期（bound date）都会触发这个错误。

#### 导致错误的示例代码

```python
# future_data.py
import pandas as pd


def generate_signals(data, date):
    # 错误：写了一个固定的未来日期
    past = data.load(
        "stock.daily_returns",
        start="2022-01-01",
        end="2099-12-31",  # 这里超过了当前交易日
        columns=["stkcd", "trddt", "dretwd"],
        numeric_columns=["dretwd"],
    )

    if past.empty:
        return pd.DataFrame({"code": [], "score": []})

    latest = past.groupby("stkcd").tail(1)
    codes = latest["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -latest["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `end="2099-12-31"`：写死了遥远的未来日期，平台发现这个日期比当前绑定日期还晚，就抛出 `FutureDataAccessError`。
- 同样，如果 `start` 写成了未来日期（例如 `start="2099-01-01"`），也会触发相同的错误。

#### 修正后的代码

```python
# bounded_data.py
import pandas as pd


def generate_signals(data, date):
    # 正确：不指定 end，默认只读到当前交易日
    past = data.load(
        "stock.daily_returns",
        start="2022-01-01",
        columns=["stkcd", "trddt", "dretwd"],
        numeric_columns=["dretwd"],
    )

    if past.empty:
        return pd.DataFrame({"code": [], "score": []})

    latest = past.groupby("stkcd").tail(1)
    codes = latest["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -latest["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- 不指定 `end` 时，`data.load` 会自动把结束日期设为当前交易日（也就是 bound date），因此不会读到未来数据。

---

### 7. `AttributeError: 'StudentDataView' object has no attribute 'bundle'`

在策略函数里错误地访问了 `data.bundle`。平台传给你的 `data` 是“日期绑定视图”，它只有 `current`、`load`、`history`、`latest` 等读取方法，没有 `bundle` 属性。

#### 导致错误的示例代码

```python
# access_bundle.py
import pandas as pd


def generate_signals(data, date):
    # 错误：data 没有 bundle 这个属性
    all_datasets = data.bundle.list_datasets()

    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `data.bundle.list_datasets()`：`data` 是**日期绑定视图**对象（内部实现为 `StudentDataView`），它为了保护未来数据，没有直接把底层 `DataBundle` 暴露出来。

#### 修正后的代码

```python
# use_data_methods.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- 用 `data.current(...)` 读取当前交易日的数据，不需要也不应该访问 `data.bundle`。

---

### 8. `strategy upload must be a Python .py file`

网页端只接受 Python 源代码文件，扩展名必须是 `.py`。

#### 导致错误的示例

你的文件叫 `我的策略.txt`。虽然文件里写的是 Python 代码，但扩展名是 `.txt`，平台会拒绝。

#### 修正后的示例

把文件重命名为 `my_strategy.py`，然后再上传。

---

### 9. `strategy upload exceeds 1000000 bytes`

策略文件大小超过 1 MB（1 000 000 字节）。常见原因是把大量数据、长注释、无关代码直接写进了策略文件。

#### 导致错误的示例

```python
# too_large.py
import pandas as pd


# 下面这种把几千行历史数据直接写在文件里的做法，会让文件迅速超过 1 MB
HUGE_LIST = [1, 2, 3]  # 实际文件里这里可能有几万行


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `HUGE_LIST = [...]`：把数据硬编码进策略文件会显著增加文件体积。平台只收代码，不收数据。

#### 修正后的示例

```python
# compact.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- 删掉文件里的嵌入数据和冗余注释，只保留真正需要运行的策略逻辑，文件大小就能控制在限制以内。

---

### 10. Timeout / `submission_timeout_seconds`

策略运行时间太长，超过了平台设置的超时时间（默认 1200 秒）。

#### 导致错误的示例代码

```python
# slow_strategy.py
import time
import pandas as pd


def generate_signals(data, date):
    # 错误：让策略故意等待 200 秒
    time.sleep(200)

    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `time.sleep(200)`：让程序暂停 200 秒，远超默认的 1200 秒超时限制。

#### 修正后的代码

```python
# fast_strategy.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- 去掉 `time.sleep` 等会拖慢运行的代码。如果计算量大，尽量用 pandas 的向量化运算，不要对每只股票写 Python `for` 循环。

---

### 11. 运行显示 “Stale” / `staleResultNotice`

一次运行明明已经成功了，但网页端给它打了 “Stale” 标签，或者弹出提示：

> Settings or data release changed after this run. Re-submit the strategy…

#### 为什么会这样

平台为了保证结果可比，会记录运行时的平台设置、数据发布版本、执行引擎版本以及策略指纹。如果运行完成后，这些条件中的任何一项发生了变化（例如老师更新了数据、平台升级了引擎、或者评分配置被调整），这次运行就会被标记为 **stale（已失效）**。

#### 怎么修

**重新提交一次策略**。提交新运行时会使用最新的设置和数据版本，只要新运行成功，就不会再是 stale 状态。

Stale 的运行只是不能参与 compare 和排行榜排名，你的策略代码本身没有问题，不需要改代码。

---

### 12. `Submissions are disabled` / `hidden test track is not currently open`

网页端提交策略时，平台返回 “Submissions are disabled” 或 “hidden test track is not currently open”。

#### 为什么会这样

平台管理员可以临时关闭提交功能，也可以单独关闭 `hidden_test`（排行榜/正式测评）赛道。默认配置里 `hidden_test_enabled` 为 `false`，因此刚部署的平台通常只有 `learning` 赛道可用。

相关配置在 `config/platform.yaml`：

- `execution.submissions_enabled: true/false`：总开关。
- `execution.hidden_test_enabled: true/false`：`hidden_test` 赛道开关。

#### 怎么修

- 如果看到 “Submissions are disabled”，说明提交总开关被关闭，等老师/助教开放后再试。
- 如果看到 “hidden test track is not currently open”，在提交时选择 **`learning`** 赛道继续练习。
- 不确定赛道状态时，优先使用 `learning`，并询问老师正式榜何时开放。

---

### 13. `Please wait N seconds before submitting again`

提交策略后，平台提示 “Please wait N seconds before submitting another strategy.”

#### 为什么会这样

平台为了防止刷提交，设置了提交冷却时间。同一支队伍两次提交之间必须间隔一定秒数（由平台后台配置控制，默认较短）。冷却时间从你**上一次提交**开始计算。

#### 怎么修

- 等提示里的倒计时结束后再点提交。
- 提交前先在本地用 [`07-running-locally.md`](./07-running-locally.md) 跑通，减少无意义的重复提交。
- 冷却时间内反复点击按钮不会加快评分，只会继续触发同样的提示。

---

### 14. Long-only 回测报 “requires at least ... aligned benchmark observations”

在 `long_only: true` 模式下运行回测，报错大致如下：

```text
long-only scoring requires at least 20 aligned benchmark observations; got 0
```

#### 为什么会这样

当轨道配置为 `long_only_benchmark: hs300`（例如 `hidden_test`）时，Long-only 的评分需要把组合收益和基准做对齐，计算 β、主动收益、跟踪误差和信息比率。如果评分窗口内没有可用的基准日收益数据，对齐后的观测数不足 `long_only_min_beta_observations`（默认 20），就会报这个错。历史学习轨道当前使用 `long_only_benchmark: none`，不会因为缺少指数而阻塞回测；指数仅在存在时用于结果图。

常见原因：

- 数据发布里缺少 `market.index_daily` 或 `TRD_Index` 表。
- `scoring_start` / `scoring_end` 设置成了基准数据没有的日期范围。
- 评分窗口太短，有效交易日不足 20 天。

#### 怎么修

1. 确认数据发布根目录里有沪深 300 指数日收益数据（`market.index_daily` 或 `TRD_Index`）。
2. 把 `scoring_start` / `scoring_end` 调整到学习数据范围内，参考 [`07-running-locally.md`](./07-running-locally.md) 的“如何临时调整评分窗口”。
3. 保证评分窗口至少覆盖 20 个有效交易日。

---

### 15. Long-only 可投资股票池为空

Long-only 回测没有报错，但 `summary.csv` 里所有指标都是 `0.0`，`trading_days=0`，诊断信息里 `long_only_universe.final_rows` 为 `0`。

#### 为什么会这样

Long-only 模式会在每天先过滤出“可投资宇宙”，只有满足以下条件的股票才会被纳入：

- 当天 `tradable` 为真；
- `front_vwap`、`front_close` 等价格字段有效且大于 0；
- 当天成交额 `dnvaltrd` 大于 0；
- 上市天数 ≥ `min_listing_days`（默认 60 天）。

如果某一天（或整个评分窗口）没有任何股票满足这些条件，股票池就是空的，回测自然没有交易。

常见原因：

- 信号日期和 `stock.daily_returns` 的交易日对不上。
- 评分窗口落在数据发布范围之外。
- 个别股票在 `basic.company_info` 中缺少有效上市日期，因此被排除。

如果启用了 `min_listing_days`，但整个 `basic.company_info` 数据集不可用、字段不完整或没有有效上市日期，平台会直接报错，不会让筛选规则静默失效。

#### 怎么修

1. 检查 `generate_signals` 返回的 `date` 是否和 `stock.daily_returns` 里的交易日一致。
2. 确认 `scoring_start` / `scoring_end` 在学习数据范围内。
3. 查看诊断输出里的 `long_only_universe`：
   - `non_tradable_rows` 高 → 很多股票当天不交易或价格异常；
   - `recent_listing_rows` 高 → 上市天数过滤掉了大部分股票；
   - `missing_listing_date_rows` 高 → 很多候选股票缺少有效上市日期，已被平台排除。
4. 如果是本地学习数据不完整，重新同步或生成数据发布。

---

## 不会报错但结果不对的陷阱

下面这些错误不会让你的策略崩溃，但会让回测结果看起来“怪怪的”。

### 陷阱 1：误解涨跌停股票

如果一只股票当天涨停或跌停（`limitstatus` 非 0），你往往买不到或卖不掉。

QuantFish 的回测执行层会处理这类交易限制：当平台发现当天交易受限，会跳过无法成交的调仓。所以入门策略不需要手动写 `limitstatus` 过滤。

你仍然可能想在信号层提前把这些股票设成中性，这属于进阶写法，不是第一天必做。

#### 入门写法

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    score = -today["dretwd"]
    return pd.Series(score.values, index=today["stkcd"])
```

**这行在做什么：**

- 策略只负责生成 `score`。
- 平台执行层负责判断哪些调仓真的能成交。

#### 进阶写法：在信号层提前设成中性

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "limitstatus"],
        numeric_columns=["dretwd", "limitstatus"],
    )
    score = -today["dretwd"]

    blocked = today["limitstatus"].ne(0)
    score = score.where(~blocked, 0.0)

    return pd.Series(score.values, index=today["stkcd"])
```

**这行在做什么：**

- `blocked = today["limitstatus"].ne(0)`：找出 `limitstatus` 不等于 0 的行。读取时的 `numeric_columns` 已经把异常值转成 `NaN`。
- `score = score.where(~blocked, 0.0)`：对交易受限的股票，把分数改成 `0.0`，相当于提前给中性信号。

---

### 陷阱 2：用当天的收盘价预测当天的收益

`data.current` 能读到当天数据，但当天收盘价 `clsprc` 是收盘后才知道的。如果你在开盘前做交易决策时用了它，就等于“偷看”了未来。

#### 有问题的代码

```python
# same_day_close.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "clsprc", "opnprc"],
        numeric_columns=["clsprc", "opnprc"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    close = today["clsprc"]
    open_ = today["opnprc"]

    # 用当天收盘价 / 当天开盘价 作为“预测”，这是未来数据
    score = close / open_ - 1.0

    return pd.DataFrame({"code": codes, "score": score})
```

**这行在做什么：**

- `score = close / open_ - 1.0`：用当天已经收盘的价格计算当天涨跌幅，再拿这个涨跌幅去打分，等于用结果预测自己。

#### 修正后的代码

```python
# previous_day_return.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "trddt", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    # 读过去几天的数据
    history = data.history(
        "stock.daily_returns",
        lookback_days=5,
        columns=["stkcd", "trddt", "dretwd"],
        numeric_columns=["dretwd"],
    )

    # 取每个股票最近一天的收益率（也就是上一个交易日的收益率）
    prev = history.groupby("stkcd").tail(1).copy()
    prev["stkcd"] = prev["stkcd"].astype(str).str.zfill(6).str[-6:]
    prev["prev_ret"] = prev["dretwd"]

    # 和今天的股票列表合并
    today["stkcd"] = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    merged = today[["stkcd"]].merge(prev[["stkcd", "prev_ret"]], on="stkcd", how="left")

    # 用上一个交易日的跌幅打分：跌得多，分数高（短期反转）
    score = -merged["prev_ret"].fillna(0.0)

    return pd.DataFrame({"code": merged["stkcd"], "score": score})
```

**这行在做什么：**

- `data.history(..., lookback_days=5)`：读取最近 5 天的数据，但截止到当前交易日（不含未来）。
- `history.groupby("stkcd").tail(1)`：对每只股票取最近一行，也就是“昨天”的数据。
- 用昨天的收益率打分，决策时不会用到当天收盘后才能知道的信息。

---

### 陷阱 3：NaN 没处理，导致某只股票没信号

pandas 里 `NaN` 表示“没有数字”。如果你的计算过程中出现了 `NaN`，平台会把它当成“这只股票今天没信号”。有时候这正是你想要的，但有时候是因为你忘了处理数据缺失，导致某只股票莫名其妙地没进入组合。

#### 有问题的代码

```python
# nan_not_handled.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    # 读过去 10 天的收盘价
    history = data.history(
        "stock.daily_returns",
        lookback_days=10,
        columns=["stkcd", "trddt", "clsprc"],
        numeric_columns=["clsprc"],
    )

    # 取每只股票最近 2 天
    latest = history.groupby("stkcd").tail(2).copy()
    latest["stkcd"] = latest["stkcd"].astype(str).str.zfill(6).str[-6:]
    latest["close"] = latest["clsprc"]

    # 计算最近一天的涨跌幅；每只股票的第一行会变成 NaN
    latest["return"] = latest.groupby("stkcd")["close"].pct_change()
    recent = latest.groupby("stkcd").tail(1)

    today["stkcd"] = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    merged = today[["stkcd"]].merge(recent[["stkcd", "return"]], on="stkcd", how="left")

    # NaN 的股票会被平台当成“无信号”
    score = merged["return"]

    return pd.DataFrame({"code": merged["stkcd"], "score": score})
```

**这行在做什么：**

- `latest.groupby("stkcd")["close"].pct_change()`：计算相对上一天的涨跌幅。因为每组只有 2 行，第一行没有“上一天”，所以会变成 `NaN`。
- `score = merged["return"]`：这些 `NaN` 会被平台当成“今天不交易这只股票”，而不是“分数为 0”。

#### 修正后的代码

```python
# nan_handled.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    history = data.history(
        "stock.daily_returns",
        lookback_days=10,
        columns=["stkcd", "trddt", "clsprc"],
        numeric_columns=["clsprc"],
    )

    latest = history.groupby("stkcd").tail(2).copy()
    latest["stkcd"] = latest["stkcd"].astype(str).str.zfill(6).str[-6:]
    latest["close"] = latest["clsprc"]

    latest["return"] = latest.groupby("stkcd")["close"].pct_change()
    recent = latest.groupby("stkcd").tail(1)

    today["stkcd"] = today["stkcd"].astype(str).str.zfill(6).str[-6:]
    merged = today[["stkcd"]].merge(recent[["stkcd", "return"]], on="stkcd", how="left")

    # 把 NaN 填成 0，让缺失值明确变成“不交易”
    score = merged["return"].fillna(0.0)

    return pd.DataFrame({"code": merged["stkcd"], "score": score})
```

**这行在做什么：**

- `merged["return"].fillna(0.0)`：把缺失的涨跌幅变成 `0.0`，这样这些股票会明确得到“不交易”的信号，而不是悄悄消失。

---

### 陷阱 4：所有股票的分数都一样

如果你给每只股票都打一样的分数，平台无法区分好坏，组合的权重会变得没有信息量，回测结果通常接近市场平均。

#### 有问题的代码

```python
# constant_score.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]

    # 每只股票的分数都是 1，没有区分度
    scores = pd.Series(1.0, index=today.index)

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `scores = pd.Series(1.0, index=today.index)`：所有行都是 `1.0`，平台看不出哪只股票更好。

#### 修正后的代码

```python
# varying_score.py
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    codes = today["stkcd"].astype(str).str.zfill(6).str[-6:]

    # 根据当天跌幅打分：跌得越多，分数越高
    scores = -today["dretwd"]

    return pd.DataFrame({"code": codes, "score": scores})
```

**这行在做什么：**

- `scores = -today["dretwd"]`：每只股票的分数根据实际数据变化，平台才能据此区分强弱。`numeric_columns` 已经让收益率列变成可计算的数字。

---

## 如果你遇到没列出来的错误怎么办

Python 报错时终端会打印一段追踪信息，英文叫 **traceback**。其中最下面一行通常是错误名字（例如 `FutureDataAccessError`），往上翻看还能找到出错文件和行号。

1. **把完整的报错信息复制下来**，回到本章按 `Ctrl+F`（或 `Command+F`）搜索错误名字。很多时候关键信息只有一两行。
2. **如果搜不到**，先检查是不是数据读取的问题，复习 [数据包接口](./02-data-bundle-api.md) 里的 `current`、`load`、`history`、`latest` 用法。
3. **如果数据读取没问题**，再检查 `generate_signals` 的返回值格式，复习 [策略函数深入解析](./04-generate-signals-deep-dive.md)。
4. **还是解决不了？** 把报错信息、你的策略文件、以及运行命令一起发给助教或老师，说明“我想实现什么效果”和“实际看到了什么报错”。

---

## 本章要点

- 常见平台报错有函数名错误、返回类型错误、缺少 `code`/`score` 列、非数字分数、重复代码、未来数据、超时、提交被禁用/冷却、long-only 基准数据不足，以及运行被标记为 stale。
- 文件类错误包括扩展名不是 `.py`、超过 1 MB、编码或编译失败。
- 不报错但结果不对的陷阱：忘记过滤涨跌停、用当天收盘价预测当天收益、NaN 处理不当、所有股票同分。
- 遇到未知错误时，先复制报错信息搜索本章，再检查数据读取和返回值格式。
- 仍无法解决时，把报错、策略文件和运行命令一起发给助教或老师。

上一步：[在网页端提交](./08-submitting-on-web.md) | 下一步：[Cookbook](./10-cookbook.md)
