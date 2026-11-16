# QuantFish 学生文档审计总结

**分支：** `docs/student-audit-2026-06-27`  
**基础分支：** `codex/longonly-ashare-upgrade`  
**审计日期：** 2026-06-27

## 1. 目标

让一位只有 `docs/student/` 文档和 `data_releases/learning` 数据的学生，能够在不阅读平台源码的情况下写出策略、在本地跑通回测，并理解 Web 提交后的结果。

## 2. 发现统计

| 严重程度 | 数量 | 说明 |
|---|---|---|
| blocker | 4 | 学生按文档操作会提交失败或得到错误结论 |
| high | 5 | 学生会误解核心机制或优化错误指标 |
| medium | 9 | 信息缺失但不至于误导 |
| low | 6 | 表述/一致性瑕疵 |
| **合计** | **24** | 详见 `docs/audit/fix-checklist.md` |

## 3. 修改的文档

共修改 18 份学生文档：

- `00-before-you-start.md`
- `00a-environment-kit.md`
- `01-first-strategy.md`
- `02-data-bundle-api.md`
- `03-dataset-catalog.md`
- `04-generate-signals-deep-dive.md`
- `05-example-strategies-walkthrough.md`
- `06-backtest-and-metrics.md`
- `07-running-locally.md`
- `08-submitting-on-web.md`
- `09-common-errors.md`
- `10-cookbook.md`
- `11-backtest-engine-explained.md`
- `13-datago-data-guide.md`
- `dataframe-field-guide.md`
- `firm-data-api-guide.md`
- `glossary.md`

未修改：`12-raw-factor-ranking-lab.md`、`12b-raw-factor-ranking-guided-lab.md`、`README.md`（经核对与当前代码无冲突）。

## 4. 学生最应该感知到的关键变化

1. **只做多（long-only）模式用主动收益打分**  
   `total_return`/`sharpe`/`max_drawdown`/`calmar` 在 long-only 下是基于 `portfolio_return - beta × hs300_return` 计算的；`raw_*` 才是原始组合表现。

2. **行业中性化默认开启**  
   `config/platform.yaml` 里 `industry_neutralization: true`，文档 previously 写成 `false`。

3. **提交超时是 1200 秒且已启用**  
   文档 previously 写成 120 秒 / 未启用。

4. **hidden_test 默认关闭**  
   学生若只看到 `learning` 轨道，应先用练习轨道，等老师开放正式轨道。

5. **综合评分公式已更新**  
   包含 `sharpe`、`annual_return`、`max_drawdown`、`average_turnover` 以及 100 权重的 `annualized_short_profit` 惩罚项。

6. **默认市场过滤 `markettype 1, 4`**  
   平台运行时只交易这两个市场类型；本地研究脚本若绕过 `DataBundle` 会看到更大股票池。

7. **`generate_signals` 收到的是受限数据视图**  
   可用方法为 `current`、`load`、`history`、`latest`、`list_datasets`、`describe`；`path`/`load_raw`/`at` 不存在。

8. **只做多图表数据与主动收益对齐**  
   基础分支 `bb6237c3` 更新后，只做多模式下 `equity`、`drawdown`、`daily_pnl`、`daily_returns`、`alpha` 均基于 `scored_daily_return`（主动收益）绘制；文档已同步此行为。

## 5. 验证结果

- 内部 Markdown 链接检查：无断链。
- 示例代码 `py_compile`：全部通过。
- 测试套件：合并基础分支的 `bb6237c3` 后重新运行，`272 passed, 1 warning`（使用 `QuantFish` Conda 环境，PYTHONPATH 设为项目根目录）。
- 冷读验证：4 名只读代理按学生视角阅读更新后的文档，发现并已在本次提交中修复的遗留问题包括：
  - `06` 与 `11` 中超时描述不一致；
  - `06` 中 `average_net_exposure` 公式表述与代码相反；
  - `07` 中学习数据起始年份残留 2015；
  - `01` 未告知如何运行策略；
  - `glossary` 缺少若干指标术语；
  - `alpha` 在多空/只做多模式下的定义冲突。

## 6. 仍然存在的已知限制 / 建议后续工作

1. **数据构建步骤无进度输出**  
   `python -m quantfish.data.releases build-from-config` 在已有数据上重建时可能长时间无输出。建议后续在工具层增加进度条，或在文档中说明如何判断是否可跳过。

2. **示例 `full_local_run.py` 仍硬编码 `hello_strategy.py`**  
   文档已在 `01-first-strategy.md` 和 `07-running-locally.md` 中反复强调需要改路径，但把脚本默认值改为 `strategy.py` 会更符合直觉（需要修改源码）。

3. **部分术语仍依赖交叉引用**  
   `11-backtest-engine-explained.md` 为“揭秘”性质，仍引用源码文件名。这符合其进阶定位，但零基础学生可能需要先读 `06` 和 `glossary`。

4. **缺少只做多实际回测样例**  
   仓库中已有的 `summary.csv` 样例均为多空模式。若课程使用 long-only，建议补充一份 long-only 的 `summary.csv`/`graph_data.json` 样例或截图，方便学生对照字段。

5. **排行榜 API 返回 `metric: sharpe` 与文档 composite score 公式不完全一致**  
   文档已按 `leaderboard/ranking.py` 中的 composite score 公式更新；UI 层若仍显示 `sharpe` 列，属于前端展示问题，不在本次文档审计范围内。

6. **审计过程中基础分支发生了代码变更**  
   在审计期间，基础分支新增了 `bb6237c3`（更新只做多图表数据源）。本审计分支已合并该提交并同步更新文档，同时删除了该提交意外带入的仓库根目录 `strategy.py`。

## 7. 如何查看变更

```bash
git log --oneline docs/student-audit-2026-06-27..origin/codex/longonly-ashare-upgrade
git diff docs/student-audit-2026-06-27..origin/codex/longonly-ashare-upgrade -- docs/student/
```

## 8. 推荐下一步

1. 由维护者 review 本分支的文档变更，特别关注 long-only 主动收益、行业中性化默认、提交超时的措辞是否准确。
2. 若课程确定使用 long-only，补充 long-only 样例输出。
3. 合并到基础分支前，建议跑一次 `scripts/start-quantfish.sh --mode verify` 做端到端验证。
