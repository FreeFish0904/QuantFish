# Metric definitions

Every number the platform shows is computed once, in one place
(`backend/src/quantfish/backtest/metrics.py`), persisted to `summary.csv`, mirrored into
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
| Detail page metric table | Every summary key, with percent formatting for `cagr`, `compounded_total_return`, `volatility` and drawdown formatting for `max_drawdown` / `compounded_max_drawdown`. |
| PDF report | Cover cards carry CAGR, Sortino and `t-stat`; the risk table lists both bases explicitly (arithmetic and compounded drawdown/Calmar). |
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
