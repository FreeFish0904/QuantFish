# 第一个策略

这一章只做一件事：写出第一个能在 QuantFish 平台上运行的策略。

你暂时不需要理解仓位（持有股票的比例）、涨跌停、六位股票代码这些细节。第一天先记住一句话：

> **学生主要负责给每只股票算一个 `score`；平台负责把 `score` 变成真实回测。**

---

## 1. 新建一个策略文件

打开 VS Code、Cursor、PyCharm 或任意代码编辑器，新建文件并保存为：

```text
strategy.py
```

`.py` 表示这是 Python 文件。平台只接受 Python 策略文件，所以不要保存成 `strategy.txt` 或 `strategy.md`。

---

## 2. 复制最小策略

把下面这段代码复制到 `strategy.py`，然后保存文件（快捷键通常是 Ctrl+S 或 Cmd+S）：

```python
import pandas as pd


def generate_signals(data, date):
    """返回当前交易日的股票信号分数。"""
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    day_return = today["dretwd"]
    score = -day_return
    return pd.Series(score.values, index=today["stkcd"])
```

这就是一个完整策略。它每天做四步：

1. 读取当天日行情。
2. 取出当天日收益率 `dretwd`。
3. 给收益率前面加负号，得到短期反转分数。
4. 返回一个 `pd.Series`：index 是股票代码，值是 `score`。

---

## 3. 每一行在做什么

```python
import pandas as pd
```

导入 pandas。你可以把 pandas 理解成 Python 里的“表格工具”。

```python
def generate_signals(data, date):
```

定义策略函数。函数名必须叫 `generate_signals`，平台每天都会自动调用它。

`data` 是平台给你的日期绑定数据视图，只能看到当天及以前的数据。`date` 是当前交易日。

```python
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "dretwd"],
    numeric_columns=["dretwd"],
)
```

读取当天日行情，只要两列：

| 列名 | 含义 |
|---|---|
| `stkcd` | 股票代码 |
| `dretwd` | 当天日收益率 |

`numeric_columns=["dretwd"]` 会让平台把 `dretwd` 转成数字。如果这一列里有空值或异常文本，平台会把它变成 `NaN`。

你现在可以只读一列；等熟悉后，你可以在 `columns=[...]` 里加更多列，比如成交量、市值，来组合信号。

```python
day_return = today["dretwd"]
```

取出已经由平台转好的日收益率。在 QuantFish 里，`NaN` 表示“这只股票今天没有有效信号”。

```python
score = -day_return
```

这是策略想法本身。

如果某只股票当天跌了很多，`day_return` 是负数；加负号后，`score` 就变成正数。也就是说：**当天跌得越多，分数越高**。

这个思路叫“短期反转”：假设今天跌多了，明天可能会反弹一点。

```python
return pd.Series(score.values, index=today["stkcd"])
```

返回信号。Series 的 index 是股票代码，值是分数。

你不需要在这里手动把 `1.0` 改成 `"000001"`。平台会自动整理股票代码，也会把分数转换成仓位。

---

## 4. 把反转改成动量

如果你想让“涨得多的股票分数更高”，只要删掉负号：

```python
score = day_return
```

这就从“短期反转”变成了“短期动量”。

第一天最重要的练习就是改这一行，然后观察回测结果有什么变化。

---

## 5. 检查有没有语法错误

保存 `strategy.py` 后，在 QuantFish 项目根目录运行：

```bash
conda activate QuantFish
python -m py_compile strategy.py
```

如果没有任何输出，说明语法没有问题。

如果看到英文错误，通常是括号、引号或缩进写错了。回到代码里对照示例检查即可。

---

## 6. 运行你的第一个策略

语法检查通过后，你就可以运行回测了。最简单的方式是：

1. 把策略文件保存为项目根目录下的 `strategy.py`（和 `config/`、`docs/` 等文件夹同级）。
2. 参考 [在本地运行](./07-running-locally.md) 里的 `full_local_run.py` 示例，把其中的策略路径改成你自己的 `strategy.py`。
3. 运行脚本，观察终端输出的 `summary` 和生成的 `output/` 文件。

> 如果你现在只想快速验证平台是否跑通，也可以先不修改 `full_local_run.py`，直接运行原始示例。等确认环境正常后，再换成自己的 `strategy.py`。

---

## 7. 平台自动帮你做什么

你在第一个策略里没有写这些代码，但平台会处理：

- 把股票代码整理成六位字符串，例如 `1.0` -> `"000001"`。
- 把 `score` 转成多空（同时做多和做空）或只做多（只能买入）仓位。
- 在下一个交易日用官方执行价模拟交易。
- 处理涨跌停、不可交易、流动性不足等执行限制。
- 生成收益、回撤、换手、分组收益和排行榜指标。

平台会自动帮你做上面这些事，所以第一天不要急着写复杂代码。先把 `score` 的方向想清楚。

---

## 本章要点

- 策略文件必须是 `.py`。
- 平台寻找的函数名必须是 `generate_signals`。
- 第一个策略只需要读取 `stkcd` 和 `dretwd`。
- 读取数值字段时，用 `numeric_columns=[...]` 让平台把异常文本和空值转成 `NaN`。
- `score` 越高，表示你越看好这只股票。
- 用 `pd.Series(score.values, index=today["stkcd"])` 是最简返回方式。
- 股票代码整理、仓位计算、交易限制由平台处理。

相关代码示例：[hello_strategy.py](./examples/hello_strategy.py)

上一步：[开始之前](./00-before-you-start.md) | 下一步：[数据包接口](./02-data-bundle-api.md)
