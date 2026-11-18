# Metric definitions

Every number the platform shows is computed once, in one place
(`backend/src/quantfish/backtest/metrics.py`, and the benchmark-relative block in
`backend/src/quantfish/backtest/excess.py`), persisted to `summary.csv`, mirrored into
`SubmissionMetrics` and rendered by the detail page and the PDF report. This page is the
reference for **what each number means**, so a reader can reproduce it without guessing.

## Two bases, side by side

QuantFish reports the same backtest on two return bases. They are never mixed inside a
single number, and they are always labelled.

| Basis | Fields | Used for |
|---|---|---|
| **Arithmetic** (summed simple returns) | `all_return`, `total_return`, `annual_return`, `max_drawdown`, `calmar`, `average_year_return`, `worst_year_return`, `fitness` | **Scoring, ranking and staleness checks.** These are the values the scoring weights in `config/platform.yaml` were tuned on. |
| **Geometric** (compounded net value) | `compounded_total_return`, `cagr`, `compounded_max_drawdown`, `compounded_calmar`, `volatility`, `sortino`, `t_stat`, `t_stat_p_value` | **Reporting.** These are the definitions an external platform (or a reviewer) would use. |

Why keep both:

- Switching scoring to the geometric basis would change every historical score, so the
  arithmetic basis stays frozen (`engine_version` unchanged) and the leaderboard remains
  comparable across releases.
- Arithmetic annualization (`return × 252 / n`) is a linear extrapolation. Over a
  multi-year window it systematically **overstates** what a strategy compounds, because it
  ignores volatility drag. A strategy that averages 20%/yr with 40% volatility compounds
  closer to 12%/yr.
- The geometric block therefore exists to answer "what would this have actually
  compounded?", while `annual_return` keeps answering "how does this rank?".

Both bases are derived from the same daily return series, so they can never disagree about
which days were traded — only about how those days are aggregated.

## Return and drawdown

Notation: `r_1 … r_n` are the scoring-window daily returns of the scored series
(`portfolio_return`, or `scored_daily_return` = beta-adjusted active return in long-only
HS300 mode), `n` is the number of observations and `252` the trading days per year.

| Key | Formula | Notes |
|---|---|---|
| `all_return` / `total_return` | `Σ r_i` | Arithmetic cumulative return. In long-only HS300 mode this is the cumulative **active** return. |
| `annual_return` | `Σ r_i × 252 / n` | Arithmetic annualization. Drives scoring. |
| `max_drawdown` | `max(1 − equity_i / peak(equity)_i)` over `equity_i = 1 + Σ_{j≤i} r_j` | Peak-to-trough on the arithmetic net value, including the initial 1.0 as a peak. |
| `calmar` | `annual_return / max_drawdown` | `null` when `max_drawdown == 0`, because the ratio has no finite value. |
| `compounded_total_return` | `Π(1 + r_i) − 1` | What the account would hold if returns compounded. |
| `cagr` | `(Π(1 + r_i))^(252/n) − 1` | Compound annual growth rate. |
| `compounded_max_drawdown` | Peak-to-trough of the compounded net value, with the initial 1.0 included as a peak. | Reported as a positive magnitude, like `max_drawdown`. |
| `compounded_calmar` | `cagr / compounded_max_drawdown` | `null` when either term is undefined. |

`compounded_max_drawdown ≥ max_drawdown` whenever returns are volatile: arithmetic equities
add gains linearly, so a losing day after a big winner appears milder than it was on the
account.

## Risk-adjusted ratios

| Key | Formula | Notes |
|---|---|---|
| `sharpe` | `sqrt(252) × mean(r) / std(r, ddof=1)` | Excess return over a zero risk-free rate, matching the historical scoring definition. `0.0` when `n < 2` or `std == 0`. |
| `volatility` | `std(r, ddof=1) × sqrt(252)` | Annualized standard deviation of daily returns. `null` when `n < 2`. |
| `sortino` | `sqrt(252) × mean(r − rf_d) / DD`, with `DD = sqrt(mean(min(r_i − rf_d, 0)²))` | `rf_d = long_only_risk_free_rate / 252` (default `1.75% / 252`) is the minimum acceptable return. Downside deviation is the root mean square of the **negative excess returns over all observations**, so zero-return days dilute the denominator instead of being dropped. `null` when `n < 2`, or when no observation falls below the MAR (an infinite ratio is not a measurement). |
| `t_stat` | `mean(r) / std(r, ddof=1) × sqrt(n)` | Unadjusted Student t-statistic of the mean daily return: "how many standard errors is the average day away from zero?". For a one-year run it equals `sharpe`; for longer windows it grows as `sqrt(n)`, which is the honest scaling of statistical evidence. It does **not** correct for autocorrelation, so overlapping or illiquid strategies overstate it — this is a screening number, not a significance test. |
| `t_stat_p_value` | `erfc(abs(t) / sqrt(2))` | Two-sided p-value under the normal approximation (computed with `math.erf`/`erfc`, no SciPy dependency). Exact only for i.i.d. normal returns; treat it as indicative. |

## Benchmark-relative returns (excess return)

The scoring bases above answer "how good is the strategy?". This block answers the
question students ask first: **did it beat the CSI 300?** It is computed in
`backend/src/quantfish/backtest/excess.py` and is deliberately independent of the scoring
basis, so a scoring change can never move it.

Notation: `s_i` is the **raw** `portfolio_return` and `b_i` the CSI 300 return on day `i`.
Only days where both exist are used, so `strategy_*`, `benchmark_*` and `excess_*` always
describe the same window and `excess = strategy − benchmark` holds exactly.

| Key | Formula | Notes |
|---|---|---|
| `strategy_total_return` | `Σ s_i` | Raw portfolio, arithmetic. Equal to `total_return` in long-short mode, but **not** the beta-adjusted value long-only scoring uses. |
| `strategy_annual_return` | `Σ s_i × 252 / n` | Same arithmetic annualization as `annual_return`. |
| `benchmark_total_return` | `Σ b_i` | CSI 300, arithmetic. |
| `benchmark_annual_return` | `Σ b_i × 252 / n` | |
| `benchmark_cagr` | `(Π(1 + b_i))^(252/n) − 1` | Geometric: what the index actually compounded. |
| `excess_total_return` | `Σ (s_i − b_i)` | Headline excess return. |
| `excess_annual_return` | `Σ (s_i − b_i) × 252 / n` | Headline annualized excess. |
| `excess_compounded_return` | `Π(1 + s_i) / Π(1 + b_i) − 1` | Relative return: how much richer the strategy account ends up than the index. |
| `excess_cagr` | `(1 + excess_compounded_return)^(252/n) − 1` | |
| `excess_max_drawdown` | Peak-to-trough of `1 + Σ (s_j − b_j)` | Measured on the **excess** equity curve, so it is not comparable with `max_drawdown`. |
| `excess_win_rate` | `mean(s_i > b_i)` | Share of days that beat the index. |
| `excess_volatility` | `std(s_i − b_i, ddof=1) × sqrt(252)` | This is the tracking error. |
| `excess_information_ratio` | `excess_annual_return / excess_volatility` | `null` when tracking error is zero. |
| `excess_beta` | `cov(s, b) / var(b, ddof=1)` | Regression slope against the index, no risk-free adjustment. `null` for a flat benchmark. |
| `excess_observations` | aligned day count | `n` used by every formula above. |

Rules:

- Fewer than `MIN_EXCESS_OBSERVATIONS` (20) aligned days, or no benchmark data at all:
  **no `excess_*` column is written** to `summary.csv` (no `NaN` pollution), and
  `diagnostics.benchmark_relative.status` becomes `"unavailable"` with the reason. The
  detail page and the PDF then hide the block instead of printing gaps. A backtest can
  never fail because the index is missing.
- `active_*` (beta-adjusted, scoring basis) and `excess_*` (simple, reporting) are different
  measurements. The detail page and the PDF show both, labelled "scoring basis" vs
  "relative to benchmark", so nobody has to guess which is which.
- Submissions scored before this block existed simply have no excess fields; they stay
  readable and get the block on the next rescore.

## Undefined values are reported as null

A missing number is information; a fake `0`, `inf` or `NaN` is not. The rules:

| Situation | Result |
|---|---|
| `n < 2` | `volatility`, `sortino`, `t_stat`, `t_stat_p_value` are `null`; returns and CAGR are still reported. |
| Any `r_i ≤ −100%` (capital wiped out) | `compounded_total_return`, `cagr`, `compounded_max_drawdown`, `compounded_calmar` are `null`; the arithmetic fields are unaffected. |
| All returns are exactly zero | `cagr = 0.0`, `compounded_total_return = 0.0`, `volatility = 0.0`; `sortino` and `t_stat` are `null` (division by zero). |
| No return below the MAR | `sortino` is `null`. |
| `max_drawdown == 0` | `calmar` is `null`. |
| Report predates these fields | The API returns `null` and the UI falls back to `annual_return` for the CAGR card, so stored submissions stay readable without a rescore. |

## Where each number surfaces

| Surface | What it shows |
|---|---|
| `summary.csv` / `artifacts.summary` | Every key above, unchanged, as produced by `calculate_backtest_metrics`. |
| `performance_by_year.csv` | Per-calendar-year rows keep the arithmetic `annualized_return`; the relative drawdown definition matches `max_drawdown`. |
| Detail page KPI cards | Total return, **CAGR** (falls back to `annual_return`), Sharpe, max drawdown. |
| Detail page metric table | Every summary key **except** the `strategy_*` / `benchmark_*` / `excess_*` block, with percent formatting for `cagr`, `compounded_total_return`, `volatility` and drawdown formatting for `max_drawdown` / `compounded_max_drawdown`. |
| Detail page "Relative to benchmark" panel | The full `strategy_*` / `benchmark_*` / `excess_*` block, hidden for runs without a benchmark. |
| PDF report | Cover: verdict line (beat/trailed the CSI 300, or why the block is missing), strategy card block, "Versus CSI 300" card block and up to four generated highlights. Pages: equity / excess / drawdown / rolling Sharpe, monthly excess, turnover, exposure, factor groups, monthly heatmap, yearly bars. Tables: performance summary (both arithmetic and compounded bases), "Benchmark & Excess Return" grouped by strategy / CSI 300 / excess / coverage, and a yearly table with annualized return, Sharpe, turnover and drawdown. The risk table and the benchmark block label which basis each number belongs to. |
| Leaderboard | Sorting stays on the arithmetic metrics (`sharpe`, `max_drawdown`, `calmar`, `total_return`). The geometric block is informational and never reorders entries. |

## Reproducing the numbers

```python
from quantfish.backtest import BacktestResult, calculate_backtest_metrics

metrics = calculate_backtest_metrics(result, risk_free_daily_return=0.0175 / 252)
metrics.summary["annual_return"]   # arithmetic, drives scoring
metrics.summary["cagr"]            # geometric, drives the headline card
```

The runner resolves `risk_free_daily_return` once from
`backtest.long_only_risk_free_rate` and passes it to **both** metric computations (raw
portfolio and beta-adjusted active), so Sortino uses the same MAR everywhere.

`backend/tests/test_backtest_metrics_graph.py` pins each formula against an independent
recomputation with `pandas`/`math`, including the null rules above.
