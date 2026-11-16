# Documentation Fix Checklist

Triaged from `docs/audit/raw-findings.md`. Each item maps a doc claim to the current code/config reality and assigns an owner scope for the fix swarm.

Severity legend:
- **blocker** — student following the doc literally cannot submit or gets a silently wrong result.
- **high** — student will misunderstand a major feature or optimize the wrong metric.
- **medium** — incomplete but not misleading.
- **low** — wording polish or consistency.

---

## Finding 1: Industry neutralization default is `true`, not `false`

- **Severity:** blocker
- **Doc file:** `docs/student/06-backtest-and-metrics.md` (config table around line 103)
- **Source file:** `config/platform.yaml:17`, `src/quantfish/backtest/runner.py:62-64`
- **Current doc claim:** `industry_neutralization` default is `false`.
- **Code reality:** `config/platform.yaml` sets `industry_neutralization: true`.
- **Fix required:** Change the default in the table to `true`. Add a short paragraph explaining that the default is on and what it does (within-industry demean; stocks without industry classification get score 0).
- **Owner agent scope:** backtest-docs

---

## Finding 2: Long-only scoring uses beta-adjusted active returns

- **Severity:** blocker
- **Doc file:** `docs/student/06-backtest-and-metrics.md`, `docs/student/11-backtest-engine-explained.md`
- **Source file:** `src/quantfish/backtest/runner.py:129-165`, `src/quantfish/backtest/active_returns.py:20-100`, `src/quantfish/backtest/metrics.py`
- **Current doc claim:** `total_return`, `sharpe`, `max_drawdown`, `calmar` describe raw portfolio performance.
- **Code reality:** In `long_only` mode, `scored_daily_return` is `portfolio_return - beta * hs300_return`; all scored metrics are computed from active returns. `summary.csv` also contains `raw_*`, `active_*`, `beta`, `tracking_error`, `information_ratio`.
- **Fix required:** Add a dedicated long-only section in `06-backtest-and-metrics.md` and update `11-backtest-engine-explained.md` to describe active-return scoring, the meaning of each raw/active field, and that `sharpe` in long-only is effectively the information ratio. Include the beta/TE/IR formulas from `active_returns.py`.
- **Owner agent scope:** backtest-docs

---

## Finding 3: Submission timeout is 1200 s and enabled, not 120 s and disabled

- **Severity:** high
- **Doc file:** `docs/student/08-submitting-on-web.md` (around line 105), `docs/student/11-backtest-engine-explained.md` (around line 66-67)
- **Source file:** `config/platform.yaml:46-47`, `src/quantfish/submissions/runners.py:117-120`
- **Current doc claim:** Default timeout is 120 s and currently disabled.
- **Code reality:** `submission_timeout_seconds: 1200`, `submission_timeout_enabled: true`.
- **Fix required:** Update both docs to `1200` seconds and `enabled: true`. Add a note that the exact value is configurable by the admin and should be checked in the running `config/platform.yaml`.
- **Owner agent scope:** submission-docs

---

## Finding 4: `hidden_test` track can be disabled; disabled by default

- **Severity:** blocker
- **Doc file:** `docs/student/08-submitting-on-web.md` (track selection section)
- **Source file:** `config/platform.yaml:44`, `src/quantfish/submissions/track_visibility.py:31-38`, `src/quantfish/submissions/service.py:142-143`
- **Current doc claim:** `hidden_test` is the formal/leaderboard track; implied always available.
- **Code reality:** `hidden_test_enabled: false` by default; submitting to hidden_test when disabled returns `Submissions are disabled`.
- **Fix required:** Explain that the admin can disable `hidden_test`; in the default config it is disabled. Tell students to select `learning` if `hidden_test` is unavailable, and to ask the instructor when the leaderboard track opens.
- **Owner agent scope:** submission-docs

---

## Finding 5: Composite score formula is wrong and omits `short_profit` penalty

- **Severity:** blocker
- **Doc file:** `docs/student/08-submitting-on-web.md` (score section around lines 121-130)
- **Source file:** `src/quantfish/leaderboard/ranking.py:208-287`, `config/platform.yaml:23-34`
- **Current doc claim:** Score combines `total_return`, `sharpe`, `max_drawdown`, `average_year_return`, `worst_year_return`, `average_turnover`.
- **Code reality:** `score = clamp(sharpe/2.0, -1, 1)*40 + clamp(annual_return/0.30, -1, 1)*60 - clamp(abs(max_drawdown)/0.30, 0, 1)*15 - clamp(average_turnover/3.0, 0, 1)*5 - clamp(annualized_short_profit/0.30, 0, 1)*100`.
- **Fix required:** Replace the prose with the exact formula, explain each clamp, and describe the 100-weight `annualized_short_profit` penalty (relevant for long-short strategies; long-only may have zero or negligible short profit).
- **Owner agent scope:** submission-docs

---

## Finding 6: `max_position_weight` and `min_listing_days` are undocumented

- **Severity:** high
- **Doc file:** `docs/student/06-backtest-and-metrics.md`, `docs/student/glossary.md`
- **Source file:** `config/platform.yaml:51`, `config/platform.yaml:53`, `src/quantfish/backtest/runner.py:109-113`, `src/quantfish/backtest/runner.py:384-465`, `src/quantfish/backtest/simulator.py:128`
- **Current doc claim:** Not mentioned.
- **Code reality:** `max_position_weight: 0.05` (long-only only); `min_listing_days: 60` filters the long-only investable universe.
- **Fix required:** Add both fields to the config table in `06-backtest-and-metrics.md`, note that they apply only in long-only mode, and add glossary entries.
- **Owner agent scope:** backtest-docs

---

## Finding 7: Default market-type filter `(1, 4)` is undocumented

- **Severity:** high
- **Doc file:** `docs/student/02-data-bundle-api.md`, `docs/student/03-dataset-catalog.md`
- **Source file:** `src/quantfish/market_types.py:19`, `src/quantfish/data/bundle.py:78-86`, `config/platform.yaml:40-42`, `src/quantfish/backtest/runner.py:42`
- **Current doc claim:** `DataBundle` examples imply access to the full release without market filtering.
- **Code reality:** Platform runs (and `DataBundle` reads by default) filter to `markettype` 1 and 4. Research scripts that bypass `DataBundle` may see a larger universe than the platform will trade.
- **Fix required:** Add a warning/callout in `02-data-bundle-api.md` and a note in `03-dataset-catalog.md` that the platform trades only `markettype 1, 4` by default. Show how to reproduce the same filter in research if desired.
- **Owner agent scope:** data-api-docs

---

## Finding 8: Offline-kit entry filename is inconsistent with online docs

- **Severity:** medium
- **Doc file:** `docs/student/00a-environment-kit.md` (around line 200), `docs/student/README.md`, `docs/student/01-first-strategy.md`
- **Source file:** `src/quantfish/student_exports/runtime_packages.py`, `src/quantfish/submissions/storage.py:37`
- **Current doc claim:** Offline kit says edit `generate_signals.py`; online docs say `strategy.py`.
- **Code reality:** The platform renames any uploaded file to `generate_signals.py` internally, but the online student journey uses `strategy.py`.
- **Fix required:** In `00a-environment-kit.md`, add a sentence: “离线包中的入口文件名为 `generate_signals.py`，功能与在线文档中的 `strategy.py` 完全相同，平台最终都会把它当作策略文件处理。” Keep online docs using `strategy.py`.
- **Owner agent scope:** env-docs

---

## Finding 9: `performance_by_year.csv` is missing from local output file list

- **Severity:** medium
- **Doc file:** `docs/student/07-running-locally.md` (output table around lines 225-236)
- **Source file:** `src/quantfish/backtest/report_writer.py:24`
- **Current doc claim:** Lists 7 output files, omitting `performance_by_year.csv`.
- **Code reality:** `report_writer.py` writes `performance_by_year.csv`.
- **Fix required:** Add `performance_by_year.csv` to the table. Optionally note that its Sharpe/Calmar/Drawdown formulas are legacy and may differ slightly from `summary.csv`.
- **Owner agent scope:** local-run-docs

---

## Finding 10: `stale` is a boolean flag, not a submission status

- **Severity:** medium
- **Doc file:** `docs/student/08-submitting-on-web.md` (status section)
- **Source file:** `src/quantfish/submissions/models.py:17-21`, `src/quantfish/submissions/routes.py:303-313`, `src/quantfish/submissions/routes.py:350-362`
- **Current doc claim:** Lists `stale` as one of five statuses.
- **Code reality:** Statuses are `queued`, `running`, `completed`, `failed`. `stale` is a separate boolean computed from config/data/engine fingerprints.
- **Fix required:** Correct the status list to four values. Explain `stale: true` as a flag that can appear on a `completed` (or `failed`) submission when the platform config/data has changed since the run.
- **Owner agent scope:** submission-docs

---

## Finding 11: `generate_signals` receives `StudentDataView`, not raw `DatedDataBundle`

- **Severity:** high
- **Doc file:** `docs/student/02-data-bundle-api.md` (around line 3), `docs/student/04-generate-signals-deep-dive.md` (around line 50)
- **Source file:** `src/quantfish/factor_execution/strategy_execution.py:176-251`
- **Current doc claim:** Describes `data` as a `DatedDataBundle`.
- **Code reality:** The object passed to `generate_signals` is `StudentDataView`, a wrapper that proxies only `current`, `load`, `history`, `latest`, `list_datasets`, `describe`.
- **Fix required:** Update both docs to say the argument is a platform-provided data view with those methods. Explicitly warn that `data.path(...)`, `data.load_raw(...)`, `data.at(...)` do not exist inside `generate_signals`.
- **Owner agent scope:** data-api-docs

---

## Finding 12: Trading calendar is derived from `stock.daily_returns`, not all calendar days

- **Severity:** medium
- **Doc file:** `docs/student/04-generate-signals-deep-dive.md` (around line 17)
- **Source file:** `src/quantfish/factor_execution/strategy_execution.py:17`, `src/quantfish/factor_execution/strategy_execution.py:333-348`
- **Current doc claim:** “平台每天都会调用一次你的策略函数.”
- **Code reality:** Dates are the unique trading dates in `stock.daily_returns` within `[data_start, scoring_end]`.
- **Fix required:** Clarify that the platform calls the strategy once per trading date as defined by the canonical `stock.daily_returns` table.
- **Owner agent scope:** data-api-docs

---

## Finding 13: `generate_signals` signature must use positional parameters

- **Severity:** low
- **Doc file:** `docs/student/04-generate-signals-deep-dive.md` (signature section)
- **Source file:** `src/quantfish/factor_execution/strategy_execution.py:299-318`
- **Current doc claim:** Shows `generate_signals(data, date)` and `generate_signals(data)`.
- **Code reality:** Keyword-only parameters (e.g., `def generate_signals(data, *, date)`) are not counted as the second positional argument.
- **Fix required:** Add a note: use positional parameters; do not make `date` keyword-only.
- **Owner agent scope:** data-api-docs

---

## Finding 14: Stock code normalization truncates codes longer than 6 digits

- **Severity:** low
- **Doc file:** `docs/student/04-generate-signals-deep-dive.md` (around line 101)
- **Source file:** `src/quantfish/factor_execution/strategy_execution.py:391-399`
- **Current doc claim:** “统一整理成六位字符串.”
- **Code reality:** Codes are right-truncated to 6 digits after `zfill(6)` (e.g., `"1234567"` → `"234567"`).
- **Fix required:** Mention that codes are padded to 6 digits and then clipped to the rightmost 6 digits; returning already-6-digit strings is safest.
- **Owner agent scope:** data-api-docs

---

## Finding 15: `history()` constraints (`start` + `lookback_days`, negative values) are undocumented

- **Severity:** low
- **Doc file:** `docs/student/02-data-bundle-api.md` (history section)
- **Source file:** `src/quantfish/data/bundle.py:216-221`
- **Current doc claim:** Describes `lookback_days` usage without restrictions.
- **Code reality:** Passing both `start` and `lookback_days`, or a negative `lookback_days`, raises `ValueError`.
- **Fix required:** Add two short rules: use either `start`/`end` or `lookback_days`, not both; `lookback_days` must be non-negative.
- **Owner agent scope:** data-api-docs

---

## Finding 16: `FutureDataAccessError` also triggers on `start_date > bound_date`

- **Severity:** low
- **Doc file:** `docs/student/02-data-bundle-api.md` (future-data section)
- **Source file:** `src/quantfish/data/bundle.py:161-164`
- **Current doc claim:** Examples only show `end` past the bound date.
- **Code reality:** `start_date` greater than the bound date also raises.
- **Fix required:** Update the example/paragraph to say both `start` and `end` must be ≤ the bound date.
- **Owner agent scope:** data-api-docs

---

## Finding 17: Static tables without a date column are not bound by the future-date rule

- **Severity:** medium
- **Doc file:** `docs/student/02-data-bundle-api.md`
- **Source file:** `src/quantfish/data/bundle.py:155-157`, `src/quantfish/data/bundle.py:241-246`
- **Current doc claim:** “绑定日期之后的都是未来，不能读取.”
- **Code reality:** Datasets with no `primary_asof_column` return the full table regardless of bound date.
- **Fix required:** Add a note that static reference tables (no date column) can be loaded fully; time-series tables are the ones bound by the date.
- **Owner agent scope:** data-api-docs

---

## Finding 18: `latest(by=None)` falls back to the whole table when no symbol column exists

- **Severity:** low
- **Doc file:** `docs/student/02-data-bundle-api.md` (latest section)
- **Source file:** `src/quantfish/data/bundle.py:239-246`
- **Current doc claim:** “会尝试用数据集中默认的股票代码列来分组.”
- **Code reality:** If no symbol column, returns the latest row of the whole table.
- **Fix required:** Document the fallback behavior.
- **Owner agent scope:** data-api-docs

---

## Finding 19: `all_return` does not include the warmup period

- **Severity:** high
- **Doc file:** `docs/student/06-backtest-and-metrics.md` (around line 206), `docs/student/11-backtest-engine-explained.md`
- **Source file:** `src/quantfish/backtest/runner.py:123`, `src/quantfish/backtest/runner.py:617-643`, `src/quantfish/backtest/runner.py:648`
- **Current doc claim:** `all_return` covers the whole backtest interval including warmup; `total_return` covers only the scoring period.
- **Code reality:** Results are cropped to `[scoring_start, scoring_end]` before metrics are computed. `all_return` and `total_return` are identical in the current pipeline.
- **Fix required:** Remove or correct the warmup claim. Explain that metrics and graphs are calculated only over the scoring window (`scoring_start` to `scoring_end`).
- **Owner agent scope:** backtest-docs

---

## Finding 20: Long-only investable-universe filters are undocumented

- **Severity:** medium
- **Doc file:** `docs/student/06-backtest-and-metrics.md`, `docs/student/11-backtest-engine-explained.md`
- **Source file:** `src/quantfish/backtest/runner.py:384-465`
- **Current doc claim:** Not mentioned.
- **Code reality:** Long-only removes untradable stocks, invalid prices/volume, and stocks listed fewer than `min_listing_days`.
- **Fix required:** Add a subsection under long-only describing the investable universe: tradable, valid close/vwap/turnover, and listing-age filter.
- **Owner agent scope:** backtest-docs

---

## Finding 21: Graph data sources differ between raw and active returns in long-only

- **Severity:** medium
- **Doc file:** `docs/student/06-backtest-and-metrics.md`, `docs/student/11-backtest-engine-explained.md`
- **Source file:** `src/quantfish/backtest/graph.py:20-22`, `src/quantfish/backtest/graph.py:70-78`, `src/quantfish/backtest/graph.py:134-135`
- **Current doc claim:** Not distinguished.
- **Code reality:** `equity`/`drawdown` use raw portfolio returns; `alpha` uses beta-adjusted active returns in long-only.
- **Fix required:** In the long-only section, note that the equity/drawdown curves show raw portfolio performance while the alpha series shows active return.
- **Owner agent scope:** backtest-docs

---

## Finding 22: Common errors doc needs updates for new failure modes

- **Severity:** medium
- **Doc file:** `docs/student/09-common-errors.md`
- **Source file:** `src/quantfish/factor_execution/strategy_execution.py`, `src/quantfish/data/bundle.py`, `src/quantfish/submissions/service.py`, `src/quantfish/submissions/storage.py`, `src/quantfish/backtest/active_returns.py`
- **Current doc claim:** Existing error list.
- **Code reality:** Missing or outdated errors: hidden_test disabled, submission cooldown, active-return benchmark missing data, long-only listing-age filter causing empty universe, `FutureDataAccessError` on `start`.
- **Fix required:** Add entries/updates for: (1) `Submissions are disabled` / hidden_test closed, (2) `Please wait N seconds before submitting again`, (3) active-return benchmark missing dates, (4) empty investable universe in long-only, (5) `FutureDataAccessError` when `start` is in the future.
- **Owner agent scope:** errors-docs

---

## Finding 23: Glossary is missing key platform terms

- **Severity:** medium
- **Doc file:** `docs/student/glossary.md`
- **Source file:** all relevant source files
- **Current doc claim:** Existing glossary.
- **Code reality:** Terms introduced by recent changes are absent: `active return`, `information ratio`, `tracking error`, `beta` (in scoring context), `max_position_weight`, `min_listing_days`, `annualized_short_profit`, `industry neutralization`, `market type`.
- **Fix required:** Add concise definitions for each term, with links to the relevant doc sections.
- **Owner agent scope:** env-docs

---

## Finding 24: `00a-environment-kit.md` and `00-before-you-start.md` should reference current script names

- **Severity:** low
- **Doc file:** `docs/student/00-before-you-start.md`, `docs/student/00a-environment-kit.md`
- **Source file:** `scripts/start-quantfish.sh`, `environment.yml`
- **Current doc claim:** Startup instructions.
- **Code reality:** `scripts/start-quantfish.sh` supports `--mode setup|dev|prod|verify`; doc only mentions basic start.
- **Fix required:** Keep the beginner path simple, but add a tip that `--mode verify` runs tests/build for teachers/TAs.
- **Owner agent scope:** env-docs

---

## Fix agent partition

| Agent scope | Docs to update | Findings covered |
|---|---|---|
| `data-api-docs` | `02-data-bundle-api.md`, `04-generate-signals-deep-dive.md`, `10-cookbook.md`, `dataframe-field-guide.md` | 7, 11, 12, 13, 14, 15, 16, 17, 18 |
| `catalog-docs` | `03-dataset-catalog.md`, `13-datago-data-guide.md`, `firm-data-api-guide.md` | 7 (catalog angle), any catalog-specific gaps |
| `backtest-docs` | `06-backtest-and-metrics.md`, `11-backtest-engine-explained.md`, `12-raw-factor-ranking-lab.md`, `12b-raw-factor-ranking-guided-lab.md` | 1, 2, 6, 19, 20, 21 |
| `submission-docs` | `08-submitting-on-web.md` | 3, 4, 5, 10 |
| `local-run-docs` | `07-running-locally.md`, `05-example-strategies-walkthrough.md` | 9, example consistency |
| `env-docs` | `00-before-you-start.md`, `00a-environment-kit.md`, `README.md`, `glossary.md` | 8, 23, 24 |
| `errors-docs` | `09-common-errors.md` | 22 |
