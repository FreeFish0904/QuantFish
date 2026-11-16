# 开始之前

欢迎来到 QuantFish。

一句话说清楚 QuantFish 是做什么的：**你写一个 Python 函数，平台用历史数据帮你模拟交易、计算分数。**

你现在不需要懂投资，也不需要懂编程。这一章只帮你准备好电脑环境，并弄清楚接下来会发生什么。

---

## QuantFish 的流程长什么样

你可以把 QuantFish 理解成一个“自动阅卷老师”：

```text
你写一个叫 strategy.py 的文件
           ↓
把它上传到平台，或者在本地运行
           ↓
平台会在每个交易日调用你文件里的 generate_signals 函数
           ↓
平台根据函数返回的分数买卖股票，并给出收益曲线和评价指标
           ↓
最后你可以看到自己的分数，并和别人比较排行榜
```

`generate_signals` 是 QuantFish 的策略函数。你现在只需要知道：

- 每个交易日平台都会问它“今天你看好哪些股票？”。
- 它要回答一个分数列表；分数越高，表示越看好这只股票。
- 平台把这些分数变成买卖决策后，会画出**收益曲线**（就是“如果你的策略真的按这个信号交易，净值会怎么变化”的图）。
- 平台还会给出**评价指标**，例如赚了多少、风险大不大。

---

## 你需要准备什么

你的电脑需要满足以下条件：

1. 能运行 Conda（一个管理 Python 环境的工具）。
2. 有一个能编辑文本的工具（推荐 VS Code 或 Cursor；Windows 自带的记事本也可以）。
3. 大约几分钟的等待时间，用来安装环境和下载数据。

如果你还没有安装 Conda，先去官网下载 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 [Anaconda](https://www.anaconda.com/download) 并安装。安装过程中全部点“下一步”即可。

---

## Python 是什么

Python 是一种编程语言，也是 QuantFish 使用的语言。

在 QuantFish 里，你只需要写一个 `.py` 文件（例如 `strategy.py`），里面包含一个 `generate_signals` 函数。`.py` 就是 Python 文件的扩展名。

你不需要在这一章学会 Python 的全部内容。我们的方法是：**先照抄示例，再慢慢改数字、改条件、试自己的想法。** 就像先学会用微波炉加热饭菜，再学做菜一样。

---

## 安装 QuantFish 的 Conda 环境

Conda 环境是一个独立的“工作间”。它把 QuantFish 需要的 Python 版本和各种依赖包都装在一起，不会和你电脑上的其他 Python 项目互相干扰。

打开终端（macOS 用“终端”，Windows 用“Anaconda Prompt”或“命令提示符”），进入 QuantFish 项目所在的文件夹，然后依次运行下面三行命令。

```bash
conda env create -f environment.yml
conda activate QuantFish
python --version
```

**这行在做什么：**

- `conda env create -f environment.yml`：根据项目根目录下的 `environment.yml` 文件，自动创建一个名字叫 `QuantFish` 的环境，并安装所需的 Python 版本和依赖包。第一次运行可能需要几分钟，请耐心等待。
- `conda activate QuantFish`：激活 `QuantFish` 环境。激活后，终端提示符前面通常会显示 `(QuantFish)`，表示你现在处于这个环境中。
- `python --version`：检查当前使用的 Python 版本。你应该能看到类似 `Python 3.12.x` 的输出。

如果 `python --version` 显示的不是 3.12，说明环境没有激活成功，请重新运行 `conda activate QuantFish`。

---

## 安装 QuantFish 包

QuantFish 本身也是 Python 的一个包。你需要用可编辑模式安装它，这样你修改代码后不需要重新安装。

确保你已经激活了 `QuantFish` 环境，然后在项目根目录运行：

```bash
python -m pip install -e .
```

**这行在做什么：**

- `python -m pip`：用 Python 自带的包管理工具 `pip`。
- `install -e .`：以可编辑模式安装当前目录（`.`）里的 QuantFish 包。安装成功后，你就可以在 Python 代码里写 `import quantfish` 了。

---

## 构建学习数据集

QuantFish 需要历史数据才能运行回测。项目里已经配好了学习用的数据集，你只需要运行一条命令来生成它。

确保仍在 `QuantFish` 环境下，在项目根目录运行：

```bash
python -m quantfish.data.releases build-from-config --config config/platform.yaml
```

运行过程中终端会显示构建进度，请耐心等待，直到命令行提示符重新出现。

构建完成后，你会看到 `data_releases/learning/`、三个 `learning_1` / `learning_2` / `learning_3` 历史窗口，以及 `data_releases/hidden_test/`；如果只用到完整学习数据，后续可以只关注 `data_releases/learning/`。
如果你现在只想学习写法，可以暂时忽略 `data_releases/hidden_test/`；后续本地练习只需要 `data_releases/learning/` 里的数据。

**这行在做什么：**

- `python -m quantfish.data.releases`：运行 QuantFish 内部负责数据发布的模块。
- `build-from-config`：告诉它“按照配置文件来构建数据集”。
- `--config config/platform.yaml`：指定配置文件路径为 `config/platform.yaml`。这个文件里写了数据从哪来、覆盖哪些日期等参数。

运行成功后，你会在项目根目录下看到一个叫 `data_releases/learning/` 的文件夹。这个文件夹就是学习数据集，以后的策略都会从里面读取数据。

> **注意：** 如果这一步运行时间很长（几分钟到十几分钟），请不要关闭终端窗口，等待命令完成即可。

---

## 检查学习数据集是否生成成功

打开文件管理器，进入 `data_releases/learning/` 文件夹，确认里面至少包含以下内容：

- `data_catalog.json`：数据目录文件，记录了有哪些数据集、每个数据集有哪些字段。
- `distribute/`：核心数据目录，里面放着股票日行情、财务报表等数据。
- `teacher/`：扩展数据目录，里面放着一些更高级的数据集。

如果你看到了这些文件和文件夹，说明数据已经准备好了。

你也可以在终端里检查：

```bash
ls data_releases/learning/
```

**这行在做什么：**

- `ls` 是“列出目录内容”的命令。
- `data_releases/learning/` 是要查看的文件夹路径。
- 运行后终端会显示这个文件夹里的内容，你应该能看到 `data_catalog.json`、`distribute`、`teacher` 等名字。

**正常输出示例：**

```text
data_catalog.json	distribute	teacher
```

如果看到这三个名字，就说明数据已经准备好了。

> **老师/助教提示**：如果你想一次性验证 QuantFish 环境是否完整，可以在项目根目录运行：
>
> ```bash
> scripts/start-quantfish.sh --mode verify
> ```
>
> 它会运行 Python 测试、前端测试和前端构建。普通学生完成前面的环境安装和数据构建即可，不需要运行这一步。

---

## 几个必须知道的命令行概念

你接下来会经常在终端里输入命令。先弄清楚下面三个概念，后面就不会慌。

### 1. 什么是 `cd`

`cd` 是 change directory 的缩写，意思是“切换文件夹”。

例如，如果你的 QuantFish 项目放在了 `Documents/platform6`，你可以这样进入它：

```bash
cd Documents/platform6
```

如果路径里包含空格，需要用英文引号包起来，例如：

```bash
cd "Vector lab/Qclass/platform6"
```

**这行在做什么：**

- `cd` 后面跟着文件夹路径。
- 运行后，终端的“当前位置”就变成了 `Documents/platform6`，之后你运行的命令都会在这个位置执行。

### 2. 什么是路径

路径就是文件或文件夹在电脑里的地址。

- 相对路径：相对于你当前所在文件夹的位置。例如你已经在 `platform6` 里，`config/platform.yaml` 就是指 `platform6` 下面的 `config` 文件夹里的 `platform.yaml`。
- 绝对路径：从电脑最顶层开始的完整地址。例如 macOS 上可能是 `/Users/你的名字/Documents/Vector lab/Qclass/platform6`。

QuantFish 的文档大多使用相对路径，因为你已经在项目根目录里了。

### 3. 怎么知道命令运行完了

终端每次运行完命令，都会重新显示一行提示符。

- 在 macOS/Linux 上，提示符通常长这样：`(QuantFish) 你的名字@电脑名:当前路径$`。
- 在 Windows 上，提示符通常长这样：`(QuantFish) C:\...>`。

如果你看到提示符重新出现了，而且没有出现红色的错误文字，就说明命令已经运行完成。

如果命令需要运行很长时间（例如安装环境或构建数据），终端可能暂时没有反应。这时候不要关闭窗口，等提示符再次出现即可。

---

## 小结

你现在应该已经：

1. 知道 QuantFish 是做什么的——你写函数，平台帮你回测。
2. 安装并激活了 `QuantFish` 的 Conda 环境。
3. 用 `python -m pip install -e .` 安装了 QuantFish 包。
4. 用 `python -m quantfish.data.releases build-from-config --config config/platform.yaml` 生成了学习数据集。
5. 确认 `data_releases/learning/` 文件夹里有 `data_catalog.json` 和 `distribute/` 等内容。
6. 知道什么是 `cd`、路径和命令行提示符。

如果上面的步骤都完成了，你就可以开始写第一个策略了。

---

## 本章要点

- QuantFish 的基本流程：写一个 `generate_signals` 函数，平台用历史数据回测并打分。
- 需要安装并激活 `QuantFish` Conda 环境，Python 版本应为 3.12。
- 用 `python -m pip install -e .` 以可编辑模式安装 QuantFish 包。
- 用 `python -m quantfish.data.releases build-from-config --config config/platform.yaml` 构建学习数据集。
- 学会 `cd`、相对路径和命令行提示符后，就可以开始写第一个策略。

下一步：[第一个策略](./01-first-strategy.md)
