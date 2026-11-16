# 在网页端提交策略

前面几章你已经学会了在本地运行回测。现在我们把策略提交到 QuantFish 网页平台，让它在平台服务器上跑一次正式评价，并查看排行榜。

## 1. 启动 Web 平台

网页端需要同时运行**后端**（负责计算、保存结果）和**前端**（负责页面显示）。

最简单的方法是使用项目自带的启动脚本。在终端里进入项目根目录，运行：

```bash
scripts/start-quantfish.sh
```

**这行在做什么**：这条命令会自动安装依赖、启动后端服务、启动前端页面，并把两个服务的地址打印在终端里。

如果脚本无法运行，也可以手动启动两步。

第一步，启动后端：

```bash
conda activate QuantFish
quantfish-web --host 0.0.0.0 --port 8000 --runtime-root runs/web_platform
```

**这行在做什么**：`quantfish-web` 是 QuantFish 的网页后端命令；`--port 8000` 表示后端监听 8000 端口；`--runtime-root` 指定提交文件和报告的存放位置。

第二步，再打开一个终端，启动前端：

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

**这行在做什么**：`npm run dev` 启动开发模式的前端页面；`--port 5173` 表示页面通过 5173 端口访问。

## 2. 打开浏览器

平台有两种运行模式，地址不同：

- **开发模式**（运行 `scripts/start-quantfish.sh` 或手动启动前端）：打开 <http://localhost:5173/>
- **生产模式**（运行 `scripts/start-quantfish.sh --mode prod`）：打开 <http://localhost:8000/>

注意：`localhost` 表示“你自己的电脑”，所以上面两个地址只能在运行平台的这台电脑上访问。如果平台部署在教室服务器上，老师可能会给你一个局域网地址，例如 `http://192.168.x.x:5173/`。用老师给的地址即可。

## 3. 提交页面操作

打开网页后，找到“提交策略”或“Submit”页面。页面上通常有以下几个输入框：

1. **队名（Team Name）**：输入你的队伍名称。队名由老师在后台创建，提交时必须和后台登记的一致。
2. **密码（Password）**：输入对应队伍的提交密码。
3. **数据轨道（Data Track）**：选择本次提交要使用的数据轨道。
   - **`hidden_test`**：正式 / 排行榜轨道。该轨道上的已完成结果会计入排行榜，用于最终排名。
   - **`learning`**：练习轨道。结果会出现在历史记录、对比页面和该轨道的诊断榜单中，方便你反复调试，但不计入以 `hidden_test` 为准的正式排名。
   - **`learning_1` / `learning_2` / `learning_3`**：历史学习窗口，分别覆盖 2010–2015、2015–2020、2020–2022。它们适合检查同一策略在不同时期是否稳定；2015 和 2020 会分别出现在相邻的两个窗口中。

   > **注意**：管理员可以随时关闭 `hidden_test` 轨道。默认配置里 `hidden_test` 是关闭的（`hidden_test_enabled: false`），所以页面上如果只显示学习类轨道，说明正式轨道尚未开放。此时请先用任一学习轨道练习，等老师通知排行榜轨道开放后再提交到 `hidden_test`。
4. **策略文件**：点击选择文件按钮，选中你写好的 `.py` 文件。这个文件里必须定义策略函数 `generate_signals`。
5. **提交按钮**：确认信息后点击提交。

提交成功后，页面会显示一个提交编号，例如 `#5`。这个编号方便你之后在历史记录里找到这次提交。

## 4. 文件必须满足的限制

平台收到文件后会先做检查。如果文件不符合要求，会立刻报错，不会进入排队。你需要注意以下几点：

- **必须是 `.py` 文件**：Python 源码文件，扩展名是小写的 `.py`。
- **必须使用 UTF-8 编码**：保存文件时请选择 UTF-8，避免出现中文乱码或无法解析。
- **大小不能超过 1 MB**：也就是 1,000,000 字节。策略文件通常只有几 KB，一般不会有问题。
- **不能是空文件**：文件里必须有内容。
- **必须能被 Python 正常编译**：如果文件里有语法错误，平台会提示 `invalid Python strategy`。

下面是一个最简单的合规文件示例，也就是我们在[第一个策略](./01-first-strategy.md)里见过的 `hello_strategy.py`：

```python
import pandas as pd


def generate_signals(data, date):
    # 读取当天股票代码和日收益率。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )

    # 构造短期反转分数：当天跌得越多，score 越高。
    # numeric_columns 已经让平台把异常文本和空值转成 NaN。
    score = -today["dretwd"]

    # Series 的 index 是股票代码，value 是 score。
    # 平台会自动整理股票代码，并把 score 转换成仓位。
    return pd.Series(score.values, index=today["stkcd"])
```

**这行在做什么**：这个文件只做了三件事——读取当天数据、给每只股票打一个分数、返回股票代码和分数。平台会在每个交易日自动调用这个函数，并负责代码规范化、仓位计算和交易限制。

## 5. 提交状态解释

提交后，你可以在“历史记录”或“History”页面看到每次提交的状态。状态只有以下四种：

- **`queued`（排队中）**：你的策略正在等待平台运行。前面有其他提交时需要排队。
- **`running`（运行中）**：平台正在读取数据、调用策略函数、计算回测结果。
- **`completed`（完成）**：回测已经跑完，可以点开查看详细结果。
- **`failed`（失败）**：运行过程中出现错误，例如策略函数返回格式不对、读取了未来数据、或者运行超时。点开展示的错误信息，对照[常见错误](./09-common-errors.md)排查。

除了上面的状态，每个提交还有一个 **`stale`（已失效）** 标志。它不是状态，而是一个附加的布尔标记：当 `completed` 的提交在平台配置、数据集、引擎版本或环境指纹发生变更后，可能会被标为 `stale: true`。失效行不能参与对比，也不能获得排行榜徽章；重新提交同一策略即可刷新为有效。

如果某个提交长时间停留在 `running`，可能是策略运行时间超过了平台设置的单次上限。当前配置默认启用 1200 秒超时（`submission_timeout_enabled: true`，`submission_timeout_seconds: 1200`），超时后会被标记为 `failed`。实际值由管理员在 `config/platform.yaml` 中设定，运行前可向老师确认。

## 6. 查看结果页

当状态变成 `completed` 后，点击提交编号进入结果页。结果页通常包含以下几部分：

- **KPI 卡片（关键绩效指标卡片）**：用几个大数字展示关键指标，例如总收益（`total_return`）、年化收益（`annual_return`）、夏普比率（`sharpe`）、最大回撤（`max_drawdown`）、胜率（`win_rate`）、平均换手率（`average_turnover`）等。
- **累计收益曲线**：一条折线图，展示每天收益按初始资金口径相加后的变化。曲线向上代表赚钱，向下代表亏损。
- **回撤图**：展示累计收益曲线从最高点回落的幅度，帮助你看清楚最差的连续亏损阶段。
- **分组收益**：平台会把股票按分数高低分成若干组，画出每组的平均收益。如果分数高的组收益也高，说明你的信号具有“单调性”。
- **分数细项**：展示综合评分（composite score）是如何由各个指标加权算出来的，例如收益、夏普、回撤各占多少分。

## 7. 查看排行榜

排行榜页面可以切换并比较每个数据轨道；正式排名以 **`hidden_test`（正式 / 排行榜）** 为准。`learning` 和三个历史学习窗口的榜单只用于练习诊断。默认情况下，每个轨道对每个队伍只取**最好的一次**提交。

排名依据是 **composite score（综合评分）**。当前配置使用的公式为：

```text
score = clamp(sharpe / 2.0, -1, 1) × 40
      + clamp(annual_return / 0.30, -1, 1) × 60
      - clamp(abs(max_drawdown) / 0.30, 0, 1) × 15
      - clamp(average_turnover / 3.0, 0, 1) × 5
      - clamp(annualized_short_profit / 0.30, 0, 1) × 100
```

其中：

- `sharpe`：夏普比率，目标值 `2.0`，权重 `40`。
- `annual_return`：年化收益，目标值 `0.30`（30%），权重 `60`。
- `max_drawdown`：最大回撤。取绝对值后与 `0.30` 比较，超过目标值会按权重 `15` 扣分。
- `average_turnover`：平均换手率。超过 `3.0` 会按权重 `5` 扣分。
- `annualized_short_profit`：年化空头收益。这是一个**权重 100 的惩罚项**，主要用于约束多空策略中的空头获利；long-only 策略通常没有空头收益或数值很小，惩罚可忽略。
- `clamp(x, lower, upper)` 表示把 `x` 限制在 `[lower, upper]` 区间内。

平台管理员可以在后台调整各项权重与目标值，所以不同课程或比赛的评分侧重点可能不一样。具体数值以运行平台时的 `config/platform.yaml` 为准。你可以点击自己的提交查看“分数细项”，了解每一项具体得了多少分。

## 8. 下载平台提供的模板与离线环境

平台提供以下下载入口（注意把 `localhost:8000` 换成你实际访问的后端地址）：

- <http://localhost:8000/api/downloads/starter-strategy.py>：一个价量动量 starter 模板，示例中已使用 `numeric_columns` 做自动类型强制，可以直接复制修改。
- <http://localhost:8000/api/downloads/quickstart.txt>：仍可通过该地址获取快速上手文字说明，但提交页面已不再显示“快速开始”按钮。
- <http://localhost:8000/api/downloads/learning-data.zip>：下载 `learning` 轨道的练习数据集和 `docs/student/` 学习文档。
- <http://localhost:8000/api/downloads/environment-options>：查看当前可用的平台环境选项（会列出 `macos-arm64`、`macos-x86_64`、`windows-x86_64` 等）。
- <http://localhost:8000/api/downloads/environment/macos-arm64.zip>：下载指定平台的离线运行环境。把 `macos-arm64` 换成你需要的平台标识，例如 `macos-x86_64` 或 `windows-x86_64`。

**如果你想在本地离线练习**，需要同时下载 `learning-data.zip` 和对应平台的 `environment-{platform}.zip`，解压到同一个文件夹后按 [环境包安装指南（离线版）](./00a-environment-kit.md) 运行即可。

下载 `starter-strategy.py` 后，可以把它重命名为 `strategy.py`。第一次可以只改合成 `score` 的那一行，观察回测结果如何变化。

提交前建议先做本地验证：

```bash
python -m py_compile strategy.py
```

**这行在做什么**：`python -m py_compile` 让 Python 只检查 `strategy.py` 的语法是否正确，不会真正运行策略。如果命令没有输出，说明语法检查通过。

更完整的本地验证脚本可以参考 [docs/student/examples/full_local_run.py](./examples/full_local_run.py)；也可以参考 [在本地运行](./07-running-locally.md)，把策略路径改成 `strategy.py`，用 `data_releases/learning` 跑一次回测。

## 9. 提交前检查清单

在点击提交之前，建议按顺序确认：

1. 本地已经用 `python -m py_compile strategy.py` 检查过语法。
2. 已经用 learning 数据本地跑过一次回测，确认策略能生成结果。
3. 文件扩展名是 `.py`。
4. 文件里没有 `TODO` 或未完成的占位符。
5. 策略函数签名是 `def generate_signals(data, date):` 或 `def generate_signals(data):`。
6. 返回的是 `pd.Series(score.values, index=stock_codes)`，或等价的 `code` / `score` DataFrame。
7. 队名和密码输入正确。
8. 确认选择了正确的数据轨道（`hidden_test` / `learning` / `learning_1` / `learning_2` / `learning_3`）。

确认无误后，就可以提交，等待平台跑出正式结果。

---

## 本章要点

- 使用 `scripts/start-quantfish.sh` 或手动命令启动前后端服务。
- 在浏览器打开对应地址后，进入提交页填写队名、密码、选择数据轨道并上传 `.py` 文件。
- 上传文件必须 ≤1 MB、UTF-8 编码、能正常编译且非空。
- 提交状态包括 queued、running、completed、failed；completed 或 failed 的提交还可能带有 `stale` 标志，stale 时重新提交即可刷新。
- 排行榜页面可切换每个轨道并按 composite score 查看每队最好的一次提交；只有 `hidden_test` 榜单用于正式排名，学习轨道榜单仅供诊断。

上一步：[在本地运行](./07-running-locally.md) | 下一步：[常见错误](./09-common-errors.md)
