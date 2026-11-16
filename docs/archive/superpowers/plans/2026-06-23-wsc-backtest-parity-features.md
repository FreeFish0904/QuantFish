# WSC Backtest Parity Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WSC-style capital sweep, long-only index hedge, and alpha correlation checking to QuantFish while preserving the existing primary submission score contract.

**Architecture:** Keep the main backtest result driven by `config.backtest.capital`; capital sweep produces additional diagnostics/artifacts and never changes leaderboard scoring. Apply index hedge after simulation and before metrics only when the resolved mode is `longonly`. Run correlation checking after report artifacts are written, using completed same-track submissions as the alpha pool.

**Tech Stack:** Python 3.12, pandas, pytest, FastAPI/Pydantic response models, React/Vitest for the admin settings surface.

---

## File Structure

- Modify `src/quantfish/platform_config/config.py`: add config fields and validation for capital sweep, hedge index, and correlation gate.
- Modify `config/platform.yaml`: add explicit default values for the new settings.
- Create `src/quantfish/backtest/capital_sweep.py`: run repeated simulations from already-loaded panel and scores.
- Create `src/quantfish/backtest/index_hedge.py`: load index returns and apply long-only hedge return subtraction.
- Modify `src/quantfish/backtest/runner.py`: extract reusable simulation/scoring helper, apply hedge, run sweep, include diagnostics.
- Modify `src/quantfish/backtest/simulator.py`: no behavior change expected; only use existing simulation entry point.
- Modify `src/quantfish/backtest/report_writer.py`: write `capital_sweep.csv`, `correlation_check.json`, and hedging fields where present.
- Create `src/quantfish/submissions/correlation.py`: read previous report returns and compute max correlation.
- Modify `src/quantfish/submissions/dispatcher.py`: run correlation gate after scoring and before marking completed.
- Modify `src/quantfish/submissions/artifacts.py`: expose new artifacts safely.
- Modify `src/quantfish/web_app/response_models.py`, frontend generated API types, and admin execution/settings UI only after backend tests pass.
- Test `tests/test_platform_config.py`, `tests/test_backtest_runner.py`, `tests/test_backtest_metrics_graph.py`, `tests/test_submission_service.py`.
- Create `tests/test_capital_sweep.py`, `tests/test_index_hedge.py`, and `tests/test_submission_correlation.py`.

---

### Task 1: Configuration Contract

**Files:**
- Modify: `src/quantfish/platform_config/config.py`
- Modify: `config/platform.yaml`
- Test: `tests/test_platform_config.py`

- [ ] **Step 1: Write failing config tests**

Add tests that lock the new public contract:

```python
def test_config_supports_wsc_parity_settings(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(
        backtest={
            "capital_sweep_enabled": True,
            "capital_sweep_values": [10_000_000, "100000000"],
            "hedge_index": "hs300",
        },
        execution={"long_only": True},
        scoring={
            "correlation_check_enabled": True,
            "correlation_threshold": 0.5,
        },
    )

    assert updated.backtest.capital_sweep_enabled is True
    assert updated.backtest.capital_sweep_values == (10_000_000, 100_000_000)
    assert updated.backtest.hedge_index == "hs300"
    assert updated.scoring.correlation_check_enabled is True
    assert updated.scoring.correlation_threshold == 0.5


def test_index_hedge_requires_long_only_mode(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="index hedge is only supported for long-only"):
        service.update(
            backtest={"alpha_type": "longshort", "hedge_index": "hs300"},
            execution={"long_only": False},
        )


def test_config_rejects_bad_capital_sweep_values(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="capital_sweep_values must be positive"):
        service.update(backtest={"capital_sweep_values": [1_000_000, 0]})


def test_config_rejects_bad_correlation_threshold(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="correlation_threshold must be between 0 and 1"):
        service.update(scoring={"correlation_threshold": 1.5})
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_platform_config.py -q
```

Expected: FAIL because `capital_sweep_enabled`, `capital_sweep_values`, `hedge_index`, `correlation_check_enabled`, and `correlation_threshold` are not defined.

- [ ] **Step 3: Implement config fields**

Add fields:

```python
@dataclass(frozen=True)
class BacktestConfig:
    data_start: date = date(2022, 1, 1)
    scoring_start: date = date(2023, 1, 1)
    scoring_end: date = date(2025, 12, 31)
    capital: int = 1_000_000
    capital_sweep_enabled: bool = False
    capital_sweep_values: tuple[int, ...] = (10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000)
    alpha_type: str = "longshort"
    hedge_index: str = "none"
    group_count: int = 5
    industry_neutralization: bool = False
    price_policy: str = "front_adjusted"
    execution_price: str = "vwap"
    mark_price: str = "close"
```

Add scoring fields:

```python
@dataclass(frozen=True)
class ScoringConfig:
    sharpe_weight: float = 45.0
    sharpe_target: float = 2.0
    annual_return_weight: float = 35.0
    annual_return_target: float = 0.30
    drawdown_weight: float = 15.0
    drawdown_limit: float = 0.30
    turnover_weight: float = 5.0
    turnover_limit: float = 3.0
    short_exposure_weight: float = 50.0
    minimum_slice_trading_days: int = 1
    correlation_check_enabled: bool = False
    correlation_threshold: float = 0.5
```

Add coercion for `capital_sweep_values`:

```python
def _coerce_backtest(values: dict[str, Any]) -> dict[str, Any]:
    if "capital_sweep_values" in values:
        raw_values = values["capital_sweep_values"] or []
        values["capital_sweep_values"] = tuple(int(value) for value in raw_values)
    if "hedge_index" in values:
        values["hedge_index"] = str(values["hedge_index"]).lower()
    return values
```

Call `_coerce_backtest(...)` inside `PlatformConfig.from_dict()` when building `BacktestConfig`.

Add validation:

```python
if not isinstance(self.backtest.capital_sweep_enabled, bool):
    raise ValueError("capital_sweep_enabled must be a boolean")
if any(value <= 0 for value in self.backtest.capital_sweep_values):
    raise ValueError("capital_sweep_values must be positive")
if self.backtest.hedge_index not in {"none", "hs300", "zz500"}:
    raise ValueError(f"unsupported hedge_index: {self.backtest.hedge_index}")
resolved_mode = "longonly" if self.execution.long_only else self.backtest.alpha_type
if self.backtest.hedge_index != "none" and resolved_mode != "longonly":
    raise ValueError("index hedge is only supported for long-only backtests")
if not isinstance(self.scoring.correlation_check_enabled, bool):
    raise ValueError("correlation_check_enabled must be a boolean")
if not 0.0 < self.scoring.correlation_threshold < 1.0:
    raise ValueError("correlation_threshold must be between 0 and 1")
```

- [ ] **Step 4: Update `config/platform.yaml`**

Add:

```yaml
backtest:
  capital_sweep_enabled: false
  capital_sweep_values:
  - 10000000
  - 100000000
  - 1000000000
  - 10000000000
  hedge_index: none
scoring:
  correlation_check_enabled: false
  correlation_threshold: 0.5
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_platform_config.py -q
git add src/quantfish/platform_config/config.py config/platform.yaml tests/test_platform_config.py
git commit -m "feat: add WSC parity config knobs"
```

Expected: tests pass.

---

### Task 2: Long-Only Index Hedge

**Files:**
- Create: `src/quantfish/backtest/index_hedge.py`
- Modify: `src/quantfish/backtest/runner.py`
- Modify: `src/quantfish/backtest/graph.py`
- Test: `tests/test_index_hedge.py`
- Test: `tests/test_backtest_runner.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_index_hedge.py`:

```python
import pandas as pd
import pytest

from quantfish.backtest.index_hedge import apply_index_hedge, select_index_returns


def test_select_index_returns_finds_hs300_and_normalizes_percent_returns() -> None:
    rows = pd.DataFrame(
        [
            {"indexcd": "000300", "idxtrd01": "2023-01-03", "idxtrd08": 1.0},
            {"indexcd": "000905", "idxtrd01": "2023-01-03", "idxtrd08": -2.0},
        ]
    )

    result = select_index_returns(
        rows,
        hedge_index="hs300",
        scoring_start=pd.Timestamp("2023-01-03"),
        scoring_end=pd.Timestamp("2023-01-03"),
    )

    assert result.to_dict("records") == [
        {"date": pd.Timestamp("2023-01-03"), "hedge_return": pytest.approx(0.01)}
    ]


def test_apply_index_hedge_subtracts_return_and_keeps_raw_return() -> None:
    daily = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-03"), "portfolio_return": 0.05},
            {"date": pd.Timestamp("2023-01-04"), "portfolio_return": -0.02},
        ]
    )
    hedge = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-03"), "hedge_return": 0.01},
            {"date": pd.Timestamp("2023-01-04"), "hedge_return": -0.03},
        ]
    )

    result = apply_index_hedge(daily, hedge)

    assert result["unhedged_portfolio_return"].tolist() == pytest.approx([0.05, -0.02])
    assert result["portfolio_return"].tolist() == pytest.approx([0.04, 0.01])
    assert result["hedge_return"].tolist() == pytest.approx([0.01, -0.03])
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_index_hedge.py -q
```

Expected: FAIL because `quantfish.backtest.index_hedge` does not exist.

- [ ] **Step 3: Implement hedge module**

Create:

```python
from __future__ import annotations

import pandas as pd

INDEX_CODES = {"hs300": "000300", "zz500": "000905"}


def select_index_returns(
    rows: pd.DataFrame,
    *,
    hedge_index: str,
    scoring_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
) -> pd.DataFrame:
    hedge_key = hedge_index.lower()
    if hedge_key == "none":
        return pd.DataFrame(columns=["date", "hedge_return"])
    if hedge_key not in INDEX_CODES:
        raise ValueError(f"unsupported hedge_index: {hedge_index}")

    code_column = _optional_column(rows, ["indexcd", "Indexcd"])
    date_column = _optional_column(rows, ["idxtrd01", "Trddt", "date", "tradingdate"])
    return_column = _optional_column(rows, ["idxtrd08", "Retindex", "return"])
    close_column = _optional_column(rows, ["idxtrd05", "Clsindex", "close"])
    if code_column is None or date_column is None:
        raise ValueError("market.index_daily must include index code and date columns")

    frame = rows.copy()
    frame["date"] = pd.to_datetime(frame[date_column]).dt.normalize()
    frame = frame[frame[code_column].map(_normalize_index_code) == INDEX_CODES[hedge_key]]
    frame = frame[(frame["date"] >= scoring_start) & (frame["date"] <= scoring_end)]
    frame = frame.sort_values("date")
    if frame.empty:
        raise ValueError(f"market.index_daily has no rows for hedge_index={hedge_key}")

    if return_column is not None:
        returns = pd.to_numeric(frame[return_column], errors="coerce")
        if returns.abs().max(skipna=True) is not None and returns.abs().max(skipna=True) > 1:
            returns = returns / 100.0
    elif close_column is not None:
        close = pd.to_numeric(frame[close_column], errors="coerce")
        returns = close.pct_change().fillna(0.0)
    else:
        raise ValueError("market.index_daily must include index return or close columns")

    return frame.assign(hedge_return=returns).loc[:, ["date", "hedge_return"]]


def apply_index_hedge(daily: pd.DataFrame, hedge_returns: pd.DataFrame) -> pd.DataFrame:
    result = daily.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    hedge = hedge_returns.copy()
    hedge["date"] = pd.to_datetime(hedge["date"]).dt.normalize()
    merged = result.merge(hedge, on="date", how="left")
    merged["hedge_return"] = pd.to_numeric(merged["hedge_return"], errors="coerce").fillna(0.0)
    merged["unhedged_portfolio_return"] = pd.to_numeric(
        merged["portfolio_return"], errors="coerce"
    ).fillna(0.0)
    merged["portfolio_return"] = merged["unhedged_portfolio_return"] - merged["hedge_return"]
    return merged


def _optional_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    return None


def _normalize_index_code(value: object) -> str:
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]
```

- [ ] **Step 4: Integrate in runner**

In `run_student_backtest(...)`, compute `mode` before simulation as it already does, then after `simulated = simulate_backtest(...)`:

```python
hedge_index = str(_config_value(backtest_config, "hedge_index", "none")).lower()
if hedge_index != "none":
    if mode != "longonly":
        raise ValueError("index hedge is only supported for long-only backtests")
    hedge_returns = select_index_returns(
        bundle.load_raw(HS300_DATASET),
        hedge_index=hedge_index,
        scoring_start=scoring_start,
        scoring_end=scoring_end,
    )
    simulated = replace(
        simulated,
        daily=apply_index_hedge(simulated.daily, hedge_returns),
    )
else:
    hedge_returns = pd.DataFrame(columns=["date", "hedge_return"])
```

Add to diagnostics:

```python
"hedge_index": hedge_index,
"hedge_rows": int(len(hedge_returns)),
```

- [ ] **Step 5: Update graph data for hedged runs**

In `build_backtest_graph_data(...)`, add a new series when `daily` has hedge columns:

```python
"hedge": _hedge_records(daily),
```

Add:

```python
def _hedge_records(rows: pd.DataFrame) -> list[dict]:
    if "hedge_return" not in rows.columns or "unhedged_portfolio_return" not in rows.columns:
        return []
    return [
        {
            "date": _date(row["date"]),
            "hedge_return": _json_float(row["hedge_return"]),
            "unhedged_portfolio_return": _json_float(row["unhedged_portfolio_return"]),
            "hedged_portfolio_return": _json_float(row["portfolio_return"]),
        }
        for _, row in rows.iterrows()
    ]
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_index_hedge.py tests/test_backtest_runner.py tests/test_backtest_metrics_graph.py -q
git add src/quantfish/backtest/index_hedge.py src/quantfish/backtest/runner.py src/quantfish/backtest/graph.py tests/test_index_hedge.py tests/test_backtest_runner.py tests/test_backtest_metrics_graph.py
git commit -m "feat: add long-only index hedge"
```

Expected: tests pass.

---

### Task 3: Capital Sweep Artifacts

**Files:**
- Create: `src/quantfish/backtest/capital_sweep.py`
- Modify: `src/quantfish/backtest/simulator.py`
- Modify: `src/quantfish/backtest/runner.py`
- Modify: `src/quantfish/backtest/report_writer.py`
- Test: `tests/test_capital_sweep.py`
- Test: `tests/test_backtest_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_capital_sweep.py`:

```python
import pandas as pd
import pytest

from quantfish.backtest.capital_sweep import run_capital_sweep
from quantfish.backtest.panel import BacktestPanel


def test_run_capital_sweep_reports_decay_metrics() -> None:
    panel = BacktestPanel(
        pd.DataFrame(
            [
                {"date": "2023-01-02", "symbol": "000001", "front_close": 10.0, "front_vwap": 10.0, "dnvaltrd": 100.0, "tradable": True, "limit_status": 0},
                {"date": "2023-01-03", "symbol": "000001", "front_close": 11.0, "front_vwap": 10.0, "dnvaltrd": 100.0, "tradable": True, "limit_status": 0},
                {"date": "2023-01-02", "symbol": "000002", "front_close": 10.0, "front_vwap": 10.0, "dnvaltrd": 100.0, "tradable": True, "limit_status": 0},
                {"date": "2023-01-03", "symbol": "000002", "front_close": 9.0, "front_vwap": 10.0, "dnvaltrd": 100.0, "tradable": True, "limit_status": 0},
            ]
        )
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = run_capital_sweep(
        panel,
        signals,
        capitals=[100.0, 10_000.0],
        mode="longshort",
        scoring_start=pd.Timestamp("2023-01-03"),
        scoring_end=pd.Timestamp("2023-01-03"),
    )

    assert result["capital"].tolist() == [100.0, 10_000.0]
    assert set(result.columns) >= {"capital", "sharpe", "fitness", "average_turnover", "total_return"}
    assert result.loc[0, "average_turnover"] >= result.loc[1, "average_turnover"]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_capital_sweep.py -q
```

Expected: FAIL because the capital sweep module does not exist.

- [ ] **Step 3: Implement capital sweep module**

Create:

```python
from __future__ import annotations

import pandas as pd

from quantfish.backtest.metrics import calculate_backtest_metrics
from quantfish.backtest.panel import BacktestPanel
from quantfish.backtest.simulator import simulate_backtest


def run_capital_sweep(
    panel: BacktestPanel,
    signals: pd.DataFrame,
    *,
    capitals: list[float] | tuple[float, ...],
    mode: str,
    scoring_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
    max_leverage: float = 1.0,
    top_k: int | None = None,
) -> pd.DataFrame:
    records = []
    for capital in capitals:
        simulated = simulate_backtest(
            panel,
            signals,
            capital=float(capital),
            mode=mode,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            max_leverage=max_leverage,
            top_k=top_k,
        )
        scoring_result = _slice_result(simulated, scoring_start, scoring_end)
        metrics = calculate_backtest_metrics(scoring_result)
        summary = metrics.summary
        records.append(
            {
                "capital": float(capital),
                "total_return": float(summary.get("all_return", 0.0)),
                "annual_return": float(summary.get("annual_return", 0.0)),
                "sharpe": float(summary.get("sharpe", 0.0)),
                "fitness": float(summary.get("fitness", 0.0)),
                "average_turnover": float(summary.get("average_turnover", 0.0)),
                "max_drawdown": float(summary.get("max_drawdown", 0.0)),
            }
        )
    return pd.DataFrame(records)


def _slice_result(result, scoring_start: pd.Timestamp, scoring_end: pd.Timestamp):
    daily = result.daily.copy()
    positions = result.positions.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.normalize()
    positions["date"] = pd.to_datetime(positions["date"]).dt.normalize()
    return type(result)(
        daily=daily[(daily["date"] >= scoring_start) & (daily["date"] <= scoring_end)].reset_index(drop=True),
        positions=positions[(positions["date"] >= scoring_start) & (positions["date"] <= scoring_end)].reset_index(drop=True),
        group_returns=pd.DataFrame(columns=["date", "group", "return"]),
    )
```

- [ ] **Step 4: Add sweep field to `BacktestResult`**

In `src/quantfish/backtest/simulator.py`, add:

```python
capital_sweep: pd.DataFrame = field(default_factory=pd.DataFrame)
```

to the `BacktestResult` dataclass.

- [ ] **Step 5: Integrate in runner and writer**

In `run_student_backtest(...)`, after primary metrics:

```python
sweep = pd.DataFrame()
if bool(_config_value(backtest_config, "capital_sweep_enabled", False)):
    sweep = run_capital_sweep(
        panel,
        scores_for_backtest.rename(columns={"code": "symbol", "score": "signal"}),
        capitals=tuple(_config_value(backtest_config, "capital_sweep_values", ())),
        mode=mode,
        scoring_start=scoring_start,
        scoring_end=scoring_end,
        commission_rate=float(_config_value(platform_execution, "commission_rate", 0.0)),
        slippage_rate=float(_config_value(platform_execution, "slippage_rate", 0.0)),
        max_leverage=float(_config_value(platform_execution, "max_leverage", 1.0)),
        top_k=_config_value(platform_execution, "top_k", None),
    )
```

Include in diagnostics:

```python
"capital_sweep_enabled": bool(_config_value(backtest_config, "capital_sweep_enabled", False)),
"capital_sweep_values": [int(value) for value in _config_value(backtest_config, "capital_sweep_values", ())],
```

Return `capital_sweep=sweep`.

In `write_backtest_report(...)`, add:

```python
_write_csv(output_path / "capital_sweep.csv", result.capital_sweep)
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_capital_sweep.py tests/test_backtest_runner.py tests/test_submission_service.py -q
git add src/quantfish/backtest/capital_sweep.py src/quantfish/backtest/simulator.py src/quantfish/backtest/runner.py src/quantfish/backtest/report_writer.py tests/test_capital_sweep.py tests/test_backtest_runner.py tests/test_submission_service.py
git commit -m "feat: add capital sweep artifact"
```

Expected: tests pass.

---

### Task 4: Alpha Correlation Check

**Files:**
- Create: `src/quantfish/submissions/correlation.py`
- Modify: `src/quantfish/submissions/dispatcher.py`
- Modify: `src/quantfish/submissions/artifacts.py`
- Modify: `src/quantfish/platform_config/config.py`
- Test: `tests/test_submission_correlation.py`
- Test: `tests/test_submission_service.py`

- [ ] **Step 1: Write failing correlation tests**

Create `tests/test_submission_correlation.py`:

```python
from pathlib import Path

import pandas as pd
import pytest

from quantfish.submissions.correlation import check_submission_correlation
from quantfish.submissions.models import Submission, SubmissionStatus


def _write_returns(report_dir: Path, values: list[float]) -> None:
    report_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"]),
            "daily_return": values,
        }
    ).to_parquet(report_dir / "daily_returns.parquet", index=False)


def test_check_submission_correlation_flags_high_corr(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate"
    existing_dir = tmp_path / "existing"
    _write_returns(candidate_dir, [0.01, 0.02, -0.01])
    _write_returns(existing_dir, [0.02, 0.04, -0.02])
    existing = Submission(
        submission_id="existing",
        team_id="team-a",
        status=SubmissionStatus.COMPLETED,
        strategy_path="strategy.py",
        report_dir=existing_dir.as_posix(),
        fingerprints=None,
        original_filename="strategy.py",
    )

    result = check_submission_correlation(
        candidate_submission_id="candidate",
        candidate_report_dir=candidate_dir,
        existing_submissions=[existing],
        threshold=0.5,
    )

    assert result.passed is False
    assert result.max_correlation == pytest.approx(1.0)
    assert result.matching_submission_id == "existing"


def test_check_submission_correlation_passes_when_pool_is_empty(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate"
    _write_returns(candidate_dir, [0.01, 0.02, -0.01])

    result = check_submission_correlation(
        candidate_submission_id="candidate",
        candidate_report_dir=candidate_dir,
        existing_submissions=[],
        threshold=0.5,
    )

    assert result.passed is True
    assert result.max_correlation is None
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_submission_correlation.py -q
```

Expected: FAIL because `quantfish.submissions.correlation` does not exist.

- [ ] **Step 3: Implement correlation module**

Create:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Any

import pandas as pd

from quantfish.submissions.models import SubmissionStatus


@dataclass(frozen=True)
class CorrelationCheckResult:
    passed: bool
    threshold: float
    max_correlation: float | None
    matching_submission_id: str | None
    checked_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_submission_correlation(
    *,
    candidate_submission_id: str,
    candidate_report_dir: Path | str,
    existing_submissions: Iterable[Any],
    threshold: float,
) -> CorrelationCheckResult:
    candidate = _read_daily_returns(Path(candidate_report_dir))
    max_corr: float | None = None
    max_id: str | None = None
    checked = 0
    for submission in existing_submissions:
        if getattr(submission, "submission_id", None) == candidate_submission_id:
            continue
        if getattr(submission, "status", None) != SubmissionStatus.COMPLETED:
            continue
        existing = _read_daily_returns(Path(getattr(submission, "report_dir", "")))
        if existing.empty:
            continue
        corr = _aligned_corr(candidate, existing)
        if corr is None:
            continue
        checked += 1
        if max_corr is None or corr > max_corr:
            max_corr = corr
            max_id = str(submission.submission_id)
    return CorrelationCheckResult(
        passed=max_corr is None or max_corr < threshold,
        threshold=float(threshold),
        max_correlation=max_corr,
        matching_submission_id=max_id,
        checked_count=checked,
    )


def _read_daily_returns(report_dir: Path) -> pd.DataFrame:
    path = report_dir / "daily_returns.parquet"
    if not path.is_file():
        return pd.DataFrame(columns=["date", "daily_return"])
    rows = pd.read_parquet(path)
    if "date" not in rows.columns or "daily_return" not in rows.columns:
        return pd.DataFrame(columns=["date", "daily_return"])
    rows = rows.loc[:, ["date", "daily_return"]].copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    rows["daily_return"] = pd.to_numeric(rows["daily_return"], errors="coerce")
    return rows.dropna(subset=["date", "daily_return"])


def _aligned_corr(candidate: pd.DataFrame, existing: pd.DataFrame) -> float | None:
    merged = candidate.merge(existing, on="date", suffixes=("_candidate", "_existing"))
    if len(merged) < 2:
        return None
    corr = merged["daily_return_candidate"].corr(merged["daily_return_existing"])
    if pd.isna(corr):
        return None
    return float(corr)
```

- [ ] **Step 4: Integrate post-score gate**

In `SubmissionScoringDispatcher._score_job(...)`, after metrics/report artifacts exist and before saving `COMPLETED`:

```python
config = self.config_repository.load()
correlation_result = None
if config.scoring.correlation_check_enabled:
    correlation_result = check_submission_correlation(
        candidate_submission_id=job.submission_id,
        candidate_report_dir=report_dir,
        existing_submissions=[
            item
            for item in self.submission_repository.list_all()
            if item.data_track == submission.data_track
        ],
        threshold=config.scoring.correlation_threshold,
    )
    _write_correlation_artifact(report_dir, correlation_result)
    if not correlation_result.passed:
        raise ValueError(
            "Check correlation fail, "
            f"max corr = {correlation_result.max_correlation:.3f} "
            f"with submission {correlation_result.matching_submission_id}"
        )
```

Add helper:

```python
def _write_correlation_artifact(report_dir: Path, result: Any) -> None:
    (report_dir / "correlation_check.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 5: Expose artifact**

In `ReportArtifactReader.read(...)`, add:

```python
"correlation_check": self._read_json(root / "correlation_check.json"),
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_submission_correlation.py tests/test_submission_service.py -q
git add src/quantfish/submissions/correlation.py src/quantfish/submissions/dispatcher.py src/quantfish/submissions/artifacts.py src/quantfish/platform_config/config.py tests/test_submission_correlation.py tests/test_submission_service.py
git commit -m "feat: add submission correlation gate"
```

Expected: tests pass.

---

### Task 5: Admin And Result Surface

**Files:**
- Modify: `src/quantfish/web_app/response_models.py`
- Modify: `frontend/src/features/admin/ui/ExecutionPanel.tsx`
- Modify: `frontend/src/features/admin/model.ts`
- Modify: `frontend/src/shared/submissions/executionParameters.ts`
- Regenerate: `frontend/src/shared/api/generated/api-types.ts`
- Test: `frontend/src/features/admin/model.test.ts`
- Test: `frontend/src/features/admin/view.test.tsx`
- Test: `frontend/src/shared/submissions/executionParameters.test.ts`

- [ ] **Step 1: Write failing frontend/model expectations**

Add expectations that admin settings include:

```ts
expect(settings.capitalSweepEnabled).toBe(false);
expect(settings.capitalSweepValues).toEqual([10000000, 100000000, 1000000000, 10000000000]);
expect(settings.hedgeIndex).toBe("none");
expect(settings.scoring.correlationCheckEnabled).toBe(false);
expect(settings.scoring.correlationThreshold).toBe(0.5);
```

Add execution parameter rows:

```ts
expect(rows.map((row) => row.id)).toContain("hedge_index");
expect(rows.map((row) => row.id)).toContain("capital_sweep_enabled");
```

- [ ] **Step 2: Run failing frontend tests**

Run:

```bash
npm test -- --run frontend/src/features/admin/model.test.ts frontend/src/features/admin/view.test.tsx frontend/src/shared/submissions/executionParameters.test.ts
```

Expected: FAIL because the new fields are absent.

- [ ] **Step 3: Add API and UI fields**

Add fields to backend response models:

```python
capital_sweep_enabled: bool | None = None
capital_sweep_values: list[int] | None = None
hedge_index: str | None = None
correlation_check_enabled: bool | None = None
correlation_threshold: float | None = None
```

In the admin UI, add:

```ts
{ key: "capital_sweep_enabled", labelKey: "admin.capitalSweepEnabled" }
{ key: "hedge_index", labelKey: "admin.hedgeIndex" }
{ key: "correlation_check_enabled", labelKey: "admin.correlationCheckEnabled" }
```

Use a comma-separated numeric input for `capital_sweep_values`, parsed into number array:

```ts
const capitalSweepValues = form.capital_sweep_values
  .split(",")
  .map((value) => Number(value.trim()))
  .filter((value) => Number.isFinite(value));
```

- [ ] **Step 4: Regenerate API types and verify**

Run:

```bash
npm test -- --run frontend/src/features/admin/model.test.ts frontend/src/features/admin/view.test.tsx frontend/src/shared/submissions/executionParameters.test.ts
npm run build
```

Expected: tests and build pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/quantfish/web_app/response_models.py frontend/src/features/admin/ui/ExecutionPanel.tsx frontend/src/features/admin/model.ts frontend/src/shared/submissions/executionParameters.ts frontend/src/shared/api/generated/api-types.ts frontend/src/features/admin/model.test.ts frontend/src/features/admin/view.test.tsx frontend/src/shared/submissions/executionParameters.test.ts
git commit -m "feat: expose WSC parity settings in admin UI"
```

---

### Task 6: End-To-End Verification

**Files:**
- Review: `docs/student/06-backtest-and-metrics.md`
- Review: `docs/student/11-backtest-engine-explained.md`
- Modify only if the behavior text becomes stale.

- [ ] **Step 1: Run backend parity tests**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_platform_config.py tests/test_index_hedge.py tests/test_capital_sweep.py tests/test_submission_correlation.py tests/test_backtest_runner.py tests/test_backtest_metrics_graph.py tests/test_submission_service.py -q
```

Expected: all listed tests pass.

- [ ] **Step 2: Run broader backend tests**

Run:

```bash
conda run -n QuantFish python -m pytest -q
```

Expected: all backend tests pass, or any unrelated pre-existing failure is documented with exact test name and error.

- [ ] **Step 3: Run frontend tests and build**

Run:

```bash
npm test -- --run
npm run build
```

Expected: frontend tests and production build pass.

- [ ] **Step 4: Manual smoke check**

Run a scoring job with:

```yaml
backtest:
  alpha_type: longonly
  hedge_index: hs300
  capital_sweep_enabled: true
scoring:
  correlation_check_enabled: true
  correlation_threshold: 0.5
execution:
  long_only: true
```

Confirm the report directory contains:

```text
summary.csv
daily_returns.parquet
net_value.parquet
turnover.parquet
group_daily_returns.parquet
performance_by_year.csv
capital_sweep.csv
graph_data.json
diagnostics.json
correlation_check.json
```

- [ ] **Step 5: Final commit if docs changed**

Run:

```bash
git add docs/student/06-backtest-and-metrics.md docs/student/11-backtest-engine-explained.md
git commit -m "docs: describe WSC parity backtest settings"
```

Skip this commit when the docs remain accurate.

---

## Self-Review

- Spec coverage: capital sweep is covered by Tasks 1 and 3; long-only index hedge is covered by Tasks 1 and 2; correlation check is covered by Tasks 1 and 4; admin/result surfacing is covered by Task 5; verification is covered by Task 6.
- Placeholder scan: no task depends on undefined file names or unspecified behavior. The plan chooses hard-fail correlation checking because WSC `check(result)` failed when `check_corr(result)` failed.
- Type consistency: config field names are `capital_sweep_enabled`, `capital_sweep_values`, `hedge_index`, `correlation_check_enabled`, and `correlation_threshold` across backend, artifacts, and UI.
- Scope boundary: the plan does not change the existing leaderboard score formula, default scoring capital, submission upload flow, or student strategy API.
