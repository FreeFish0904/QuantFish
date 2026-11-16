from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd

from quantfish.backtest.benchmark import (
    build_hs300_benchmark_records,
    load_hs300_benchmark,
)
from quantfish.data import DataBundle
from quantfish.submissions.track_config import track_release_root


def complete_hs300_benchmark_artifacts(
    artifacts: dict[str, Any],
    config: Any,
    data_track: Any,
) -> dict[str, Any]:
    graph_data = artifacts.get("graph_data")
    if not isinstance(graph_data, dict):
        return artifacts
    equity = _point_series(graph_data.get("equity"))
    if not equity:
        return artifacts
    benchmark = _point_series(graph_data.get("benchmark"))
    if _covers_equity_span(benchmark, equity):
        return artifacts

    benchmark_frame = _load_release_benchmark(config, data_track, equity)
    if benchmark_frame.empty or len(benchmark_frame) <= len(benchmark):
        return artifacts

    completed = copy.deepcopy(artifacts)
    completed_graph = dict(completed.get("graph_data") or {})
    completed_graph["benchmark"] = build_hs300_benchmark_records(
        benchmark_frame,
        capital=_artifact_capital(artifacts),
    )
    completed["graph_data"] = completed_graph
    return completed


def _load_release_benchmark(
    config: Any,
    data_track: Any,
    equity: list[dict[str, Any]],
) -> pd.DataFrame:
    try:
        data_root = Path(track_release_root(config, data_track))
        return load_hs300_benchmark(
            DataBundle(data_root),
            pd.Timestamp(_point_date(equity[0])).normalize(),
            pd.Timestamp(_point_date(equity[-1])).normalize(),
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return pd.DataFrame(columns=["date", "return"])


def _point_series(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = [point for point in value if isinstance(point, dict) and _point_date(point)]
    return sorted(rows, key=_point_date)


def _covers_equity_span(
    benchmark: list[dict[str, Any]],
    equity: list[dict[str, Any]],
) -> bool:
    if not benchmark:
        return False
    return _point_date(benchmark[0]) <= _point_date(equity[0]) and _point_date(
        benchmark[-1]
    ) >= _point_date(equity[-1])


def _point_date(point: dict[str, Any]) -> str:
    return str(point.get("date") or "")


def _artifact_capital(artifacts: dict[str, Any]) -> float:
    diagnostics = artifacts.get("diagnostics")
    if isinstance(diagnostics, dict):
        value = diagnostics.get("capital")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 1_000_000.0
