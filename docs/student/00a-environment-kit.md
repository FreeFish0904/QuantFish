# 环境包安装指南（离线版）

> 如果你选择用 Conda 自己配置环境，请参考 [开始之前](./00-before-you-start.md)。
> 本文档适用于教师通过 Web 平台或网盘发给你的 **离线安装包**。

---

## 你手里拿到的是什么

教师会给你两个压缩包：

| 文件名 | 里面有什么 | 是否必须 |
|--------|-----------|---------|
| `learning-data.zip` | QuantFish 的 **学习数据集**（历史行情、财务预告等）和 `docs/student/` 学习文档 | 是 |
| `environment-macos-arm64.zip` / `environment-macos-x86_64.zip` / `environment-windows-x86_64.zip` | **离线 Python 运行环境** + QuantFish 源码 + 示例策略 + 启动脚本 | 是 |

> 下载时请根据你的电脑选择对应平台的环境包。不确定选哪个？看下一节“支持的平台”。

---

## 支持的平台

| 平台 | 环境包文件名示例 | 说明 |
|------|------------------|------|
| macOS Apple Silicon（M1/M2/M3 芯片） | `environment-macos-arm64.zip` | 最近几年的 Mac 笔记本/台式机 |
| macOS Intel（Intel 芯片） | `environment-macos-x86_64.zip` | 2020 年及以前的 Mac |
| Windows 10/11 64 位 | `environment-windows-x86_64.zip` | 绝大多数 Windows 笔记本 |

**如何查看自己的芯片/系统：**

- **macOS**：点击屏幕左上角 `` → “关于本机”。
  - 看到 “Chip Apple M...” 选 `arm64`。
  - 看到 “Processor Intel...” 选 `x86_64`。
- **Windows**：右键“此电脑” → “属性” → 查看“系统类型”，应为“64 位操作系统”。

---

## macOS 安装步骤

假设你下载的两个文件都在 `Downloads`（下载）文件夹里。

### 1. 新建一个文件夹并解压

打开“终端”（Terminal）应用，依次输入下面三行命令，每行输入后按回车：

```bash
cd ~/Downloads
mkdir -p quantfish-local-kit
cd quantfish-local-kit
```

> **这三行在做什么？**
> - `cd ~/Downloads`：进入“下载”文件夹。
> - `mkdir -p quantfish-local-kit`：创建一个名叫 `quantfish-local-kit` 的新文件夹。
> - `cd quantfish-local-kit`：进入这个新文件夹。

然后解压两个压缩包（假设你下载的是 Apple Silicon 版，Intel Mac 请把 `arm64` 换成 `x86_64`）：

```bash
unzip ../learning-data.zip
unzip ../environment-macos-arm64.zip
```

> 如果系统没有 `unzip` 命令，可以双击 `.zip` 文件用“归档实用工具”解压，但要确保解压后的 `data_releases/` 和 `offline-runtime/` 等文件夹**最终都位于 `quantfish-local-kit/` 里面**。

### 2. 运行安装脚本

```bash
chmod +x setup_mac.command
./setup_mac.command
```

> **这两行在做什么？**
> - `chmod +x setup_mac.command`：给安装脚本“可执行”权限，否则系统不让它运行。
> - `./setup_mac.command`：执行安装脚本，把离线 Python 环境解压到 `runtime/` 文件夹。

如果看到下面这句话，说明安装成功：

```text
Offline runtime unpacked. Run: runtime/bin/python run_learning_backtest.py
```

> 如果双击 `setup_mac.command` 提示“无法打开”，请回到终端用上面的 `chmod +x` 和 `./setup_mac.command` 方式运行。

### 3. 跑第一次回测（验证安装是否成功）

```bash
runtime/bin/python run_learning_backtest.py --strategy generate_signals.py --output output/local_run
```

> **这行在做什么？**
> - `runtime/bin/python`：使用刚刚解压出来的离线 Python。
> - `run_learning_backtest.py`：一个帮你运行回测的脚本。
> - `--strategy generate_signals.py`：告诉它用 `generate_signals.py` 这个策略文件。
> - `--output output/local_run`：把结果保存到 `output/local_run/` 文件夹。

如果一切正常，终端最后会打印一张类似这样的指标表：

```text
 all_return  annual_return  ...  total_return  trading_days
  0.123456       1.234567   ...      0.123456           123
```

同时 `output/local_run/` 文件夹里会出现 `summary.csv`、`graph_data.json` 等文件。

### 4.（可选）画图

```bash
runtime/bin/python plot_results.py --report output/local_run
```

运行后会在 `output/local_run/equity_metrics.png` 生成一张图。

---

## Windows 安装步骤

假设你下载的两个文件都在 `Downloads` 文件夹里。

### 1. 新建文件夹并解压

打开 **PowerShell**（不是 CMD）。按 `Win + X`，选择 “终端” 或 “Windows PowerShell”。

依次执行：

```powershell
cd ~\Downloads
New-Item -ItemType Directory -Force quantfish-local-kit | Out-Null
cd quantfish-local-kit
```

然后解压（假设你下载的是 Windows 版）：

```powershell
Expand-Archive -Force ..\learning-data.zip -DestinationPath .
Expand-Archive -Force ..\environment-windows-x86_64.zip -DestinationPath .
```

### 2. 运行安装脚本

PowerShell 默认不允许运行脚本，需要先临时放宽执行策略：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

> **这两行在做什么？**
> - `Set-ExecutionPolicy -Scope Process Bypass`：只在这个 PowerShell 窗口里允许运行本地脚本，关闭窗口后失效。
> - `.\setup_windows.ps1`：执行安装脚本，把离线 Python 环境解压到 `runtime\` 文件夹。

如果看到下面这句话，说明安装成功：

```text
Offline runtime unpacked. Run: .\runtime\python.exe run_learning_backtest.py
```

### 3. 跑第一次回测（验证安装是否成功）

```powershell
.\runtime\python.exe run_learning_backtest.py --strategy generate_signals.py --output output\local_run
```

正常结束时终端会打印指标表，并在 `output\local_run\` 里生成结果文件。

### 4.（可选）画图

```powershell
.\runtime\python.exe plot_results.py --report output\local_run
```

---

## 解压后你应该看到的文件结构

```text
quantfish-local-kit/
├── README.zh-CN.md              # 包自带的简短说明
├── config/
│   └── platform.yaml            # 平台配置（学习数据日期范围等）
├── data_releases/
│   └── learning/                # 学习数据集
├── generate_signals.py          # 你的策略文件（一开始是示例）
├── offline-runtime/
│   └── {platform}.zip           # 离线 Python 环境压缩包
├── plot_results.py              # 画图脚本
├── run_learning_backtest.py     # 本地回测脚本
├── setup_mac.command            # macOS 安装脚本
├── setup_windows.ps1            # Windows 安装脚本
├── src/quantfish/                 # QuantFish 源码（供离线导入使用）
├── environment.yml              # 环境配方（高级用户可选）
├── pyproject.toml               # 包元信息
└── output/                      # 回测结果会放在这里
```

---

## 怎么写自己的策略

你**只需要修改一个文件**：`generate_signals.py`。

> **注意**：离线包中的入口文件名为 `generate_signals.py`，功能与在线文档中的 `strategy.py` 完全相同，平台最终都会把它当作策略文件处理。

里面已经有一个示例函数 `generate_signals(data, date)`。你可以：

1. 用 `data.current(...)` 读取更多列；
2. 用 `data.history(...)` 读取历史数据；
3. 修改 `score` 的计算逻辑；
4. 保存文件后，再次运行上面的回测命令即可看到新结果。

具体写法请参考：

- [第一个策略](./01-first-strategy.md)
- [数据包接口](./02-data-bundle-api.md)
- [策略函数深入解析](./04-generate-signals-deep-dive.md)
- [Cookbook](./10-cookbook.md)

---

## 常见问题

### 1. macOS 双击 `setup_mac.command` 打不开

在终端里执行：

```bash
chmod +x setup_mac.command
./setup_mac.command
```

### 2. Windows 运行 `setup_windows.ps1` 报错 “无法加载文件，因为在此系统上禁止运行脚本”

先执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

然后再运行 `.\setup_windows.ps1`。

### 3. 提示找不到 `runtime/bin/python` 或 `runtime\python.exe`

说明离线环境还没有解压。请先成功运行 `setup_mac.command` 或 `setup_windows.ps1`，确认 `runtime/` 文件夹出现后再跑回测。

### 4. 提示找不到 `data_releases/learning`

说明 `learning-data.zip` 没有解压到 `quantfish-local-kit/` 文件夹里。请重新解压，确保 `data_releases/learning/` 和 `run_learning_backtest.py` 在同一层目录。

### 5. 修改策略后结果没有变化

确认你保存了 `generate_signals.py`，并且重新运行了 `run_learning_backtest.py`。

### 6. 这个离线包和 Web 平台是什么关系？

- **离线包**里的 `learning-data.zip` 是练习数据，也包含 `docs/student/` 学习文档，方便你在自己电脑上快速试错。
- **正式提交**还需要到 QuantFish Web 平台，选择 `hidden_test` 轨道上传你的策略。
- 本地表现好不等于平台表现好，最终成绩以平台 `hidden_test` 回测为准。

### 7. 老师/助教如何验证环境

如果你拥有完整的 QuantFish 项目仓库（而不仅是离线包），可以运行项目根目录下的统一启动脚本做完整验证：

```bash
scripts/start-quantfish.sh --mode verify
```

**这行在做什么：**

- `scripts/start-quantfish.sh`：项目根目录下的统一启动脚本，支持 `setup`、`dev`、`prod`、`verify` 等模式。
- `--mode verify`：运行 Python 测试、前端测试和前端构建，确认环境完整。

这一步主要用于老师/助教在课前检查环境；普通学生完成前面的安装和回测即可。

---

下一步：阅读 [第一个策略](./01-first-strategy.md)，学习怎么修改 `generate_signals.py`。
