from pathlib import Path

import pandas as pd

import quantfish.backtest.panel_cache as panel_cache
from quantfish.backtest.panel_cache import load_or_build_backtest_panel
from quantfish.data import DataBundle
from quantfish.data.catalog import DataCatalog, DatasetSpec

RETURNS_DATASET = "stock.daily_returns"
ADJ_FACTOR_DATASET = "factor_benchmark.adj_factor"


def test_panel_cache_reuses_cached_panel_without_rebuilding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    bundle = DataBundle(data_root, allowed_market_types=(1, 4))

    first = load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)

    def fail_build(*args, **kwargs):
        raise AssertionError("panel cache should avoid rebuilding")

    monkeypatch.setattr(panel_cache, "build_backtest_panel", fail_build)
    second = load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)

    assert first.status == "rebuilt"
    assert second.status == "hit"
    assert first.panel_path.exists()
    assert first.metadata_path.exists()
    pd.testing.assert_frame_equal(first.panel.rows, second.panel.rows)


def test_panel_cache_keys_include_allowed_market_types(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    main_board = load_or_build_backtest_panel(
        DataBundle(data_root, allowed_market_types=(1, 4)),
        RETURNS_DATASET,
        ADJ_FACTOR_DATASET,
    )
    startup_board = load_or_build_backtest_panel(
        DataBundle(data_root, allowed_market_types=(16,)),
        RETURNS_DATASET,
        ADJ_FACTOR_DATASET,
    )

    assert main_board.status == "rebuilt"
    assert startup_board.status == "rebuilt"
    assert main_board.panel_path != startup_board.panel_path
    assert sorted(main_board.panel.rows["symbol"].unique()) == ["000001", "000002"]
    assert startup_board.panel.rows["symbol"].unique().tolist() == ["300001"]


def test_panel_cache_invalidates_when_source_file_signature_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    bundle = DataBundle(data_root, allowed_market_types=(1, 4))
    load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)

    path = data_root / "distribute" / "stock" / "daily_returns.parquet"
    rows = pd.read_parquet(path)
    rows.loc[rows["Symbol"] == "000001", "Clsprc"] = 99.0
    rows.to_parquet(path, index=False)

    original_build = panel_cache.build_backtest_panel
    calls = {"count": 0}

    def counting_build(*args, **kwargs):
        calls["count"] += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(panel_cache, "build_backtest_panel", counting_build)
    rebuilt = load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)

    assert rebuilt.status == "rebuilt"
    assert calls["count"] == 1
    raw_close = rebuilt.panel.rows.loc[
        rebuilt.panel.rows["symbol"] == "000001",
        "raw_close",
    ].iloc[0]
    assert raw_close == 99.0


def test_panel_cache_rebuilds_corrupt_cached_panel(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    bundle = DataBundle(data_root, allowed_market_types=(1, 4))
    first = load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)
    first.panel_path.write_text("not a parquet file", encoding="utf-8")

    rebuilt = load_or_build_backtest_panel(bundle, RETURNS_DATASET, ADJ_FACTOR_DATASET)

    assert rebuilt.status == "rebuilt"
    assert not rebuilt.panel.rows.empty


def _write_release(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000001",
                "Clsprc": 10.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_000_000.0,
                "Markettype": 1,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000002",
                "Clsprc": 20.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 2_000_000.0,
                "Markettype": 4,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "300001",
                "Clsprc": 30.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 3_000_000.0,
                "Markettype": 16,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Clsprc": 11.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_100_000.0,
                "Markettype": 1,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "Clsprc": 19.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_900_000.0,
                "Markettype": 4,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "300001",
                "Clsprc": 31.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 3_100_000.0,
                "Markettype": 16,
            },
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    factor_dir = root / "teacher" / "factor_benchmark"
    factor_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000001",
                "cumulatefwardfactor": 2.0,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000002",
                "cumulatefwardfactor": 3.0,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "300001",
                "cumulatefwardfactor": 4.0,
            },
        ]
    ).to_parquet(factor_dir / "adj_factor.parquet", index=False)
    DataCatalog(
        root=root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id=RETURNS_DATASET,
                aliases=[],
                csmar_table_code=None,
                relative_path="distribute/stock/daily_returns.parquet",
                format="parquet",
                is_static=False,
                date_columns=["TradingDate"],
                primary_asof_column="TradingDate",
                symbol_column="Symbol",
            ),
            DatasetSpec(
                dataset_id=ADJ_FACTOR_DATASET,
                aliases=[],
                csmar_table_code=None,
                relative_path="teacher/factor_benchmark/adj_factor.parquet",
                format="parquet",
                is_static=False,
                date_columns=["TradingDate"],
                primary_asof_column="TradingDate",
                symbol_column="Symbol",
            ),
        ],
    ).save(root / "data_catalog.json")
