# 在本地运行回测

前面几章，你已经学会了写策略函数 `generate_signals`，也知道了平台会怎么评价一个策略。本章我们把这两者连起来：在**你自己的电脑上**跑一次完整回测，并看懂生成的结果文件。

**回测**（backtest）的意思，是用历史数据模拟你的策略在过去会赚多少钱、亏多少钱。只有先在本地跑通，才适合上传到网页端参加正式评价。

## 环境检查清单

在运行脚本之前，请确认下面三件事已经完成。

### 1. 激活 QuantFish 环境

Conda 是一个管理 Python 环境的工具。QuantFish 项目有自己独立的环境，名字就叫 `QuantFish`。

打开终端，输入：

```bash
conda activate QuantFish
```

如果命令行前面出现 `(QuantFish)`，就表示环境已经激活。

### 2. 安装 QuantFish 包

需要在可编辑模式下安装 QuantFish 包，这样 Python 才能找到 `quantfish` 这个模块。

```bash
conda activate QuantFish
python -m pip install -e .
```

`-e .` 表示“安装当前目录下的包，并且不复制文件，改动会立即生效”。

### 3. 构建学习数据集

回测需要历史数据。学习数据集的路径是 `data_releases/learning`。如果该目录已经存在，就可以跳过构建命令。

如果还没有构建，确保已在 `QuantFish` 环境下，在项目根目录运行：

```bash
python -m quantfish.data.releases build-from-config --config config/platform.yaml
```

**这行在做什么**：`build-from-config` 会按照 `config/platform.yaml` 里的设置，生成完整学习数据、三个历史学习窗口和隐藏测试发布目录。第一次运行需要一些时间，请等待命令执行完毕（终端重新出现提示符即表示完成）。如果只需完整学习数据，可在命令末尾加 `--release learning`。

如果该目录已经存在，可以跳过上面命令，直接检查：

```bash
ls data_releases/learning
```

**这行在做什么：**

- `ls` 是列出目录内容的命令。
- `data_releases/learning` 是学习数据集的存放位置。

如果看到类似 `data_catalog.json`、`distribute`、`teacher` 这样的文件和文件夹，说明数据集已经准备好了。

## 完整本地回测脚本

下面这个脚本保存在 `docs/student/examples/full_local_run.py`，可以直接运行。它的作用是指定策略文件、加载平台配置、运行回测，并把结果写到 `output/student_doc_smoke` 目录。默认使用 `data_releases/learning` 做一次快速练习；如果你想模拟正式评分窗口，再按照后文切换到隐藏测试数据。

```python
# full_local_run.py
# 在本地运行一次完整回测并保存结果。
#
# 这个脚本不是策略文件，不需要提交到平台。
# 它的作用是：帮你在自己的电脑上先跑一遍 hello_strategy.py，
# 看看策略能不能正常生成结果。

import sys
from dataclasses import replace as dataclass_replace

from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.platform_config import ConfigRepository


# 1. 加载平台配置。
#    config/platform.yaml 里保存了回测日期、初始资金、执行价格等设置。
config = ConfigRepository("config/platform.yaml").load()

# 2. 本地学习数据覆盖 2010-01-02 至 2022-12-31（以 config/platform.yaml 的 learning_start/learning_end 为准）。
#    为了让刚下载数据的同学立刻看到结果，这里把评分窗口临时调到学习数据内，
#    并把 data_start 也改到评分窗口之前，避免从 2010 年开始加载全部学习数据。
#    这只影响本地冒烟测试，不会改变平台正式提交时的隐藏测试窗口。
new_backtest = dataclass_replace(
    config.backtest,
    data_start="2022-05-01",   # 避免从 2010-01-01 开始加载全部学习数据
    scoring_start="2022-06-01",
    scoring_end="2022-06-30",
)
config = dataclass_replace(config, backtest=new_backtest)

# 3. 运行回测。
#    第一个参数是策略文件路径。想测试自己的 strategy.py 时，改这里即可。
result = run_student_backtest(
    "docs/student/examples/hello_strategy.py",
    "data_releases/learning",
    config,
)

# 4. 把结果写入 output/student_doc_smoke。
#    里面会有 summary.csv、graph_data.json 等文件。
write_backtest_report(result, "output/student_doc_smoke")

# 5. 在终端打印核心指标，方便快速确认策略是否跑通。
print(result.summary)

# 6. 显式退出，避免某些后台线程让终端看起来像“卡住了”。
sys.exit(0)
```

**这行在做什么：**

- `from quantfish.platform_config import ConfigRepository`：从 QuantFish 包里导入读取配置的工具。
- `from quantfish.backtest import run_student_backtest`：导入真正执行回测的函数。
- `from quantfish.backtest.report_writer import write_backtest_report`：导入把结果写成文件的函数。
- `config = ConfigRepository("config/platform.yaml").load()`：读取项目根目录下的 `config/platform.yaml`，里面记录了回测的起止日期、初始资金、多空模式等参数。这个文件就是**平台配置文件**。
- `new_backtest = dataclass_replace(...)`：复制并修改回测配置。这里把 `data_start` 提前到 `2022-05-01`，并把评分窗口改到 `2022-06-01` 至 `2022-06-30`，让脚本在学习数据内快速跑完。正式提交时平台仍会使用 `config/platform.yaml` 里的默认窗口。
- `run_student_backtest(...)`：运行回测。三个参数分别是：
  - 策略文件路径；
  - 数据根目录（这里使用学习数据集 `"data_releases/learning"`）；
  - 平台配置对象。
- `write_backtest_report(result, "output/student_doc_smoke")`：把回测结果存到 `output/student_doc_smoke` 文件夹。如果文件夹不存在，函数会自动创建。
- `print(result.summary)`：在终端打印**指标摘要**。`summary` 是 `BacktestResult` 里存放核心指标（比如 total_return、sharpe）的字段。

> 如果你已经构建了 `data_releases/hidden_test` 数据，也可以把第二参数改回 `config.data_releases.hidden_output_root` 来进行官方评分窗口的模拟。

脚本里的 `"output/student_doc_smoke"` 可以改成任意你想要的输出目录，比如 `"output/my_first_run"`。

## 如何自定义输出目录

`write_backtest_report` 的第二个参数是输出目录。想把结果存到别处，例如 `output/my_results`，只需要改这个路径：

```python
write_backtest_report(result, "output/my_results")
```

**这行在做什么：**

- `"output/my_results"`：指定报告保存的文件夹。如果目录不存在，函数会自动创建。

## 切换到官方评分窗口数据

上面的主示例已经直接使用 `"data_releases/learning"`，所以只要构建过学习数据集就能直接运行。如果你后续想切换到官方评分窗口使用的隐藏数据集，把第二个参数改成配置文件里的隐藏测试数据路径即可：

```python
result = run_student_backtest(
    "docs/student/examples/hello_strategy.py",  # 策略文件路径
    config.data_releases.hidden_output_root,     # 隐藏测试数据根目录
    config,                                      # 平台配置对象
)
```

**这行在做什么：**

- `config.data_releases.hidden_output_root`：使用配置文件里指定的隐藏测试数据目录。需要先构建 `data_releases/hidden_test/`。
- 其余参数和前面示例保持一致。

## 怎么改成自己的策略

上面脚本运行的是示例策略 `hello_strategy.py`。要换成你自己的策略，只需要改第一个参数。

假设你自己写的策略文件叫 `strategy.py`，并且放在项目根目录下：

```python
result = run_student_backtest(
    "strategy.py",
    "data_releases/learning",
    config,
)
```

**这行在做什么：**

- `"strategy.py"`：改成你自己的策略文件路径。
- `"data_releases/learning"`：先用学习数据跑通自己的策略。
- `config`：继续使用前面已经临时调整到 learning 日期范围内的平台配置。

如果老师要求你模拟正式评分，再切换到隐藏测试数据：

```python
result = run_student_backtest(
    "strategy.py",
    config.data_releases.hidden_output_root,
    config,
)
```

你自己的 `strategy.py` 里必须定义 `generate_signals` 函数，格式要求和 `hello_strategy.py` 一样。

## 运行命令

确认当前终端已经位于项目根目录，然后运行下面两种命令之一：

如果你已经执行了 `conda activate QuantFish`，可以直接运行：

```bash
python docs/student/examples/full_local_run.py
```

如果你不想手动激活环境，也可以用：

```bash
conda run -n QuantFish python docs/student/examples/full_local_run.py
```

**这行在做什么：**

- `python docs/student/examples/full_local_run.py`：用 Python 运行刚才的脚本。
- `conda run -n QuantFish`：让命令在 QuantFish 环境里执行，即使你没有手动 `conda activate`。

运行成功后，终端会输出类似下面的一行指标表：

```text
   all_return  annual_return  ...  total_return  trading_days
0   -0.322626      -0.126304  ...     -0.322626           727
```

具体数字会因为策略不同而变化。只要没有报错，就说明回测已经跑完。

## 输出文件说明

运行结束后，`output/student_doc_smoke` 目录下会出现以下文件：

| 文件 | 格式 | 内容 |
|---|---|---|
| `summary.csv` | CSV | 所有核心指标的一行汇总表，可以直接用 Excel 打开。 |
| `daily_returns.parquet` | Parquet | 每天的组合收益率。 |
| `net_value.parquet` | Parquet | 每天的累计收益指数，等于 `1 + daily_return.cumsum()`。 |
| `turnover.parquet` | Parquet | 每天的换手率。 |
| `group_daily_returns.parquet` | Parquet | 按分数分组后，每组每天的收益。 |
| `performance_by_year.csv` | CSV | 按年份拆分的指标表，包含每年的收益、Sharpe、最大回撤、换手率、Calmar 等，以及一行 `all` 汇总。 |
| `graph_data.json` | JSON | 画图用的数据，网页端会用它展示累计收益曲线。 |
| `diagnostics.json` | JSON | 运行诊断信息，包括配置参数、交易日列表、信号行数等。 |

> 注意：`performance_by_year.csv` 里的 Sharpe、Calmar、Drawdown 使用的是早期实现公式，和 `summary.csv` 中的同名指标可能略有不同；正式评分以 `summary.csv` 为准。

**CSV** 是一种表格文件，用 Excel 或 WPS 可以直接打开。**Parquet** 是一种压缩的表格格式，Python 可以用 pandas 读取，Excel 默认打不开。**JSON** 是一种文本格式，用来存放配置和元数据。

如果你想用 Python 查看 `summary.csv`，可以写：

```python
import pandas as pd

summary = pd.read_csv("output/student_doc_smoke/summary.csv")
print(summary)
```

**这行在做什么：**

- `import pandas as pd`：导入 pandas，一个处理表格数据的 Python 库。
- `pd.read_csv(...)`：读取 CSV 文件，把它变成一个 DataFrame。
- `print(summary)`：把表格内容显示在终端。

Parquet 文件也可以用 pandas 读取。例如查看每天的组合收益率：

```python
import pandas as pd

daily_returns = pd.read_parquet("output/student_doc_smoke/daily_returns.parquet")
print(daily_returns.head())
```

**这行在做什么**：

- `pd.read_parquet(...)`：读取 Parquet 文件，把它变成 DataFrame。`.head()` 只显示前 5 行，避免一次输出太多。
- 其余行和读取 CSV 的示例含义相同。

## 最小验证清单

看到输出后，先检查下面四点，确认回测结果是合理的：

1. **Sharpe 不是 NaN**。如果 Sharpe 是 `NaN`（Not a Number，不是数字），通常说明策略在所有交易日都没有产生有效信号，或者收益序列全为零。

2. **total_return 在合理范围**。total_return 是策略在整个回测期的算术累计收益，也就是每天的收益率直接相加。它可以是正数也可以是负数，但不应该出现极其离谱的数值，例如 `1e20`。如果总收益看起来异常大或小，先检查策略是否读取了未来数据，或者分数是否被错误地放大了千万倍。

3. **turnover 不是极高**。average_turnover 是平均每日换手率。如果它长期大于 5 甚至 10，说明你的策略每天都在大幅调仓，模拟交易成本会吃掉大部分收益，实际中也不可持续。

4. **trading_days 不应为 0**。如果 `trading_days=0` 且所有指标都是 `0.0`，很可能是因为 `config/platform.yaml` 里的 scoring window 和学习数据的日期没有重叠。可以用单日期探针检查（参考 [`examples/load_current.py`](./examples/load_current.py)），或者在学习阶段临时把 scoring window 调整到 learning 数据范围内。

如果以上四项都正常，你就可以继续优化策略，或者准备上传到网页端。

### 如何临时调整评分窗口

如果你想在学习阶段不修改 `config/platform.yaml`，直接把 scoring window 改到 `data_releases/learning` 的日期范围内，可以在内存里复制并修改配置对象：

```python
from dataclasses import replace as dataclass_replace
from quantfish.platform_config import ConfigRepository

config = ConfigRepository("config/platform.yaml").load()
# 把评分窗口临时调整到 learning 数据范围内
new_backtest = dataclass_replace(
    config.backtest,
    scoring_start="2022-06-01",
    scoring_end="2022-06-30",
)
config = dataclass_replace(config, backtest=new_backtest)
```

`scoring_start`/`scoring_end` 可以根据 `data_releases/learning` 里的实际日期范围调整。修改后的 `config` 可以直接传给 `run_student_backtest`。

## 如何确认数据日期范围

如果你不确定学习数据集里有哪些日期，可以用下面的代码片段查看：

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")
df = data.load("stock.daily_returns", columns=["trddt"])
print(df["trddt"].min(), df["trddt"].max())
```

这段代码会输出 `stock.daily_returns` 数据集中 `trddt`（交易日）列的最小和最大日期，也就是当前学习发布包可用的日期范围。如果 `config/platform.yaml` 里的 `scoring_start` 或 `scoring_end` 超出了这个范围，回测时就会出现 `trading_days=0` 的情况。

## 如果报错怎么办

运行脚本时如果终端出现红色文字，不要慌。按照下面两步排查：

**第一步：先看 traceback 的最后一行。**

Python 报错时，会打印一段追踪信息（traceback）。最关键的信息通常在最下面，类似：

```text
StrategySignalError: student strategy must define callable generate_signals
```

或者：

```text
FutureDataAccessError: end date 2024-01-05 is after bound date 2024-01-04
```

最后一行已经告诉你错误类型和原因。

**第二步：对照常见错误清单。**

[常见错误](./09-common-errors.md) 那一章会把常见报错、原因和解决办法一一列出。根据最后一行的错误名，找到对应条目即可。

如果常见错误章节里没有你的报错，再往上翻看 traceback，找到出现 `.py` 文件路径和行号的位置，检查那行代码。

---

## 本章要点

- 运行前先激活 QuantFish 环境、安装包并确认 `data_releases/learning` 已构建。
- `full_local_run.py` 会加载配置、运行回测并把结果写入 `output/student_doc_smoke`。
- 把脚本中的策略路径改成自己的 `strategy.py` 即可运行自定义策略。
- 检查 Sharpe、total_return、average_turnover 是否在合理范围。
- 报错时先看 traceback 最后一行，再对照 [常见错误](./09-common-errors.md) 排查。

相关代码示例：[full_local_run.py](./examples/full_local_run.py)

上一步：[回测与评价指标](./06-backtest-and-metrics.md) | 下一步：[在网页端提交](./08-submitting-on-web.md)
