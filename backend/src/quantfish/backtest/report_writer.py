from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from quantfish.backtest.result import BacktestResult


def write_backtest_report(result: BacktestResult, output_dir: Path | str) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    artifacts = [
        _write_csv(output_path / "summary.csv", result.summary),
        _write_parquet(output_path / "daily_returns.parquet", result.daily_returns),
        _write_parquet(output_path / "net_value.parquet", result.net_value),
        _write_parquet(output_path / "turnover.parquet", result.turnover),
        _write_parquet(
            output_path / "group_daily_returns.parquet", result.group_daily_returns
        ),
        _write_csv(output_path / "performance_by_year.csv", result.performance_by_year),
        _write_json(output_path / "graph_data.json", result.graph_data),
        _write_json(output_path / "diagnostics.json", result.diagnostics),
    ]
    return artifacts


def _write_csv(path: Path, frame: pd.DataFrame) -> Path:
    frame.to_csv(path, index=False)
    return path


def _write_parquet(path: Path, frame: pd.DataFrame) -> Path:
    frame.to_parquet(path, index=False)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    return path
