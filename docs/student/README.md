# QuantFish 学生文档

QuantFish是一个量化投资策略学习与回测平台，你只需要会写一个简单的 Python 函数，就能在真实历史数据上测试自己的投资想法。如果你想弄清“上传后平台到底做了什么”，可以重点阅读新增的 [回测引擎揭秘](./11-backtest-engine-explained.md)。

## 写给谁看

这份文档面向**完全没有编程背景**的学生。我们会从最基本的概念讲起，手把手带你写出第一个能在 QuantFish 平台上运行的策略。

## 快速开始

> 这个“快速开始”是给已经了解基础知识的学生的可选捷径。如果你是第一次接触 QuantFish，建议先阅读 [开始之前](./00-before-you-start.md) 和 [第一个策略](./01-first-strategy.md)。

如果你已经装好 Conda，按下面顺序操作即可跑通第一个策略。

> **运行命令前，请确保：**
>
> - 当前目录是 QuantFish 项目根目录（也就是包含 `config/`、`data_releases/`、`docs/` 的文件夹）。
> - 你已经会用 `cd` 命令进入这个文件夹（不会用请参考 [开始之前](./00-before-you-start.md) 的“几个必须知道的命令行概念”）。

1. 创建并激活 QuantFish 环境：
   ```bash
   conda env create -f environment.yml
   conda activate QuantFish
   ```
   第一次创建环境可能需要几分钟。完成后，终端提示符前面会出现 `(QuantFish)`。
2. 以可编辑模式安装 QuantFish 包：
   ```bash
   python -m pip install -e .
   ```
   成功时终端会显示类似 `Successfully installed quantfish` 的字样。
3. 构建学习数据集：
   ```bash
   python -m quantfish.data.releases build-from-config --config config/platform.yaml
   ```
   构建完成后，项目根目录会出现 `data_releases/learning/` 文件夹。
4. 阅读 [第一个策略](./01-first-strategy.md)（约 10 分钟）
5. 把示例策略复制成自己的 `strategy.py`，方便后续编辑和提交：
   ```bash
   cp docs/student/examples/hello_strategy.py strategy.py
   ```
   > 这步可以先跳过——它只是为了给你准备一个可修改的策略文件。
   > `cp` 命令成功时没有输出，执行后项目根目录会出现一个 `strategy.py` 文件。如果该文件已存在，会被覆盖。
6. 运行完整本地回测（smoke test）：
   ```bash
   python docs/student/examples/full_local_run.py
   ```
   > 这一步使用内置的 `hello_strategy.py`，是**开箱即用**的验证脚本。刚构建好学习数据就可以立刻运行，不需要先编辑 `strategy.py`。
   > 如果运行成功，终端最后会打印一行指标表；如果看到红色报错，先检查前面三步是否都完成了。

## 阅读顺序

1. [开始之前](./00-before-you-start.md) —— 约 10 分钟
2. [环境包安装指南（离线版）](./00a-environment-kit.md) —— 约 8 分钟
3. [第一个策略](./01-first-strategy.md) —— 约 10 分钟
4. [数据包接口](./02-data-bundle-api.md) —— 约 12 分钟
5. [数据集目录](./03-dataset-catalog.md) —— 约 12 分钟
6. [DataFrame 字段速查](./dataframe-field-guide.md) —— 约 15 分钟
7. [策略函数深入解析](./04-generate-signals-deep-dive.md) —— 约 15 分钟
8. [示例策略逐行讲解](./05-example-strategies-walkthrough.md) —— 约 15 分钟
9. [回测与评价指标](./06-backtest-and-metrics.md) —— 约 12 分钟
10. [在本地运行](./07-running-locally.md) —— 约 10 分钟
11. [在网页端提交](./08-submitting-on-web.md) —— 约 8 分钟
12. [常见错误](./09-common-errors.md) —— 约 10 分钟
13. [Cookbook](./10-cookbook.md) —— 约 12 分钟
14. [回测引擎揭秘](./11-backtest-engine-explained.md) —— 约 15 分钟
15. [原始数据因子排序引导练习](./12b-raw-factor-ranking-guided-lab.md) —— 约 25 分钟
16. [原始数据因子排序实验](./12-raw-factor-ranking-lab.md) —— 约 20 分钟
17. [DataGo 舆情数据使用指南](./13-datago-data-guide.md) —— 约 20 分钟
18. [术语表](./glossary.md) —— 约 5 分钟

## 开始前需要准备什么

- 已经安装 [Conda](https://docs.conda.io/)（一个管理 Python 环境的工具）。
- 环境为 Python 3.12。
- 已经创建并激活 QuantFish 环境：

  ```bash
  conda activate QuantFish
  ```

- 已经用可编辑模式安装好 QuantFish 包：

  ```bash
  conda activate QuantFish
  python -m pip install -e .
  ```

- 已经生成学习数据集 `data_releases/learning`（构建方法见 [开始之前](./00-before-you-start.md)）。

## 快速上手

如果你已经准备好环境，可以直接打开最小的可运行示例：

[`examples/hello_strategy.py`](./examples/hello_strategy.py)

这个文件只有几十行，展示了策略函数 `generate_signals` 最基本的写法。

---

下一步：阅读 [开始之前](./00-before-you-start.md)
