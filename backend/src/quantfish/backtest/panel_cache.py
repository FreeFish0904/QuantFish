from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quantfish.backtest.panel import BacktestPanel, build_backtest_panel
from quantfish.data import DataBundle

PANEL_CACHE_SCHEMA_VERSION = 2
PANEL_CACHE_DIR = ".quantfish-cache/backtest-panels"


@dataclass(frozen=True)
class PanelCacheResult:
    panel: BacktestPanel
    status: str
    panel_path: Path
    metadata_path: Path


def load_or_build_backtest_panel(
    bundle: DataBundle,
    returns_dataset: str,
    adj_factor_dataset: str,
) -> PanelCacheResult:
    metadata = _cache_metadata(bundle, returns_dataset, adj_factor_dataset)
    cache_key = _metadata_digest(metadata)
    cache_dir = bundle.root / PANEL_CACHE_DIR
    panel_path = cache_dir / f"{cache_key}.parquet"
    metadata_path = cache_dir / f"{cache_key}.json"

    cached = _read_cached_panel(panel_path, metadata_path, metadata)
    if cached is not None:
        return PanelCacheResult(
            panel=BacktestPanel(cached),
            status="hit",
            panel_path=panel_path,
            metadata_path=metadata_path,
        )

    panel = build_backtest_panel(
        bundle.load_raw(returns_dataset),
        bundle.load_raw(adj_factor_dataset),
    )
    _write_cached_panel(panel.rows, panel_path, metadata_path, metadata)
    return PanelCacheResult(
        panel=panel,
        status="rebuilt",
        panel_path=panel_path,
        metadata_path=metadata_path,
    )


def _cache_metadata(
    bundle: DataBundle,
    returns_dataset: str,
    adj_factor_dataset: str,
) -> dict[str, Any]:
    catalog_path = bundle.root / "data_catalog.json"
    return {
        "schema_version": PANEL_CACHE_SCHEMA_VERSION,
        "returns_dataset": returns_dataset,
        "adj_factor_dataset": adj_factor_dataset,
        "allowed_market_types": (
            list(bundle.allowed_market_types)
            if bundle.allowed_market_types is not None
            else None
        ),
        "files": [
            _file_signature("data_catalog.json", catalog_path),
            _dataset_signature(bundle, returns_dataset),
            _dataset_signature(bundle, adj_factor_dataset),
        ],
    }


def _dataset_signature(bundle: DataBundle, dataset_id_or_alias: str) -> dict[str, Any]:
    spec = bundle.describe(dataset_id_or_alias)
    return _file_signature(spec.relative_path, bundle.path(dataset_id_or_alias))


def _file_signature(relative_path: str, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": relative_path,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _metadata_digest(metadata: dict[str, Any]) -> str:
    payload = json.dumps(
        metadata,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_cached_panel(
    panel_path: Path,
    metadata_path: Path,
    expected_metadata: dict[str, Any],
) -> pd.DataFrame | None:
    try:
        if not panel_path.exists() or not metadata_path.exists():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata != expected_metadata:
            return None
        rows = pd.read_parquet(panel_path)
        if "tradable" in rows.columns:
            rows["tradable"] = rows["tradable"].map(bool).astype(object)
        return rows
    except Exception:
        return None


def _write_cached_panel(
    rows: pd.DataFrame,
    panel_path: Path,
    metadata_path: Path,
    metadata: dict[str, Any],
) -> None:
    try:
        panel_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_panel_path = panel_path.with_name(f".{panel_path.stem}.tmp.parquet")
        tmp_metadata_path = metadata_path.with_name(f".{metadata_path.stem}.tmp.json")
        rows.to_parquet(tmp_panel_path, index=False)
        tmp_metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_panel_path.replace(panel_path)
        tmp_metadata_path.replace(metadata_path)
    except Exception:
        return
