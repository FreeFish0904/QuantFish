import json
from pathlib import Path

import pandas as pd
import pytest

from quantfish.backtest import BacktestPanel, run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.backtest.runner import BacktestResult, _calculate_group_returns
from quantfish.data.catalog import DataCatalog, DatasetSpec


def _write_release(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000001",
                "Ret": 99.0,
                "Clsprc": 10.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_000_000.0,
                "Markettype": 1,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000002",
                "Ret": 99.0,
                "Clsprc": 20.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 2_000_000.0,
                "Markettype": 4,
            },
            {
                "TradingDate": "2023-01-02",
                "Symbol": "300001",
                "Ret": 99.0,
                "Clsprc": 30.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 3_000_000.0,
                "Markettype": 16,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Ret": 99.0,
                "Clsprc": 10.9,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_000_000.0,
                "Markettype": 1,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "Ret": 99.0,
                "Clsprc": 18.2,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 2_000_000.0,
                "Markettype": 4,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "300001",
                "Ret": 99.0,
                "Clsprc": 39.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 3_900_000.0,
                "Markettype": 16,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000001",
                "Ret": 99.0,
                "Clsprc": 12.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_100_000.0,
                "Markettype": 1,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000002",
                "Ret": 99.0,
                "Clsprc": 18.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 1_800_000.0,
                "Markettype": 4,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "300001",
                "Ret": 99.0,
                "Clsprc": 25.0,
                "Dnshrtrd": 100_000.0,
                "Dnvaltrd": 2_500_000.0,
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
    market_dir = root / "distribute" / "market"
    market_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "indexcd": "000300",
                "idxtrd01": "2023-01-03",
                "idxtrd05": 4100.0,
                "idxtrd08": 1.0,
                "idxtrd09": "沪深300",
            },
            {
                "indexcd": "000300",
                "idxtrd01": "2023-01-04",
                "idxtrd05": 4018.0,
                "idxtrd08": -2.0,
                "idxtrd09": "沪深300",
            },
            {
                "indexcd": "000001",
                "idxtrd01": "2023-01-04",
                "idxtrd05": 3200.0,
                "idxtrd08": -1.0,
                "idxtrd09": "上证指数",
            },
        ]
    ).to_csv(market_dir / "index_daily.csv", index=False)
    basic_dir = root / "distribute" / "basic"
    basic_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"ImplementDate": "2022-12-31", "Symbol": "000001", "IndustryName": "银行"},
            {"ImplementDate": "2022-12-31", "Symbol": "000002", "IndustryName": "银行"},
            {"ImplementDate": "2022-12-31", "Symbol": "300001", "IndustryName": "软件"},
        ]
    ).to_csv(basic_dir / "STK_INDUSTRYCLASS.csv", index=False)
    DataCatalog(
        root=root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="basic.STK_INDUSTRYCLASS",
                aliases=["STK_INDUSTRYCLASS"],
                csmar_table_code="STK_INDUSTRYCLASS",
                relative_path="distribute/basic/STK_INDUSTRYCLASS.csv",
                format="csv",
                is_static=False,
                date_columns=["ImplementDate"],
                primary_asof_column="ImplementDate",
                symbol_column="Symbol",
            ),
            DatasetSpec(
                dataset_id="stock.daily_returns",
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
                dataset_id="factor_benchmark.adj_factor",
                aliases=[],
                csmar_table_code=None,
                relative_path="teacher/factor_benchmark/adj_factor.parquet",
                format="parquet",
                is_static=False,
                date_columns=["TradingDate"],
                primary_asof_column="TradingDate",
                symbol_column="Symbol",
            ),
            DatasetSpec(
                dataset_id="market.index_daily",
                aliases=[],
                csmar_table_code=None,
                relative_path="distribute/market/index_daily.csv",
                format="csv",
                is_static=False,
                date_columns=["idxtrd01"],
                primary_asof_column="idxtrd01",
                symbol_column="indexcd",
            ),
        ],
    ).save(root / "data_catalog.json")


def _write_strategy(path: Path) -> Path:
    path.write_text(
        """
import pandas as pd

def generate_signals(data):
    current = data.current("stock.daily_returns")
    codes = current["Symbol"].map(str).str.zfill(6)
    current = current.loc[codes.isin(["000001", "000002"])]
    return pd.DataFrame({"code": current["Symbol"], "score": [3, -1][:len(current)]})
""",
        encoding="utf-8",
    )
    return path


def test_group_returns_exclude_non_executable_trade_date_rows() -> None:
    panel = BacktestPanel(
        pd.DataFrame(
            [
                {
                    "date": "2023-01-02",
                    "symbol": "000001",
                    "front_close": 100.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-02",
                    "symbol": "000002",
                    "front_close": 100.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-02",
                    "symbol": "000003",
                    "front_close": 100.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-02",
                    "symbol": "000004",
                    "front_close": 100.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "000001",
                    "front_close": 109.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "000002",
                    "front_close": 95.0,
                    "front_vwap": None,
                    "tradable": True,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "000003",
                    "front_close": 101.0,
                    "front_vwap": 100.0,
                    "tradable": False,
                    "limit_status": 0,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "000004",
                    "front_close": 111.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "limit_status": 1,
                },
            ]
        ).assign(date=lambda df: pd.to_datetime(df["date"]))
    )
    scores = pd.DataFrame(
        [
            {"date": "2023-01-02", "code": "000002", "score": 1.0},
            {"date": "2023-01-02", "code": "000003", "score": 2.0},
            {"date": "2023-01-02", "code": "000004", "score": 3.0},
            {"date": "2023-01-02", "code": "000001", "score": 4.0},
        ]
    )

    returns = _calculate_group_returns(panel, scores, group_count=2)

    assert returns.to_dict("records") == [
        {
            "date": pd.Timestamp("2023-01-03"),
            "group": "group_2",
            "return": pytest.approx(0.09),
        }
    ]


def test_group_returns_use_chinext_twenty_percent_fallback_limit() -> None:
    panel = BacktestPanel(
        pd.DataFrame(
            [
                {
                    "date": "2023-01-02",
                    "symbol": "300001",
                    "front_close": 100.0,
                    "front_vwap": 100.0,
                    "tradable": True,
                    "market_type": 16,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "300001",
                    "front_close": 111.0,
                    "front_vwap": 105.0,
                    "tradable": True,
                    "market_type": 16,
                },
            ]
        ).assign(date=lambda df: pd.to_datetime(df["date"]))
    )
    scores = pd.DataFrame(
        [{"date": "2023-01-02", "code": "300001", "score": 1.0}]
    )

    returns = _calculate_group_returns(panel, scores, group_count=1)

    assert returns.to_dict("records") == [
        {
            "date": pd.Timestamp("2023-01-03"),
            "group": "group_1",
            "return": pytest.approx(111.0 / 105.0 - 1.0),
        }
    ]


def _add_trd_index_dataset(root: Path, rows: list[dict[str, object]]) -> None:
    index_dir = root / "teacher" / "index_metadata" / "index_info"
    index_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(index_dir / "TRD_Index.csv", index=False)
    catalog = DataCatalog.load(root / "data_catalog.json")
    catalog.datasets.append(
        DatasetSpec(
            dataset_id="index_metadata.index_info.TRD_Index",
            aliases=["TRD_Index"],
            csmar_table_code="TRD_Index",
            relative_path="teacher/index_metadata/index_info/TRD_Index.csv",
            format="csv",
            is_static=False,
            date_columns=["Trddt"],
            primary_asof_column="Trddt",
            symbol_column="Indexcd",
        )
    )
    catalog.save(root / "data_catalog.json")


def _add_company_info_dataset(root: Path, rows: list[dict[str, object]]) -> None:
    basic_dir = root / "distribute" / "basic"
    basic_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(basic_dir / "company_info.csv", index=False)
    catalog = DataCatalog.load(root / "data_catalog.json")
    catalog.datasets.append(
        DatasetSpec(
            dataset_id="basic.company_info",
            aliases=[],
            csmar_table_code=None,
            relative_path="distribute/basic/company_info.csv",
            format="csv",
            is_static=True,
            date_columns=["listdt"],
            symbol_column="Symbol",
        )
    )
    catalog.save(root / "data_catalog.json")


def test_run_student_backtest_returns_public_result_contract(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
            },
            "execution": {"max_participation_rate": 1.0, "max_position_weight": 1.0},
        },
    )

    assert isinstance(result, BacktestResult)
    assert set(result.summary.columns) >= {
        "total_return",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "average_turnover",
        "win_rate",
    }
    assert result.daily_returns["date"].tolist() == [
        pd.Timestamp("2023-01-03"),
        pd.Timestamp("2023-01-04"),
    ]
    assert result.daily_returns["daily_return"].tolist() == pytest.approx(
        [0.09, 0.05553620695]
    )
    assert result.net_value["net_value"].round(6).tolist() == [1.09, 1.145536]
    assert result.positions[["date", "code", "weight"]].to_dict("records") == [
        {"date": pd.Timestamp("2023-01-03"), "code": "000001", "weight": 0.5},
        {"date": pd.Timestamp("2023-01-03"), "code": "000002", "weight": -0.5},
        {"date": pd.Timestamp("2023-01-03"), "code": "300001", "weight": 0.0},
        {"date": pd.Timestamp("2023-01-04"), "code": "000001", "weight": 0.5},
        {"date": pd.Timestamp("2023-01-04"), "code": "000002", "weight": -0.5},
        {"date": pd.Timestamp("2023-01-04"), "code": "300001", "weight": 0.0},
    ]
    assert result.turnover["turnover"].tolist() == [1.0, 0.0]
    performance_rows = result.performance_by_year.set_index("period").to_dict("index")
    assert list(result.performance_by_year["period"]) == ["2023", "all"]
    assert performance_rows["2023"]["long"] == pytest.approx(0.5)
    assert performance_rows["2023"]["short"] == pytest.approx(-0.5)
    assert performance_rows["2023"]["long_count"] == 1
    assert performance_rows["2023"]["short_count"] == 1
    assert performance_rows["2023"]["total_return"] == pytest.approx(0.09 + 0.05553620695)
    assert performance_rows["2023"]["annualized_return"] == pytest.approx(
        ((0.09 + 0.05553620695) / 2) * 252
    )
    assert performance_rows["2023"]["turnover"] == pytest.approx(0.5)
    assert set(result.group_daily_returns["group"].unique()) == {"group_1", "group_2"}
    assert result.graph_data["equity"][0]["equity"] == 1.09
    assert result.graph_data["equity_cny"][0]["equity_cny"] == pytest.approx(1_090_000)
    assert result.graph_data["daily_pnl"][0]["pnl_cny"] == pytest.approx(90_000)
    assert result.graph_data["trade_volume"][0] == {
        "date": "2023-01-03",
        "buy_cny": pytest.approx(500_000),
        "sell_cny": pytest.approx(500_000),
    }
    assert result.graph_data["benchmark"] == [
        {
            "date": "2023-01-03",
            "benchmark_return": pytest.approx(0.01),
            "benchmark_equity": pytest.approx(1.01),
            "benchmark_cny": pytest.approx(1_010_000),
        },
        {
            "date": "2023-01-04",
            "benchmark_return": pytest.approx(-0.02),
            "benchmark_equity": pytest.approx(0.99),
            "benchmark_cny": pytest.approx(990_000),
        },
    ]
    assert result.graph_data["alpha"][0]["alpha_cny"] == pytest.approx(1_080_000)
    assert result.diagnostics["strategy_path"].endswith("student_strategy.py")
    assert result.diagnostics["execution_mode"] == "longshort"
    assert "alpha_type" not in result.diagnostics
    assert result.diagnostics["price_policy"] == "front_adjusted"
    assert result.diagnostics["allowed_market_types"] == [1, 4, 16, 32, 64]
    assert result.diagnostics["stale_positions"] == {
        "stale_position_days": 0,
        "max_stale_gross_exposure": pytest.approx(0.0),
        "average_stale_gross_exposure": pytest.approx(0.0),
        "terminal_stale_position_count": 0,
        "terminal_stale_gross_exposure": pytest.approx(0.0),
    }
    assert result.diagnostics["industry_neutralization"] == {
        "enabled": False,
        "dataset": "basic.STK_INDUSTRYCLASS",
        "industry_column": None,
        "signal_rows": 6,
        "neutralized_rows": 0,
        "missing_industry_rows": 0,
        "industry_count": 0,
    }


def test_run_student_backtest_longonly_scores_active_returns_and_keeps_raw_columns(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_min_beta_observations": 2,
                "long_only_risk_free_rate": 0.0175,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 2,
                "max_position_weight": 0.50,
                "max_participation_rate": 1.0,
                "min_listing_days": 0,
            },
        },
    )

    summary = result.summary.iloc[0].to_dict()
    assert summary["total_return"] == pytest.approx(summary["active_total_return"])
    assert summary["annual_return"] == pytest.approx(summary["active_annual_return"])
    assert summary["sharpe"] == pytest.approx(summary["information_ratio"])
    assert summary["max_drawdown"] == pytest.approx(summary["active_max_drawdown"])
    assert summary["calmar"] == pytest.approx(summary["active_calmar"])
    assert "beta" in summary
    assert "tracking_error" in summary
    assert "raw_total_return" in summary
    assert "raw_sharpe" in summary
    assert "raw_max_drawdown" in summary
    assert "raw_calmar" in summary
    assert summary["risk_free_rate"] == pytest.approx(0.0175)
    assert summary["risk_free_daily_return"] == pytest.approx(0.0175 / 252)
    assert result.daily_returns.columns.tolist() == [
        "date",
        "daily_return",
        "portfolio_return",
        "long_return",
        "short_return",
        "benchmark_return",
        "risk_free_return",
        "active_return",
        "scored_daily_return",
    ]
    assert result.daily_returns["risk_free_return"].tolist() == pytest.approx([0.0175 / 252] * 2)
    raw_excess_returns = result.daily_returns["portfolio_return"] - (0.0175 / 252)
    assert summary["raw_sharpe"] == pytest.approx(
        (252**0.5) * raw_excess_returns.mean() / raw_excess_returns.std(ddof=1)
    )
    assert result.daily_returns["scored_daily_return"].tolist() == pytest.approx(
        result.daily_returns["active_return"].tolist()
    )
    assert result.daily_returns["daily_return"].tolist() == pytest.approx(
        result.daily_returns["active_return"].tolist()
    )
    assert result.daily_returns["portfolio_return"].tolist() != pytest.approx(
        result.daily_returns["daily_return"].tolist()
    )
    assert result.net_value["net_value"].tolist() == pytest.approx(
        1.0 + result.daily_returns["active_return"].cumsum()
    )
    raw_graph_equity = 1.0 + result.daily_returns["portfolio_return"].cumsum()
    assert [point["equity"] for point in result.graph_data["equity"]] == pytest.approx(
        raw_graph_equity.tolist()
    )
    assert [
        point["daily_return"] for point in result.graph_data["daily_pnl"]
    ] == pytest.approx(result.daily_returns["portfolio_return"].tolist())
    assert result.graph_data["alpha"][0]["alpha_return"] == pytest.approx(
        result.daily_returns.loc[0, "active_return"]
    )
    assert result.diagnostics["execution_mode"] == "longonly"
    assert "alpha_type" not in result.diagnostics
    assert result.diagnostics["long_only_scoring"]["benchmark"] == "hs300"
    assert result.diagnostics["long_only_scoring"]["risk_free_rate"] == pytest.approx(0.0175)
    assert result.diagnostics["long_only_scoring"]["risk_free_daily_return"] == pytest.approx(0.0175 / 252)


def test_run_student_backtest_unbenchmarked_longonly_tolerates_missing_index(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    catalog = DataCatalog.load(data_root / "data_catalog.json")
    DataCatalog(
        root=catalog.root,
        datasets=[
            spec for spec in catalog.datasets if spec.dataset_id != "market.index_daily"
        ],
    ).save(data_root / "data_catalog.json")

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_benchmark": "none",
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 2,
                "max_position_weight": 0.50,
                "max_participation_rate": 1.0,
                "min_listing_days": 0,
            },
        },
    )

    summary = result.summary.iloc[0].to_dict()
    assert result.positions["weight"].min() >= 0
    assert result.daily_returns["daily_return"].tolist() == pytest.approx(
        result.daily["portfolio_return"].tolist()
    )
    assert "active_return" not in result.daily_returns.columns
    assert "scored_daily_return" not in result.daily_returns.columns
    assert summary["total_return"] == pytest.approx(summary["raw_total_return"])
    assert summary["sharpe"] == pytest.approx(summary["raw_sharpe"])
    assert result.graph_data["benchmark"] == []
    assert result.graph_data["alpha"] == []
    assert result.diagnostics["long_only_scoring"] == {
        "benchmark": "none",
        "benchmark_available": False,
        "scoring_basis": "portfolio_return",
    }


def test_run_student_backtest_ignores_legacy_alpha_type_for_mode(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "alpha_type": "longonly",
            },
            "execution": {
                "long_only": False,
            },
        },
    )

    assert result.diagnostics["execution_mode"] == "longshort"
    assert result.positions["weight"].min() < 0
    assert "active_return" not in result.daily_returns.columns


def test_run_student_backtest_keeps_legacy_longshort_participation_model(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
            },
            "execution": {
                "long_only": False,
                "max_participation_rate": 0.10,
                "max_position_weight": 1.0,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.5, "000002": -0.5, "300001": 0.0}
    )


def test_run_student_backtest_filters_longonly_universe_on_signal_date(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    daily_path = data_root / "distribute" / "stock" / "daily_returns.parquet"
    daily = pd.read_parquet(daily_path)
    illiquid_signal_date = (
        (daily["TradingDate"] == "2023-01-03")
        & (daily["Symbol"].map(str).str.zfill(6) == "000001")
    )
    daily.loc[illiquid_signal_date, ["Dnshrtrd", "Dnvaltrd"]] = 0.0
    execution_date = (
        (daily["TradingDate"] == "2023-01-04")
        & (daily["Symbol"].map(str).str.zfill(6) == "000001")
    )
    daily.loc[execution_date, "Clsprc"] = 11.4
    daily.to_parquet(daily_path, index=False)
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_min_beta_observations": 2,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 1,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 0,
            },
        },
    )

    positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-04")
    ].set_index("code")["weight"].to_dict()
    assert positions == pytest.approx(
        {"000001": 0.0, "000002": 1.0, "300001": 0.0}
    )
    assert result.diagnostics["investable_universe"]["non_tradable_rows"] == 1
    assert (
        result.diagnostics["investable_universe"]["selection_information_date"]
        == "signal_date"
    )


def test_run_student_backtest_does_not_use_next_day_tradability_to_promote_runner_up(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    daily_path = data_root / "distribute" / "stock" / "daily_returns.parquet"
    daily = pd.read_parquet(daily_path)
    blocked_execution = (
        (daily["TradingDate"] == "2023-01-04")
        & (daily["Symbol"].map(str).str.zfill(6) == "000001")
    )
    daily.loc[blocked_execution, ["Dnshrtrd", "Dnvaltrd"]] = 0.0
    daily.to_parquet(daily_path, index=False)
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    current = data.current("stock.daily_returns")
    signal_date = pd.Timestamp(current["TradingDate"].iloc[0])
    if signal_date < pd.Timestamp("2023-01-03"):
        return pd.Series(dtype=float)
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_min_beta_observations": 2,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 1,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 0,
            },
        },
    )

    positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-04")
    ].set_index("code")["weight"].to_dict()
    assert positions == pytest.approx(
        {"000001": 0.0, "000002": 0.0, "300001": 0.0}
    )


def test_run_student_backtest_does_not_apply_longonly_position_cap_to_longshort(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
            },
            "execution": {
                "long_only": False,
                "max_position_weight": 0.05,
                "max_participation_rate": 1.0,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.5, "000002": -0.5, "300001": 0.0}
    )
    assert result.diagnostics["investable_universe"] is None


def test_run_student_backtest_does_not_apply_longonly_listing_filter_to_longshort(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    _add_company_info_dataset(
        data_root,
        [
            {"Symbol": "000001", "listdt": "2023-01-01"},
            {"Symbol": "000002", "listdt": "2020-01-01"},
            {"Symbol": "300001", "listdt": "2020-01-01"},
        ],
    )
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
            },
            "execution": {
                "long_only": False,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 60,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.5, "000002": -0.5, "300001": 0.0}
    )
    assert result.diagnostics["investable_universe"] is None
    assert result.diagnostics["long_only_universe"] is None


def test_run_student_backtest_filters_longonly_recent_listings(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    _add_company_info_dataset(
        data_root,
        [
            {"Symbol": "000001", "listdt": "2023-01-01"},
            {"Symbol": "000002", "listdt": "2020-01-01"},
            {"Symbol": "300001", "listdt": "2020-01-01"},
        ],
    )
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_min_beta_observations": 2,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 2,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 60,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.0, "000002": 1.0, "300001": 0.0}
    )
    assert result.diagnostics["long_only_universe"]["recent_listing_rows"] > 0
    assert result.diagnostics["long_only_universe"]["min_listing_days"] == 60


def test_run_student_backtest_excludes_missing_listing_dates(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    _add_company_info_dataset(
        data_root,
        [
            {"Symbol": "000001", "listdt": "2023-01-01"},
        ],
    )
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "long_only_min_beta_observations": 2,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 2,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 60,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.0, "000002": 0.0, "300001": 0.0}
    )
    assert result.diagnostics["long_only_universe"]["missing_listing_date_rows"] > 0
    assert result.diagnostics["long_only_universe"]["recent_listing_rows"] > 0


def test_run_student_backtest_requires_listing_source_when_filter_enabled(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 100.0, "000002": 1.0})
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"min_listing_days=60 requires basic\.company_info.*unavailable",
    ):
        run_student_backtest(
            strategy_path,
            data_root,
            {
                "backtest": {
                    "data_start": "2023-01-02",
                    "scoring_start": "2023-01-03",
                    "scoring_end": "2023-01-04",
                    "capital": 1_000_000,
                    "group_count": 2,
                    "long_only_min_beta_observations": 2,
                },
                "execution": {
                    "long_only": True,
                    "long_only_weighting": "rank_equal",
                    "long_only_target_count": 2,
                    "max_position_weight": 1.0,
                    "max_participation_rate": 1.0,
                    "min_listing_days": 60,
                },
            },
        )


def test_run_student_backtest_uses_full_trd_index_hs300_when_market_index_is_partial(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    pd.DataFrame(
        [
            {
                "indexcd": "000300",
                "idxtrd01": "2023-01-04",
                "idxtrd05": 4018.0,
                "idxtrd08": -2.0,
                "idxtrd09": "沪深300",
            },
        ]
    ).to_csv(data_root / "distribute" / "market" / "index_daily.csv", index=False)
    _add_trd_index_dataset(
        data_root,
        [
            {
                "Indexcd": "000300",
                "Trddt": "2023-01-03",
                "Clsindex": 4100.0,
                "Retindex": 0.005,
            },
            {
                "Indexcd": "000300",
                "Trddt": "2023-01-04",
                "Clsindex": 4128.7,
                "Retindex": 0.007,
            },
        ],
    )

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "data_start": "2023-01-02",
            "scoring_start": "2023-01-03",
            "scoring_end": "2023-01-04",
            "capital": 1_000_000,
            "group_count": 2,
        },
    )

    assert result.graph_data["benchmark"] == [
        {
            "date": "2023-01-03",
            "benchmark_return": pytest.approx(0.005),
            "benchmark_equity": pytest.approx(1.005),
            "benchmark_cny": pytest.approx(1_005_000),
        },
        {
            "date": "2023-01-04",
            "benchmark_return": pytest.approx(0.007),
            "benchmark_equity": pytest.approx(1.012),
            "benchmark_cny": pytest.approx(1_012_000),
        },
    ]


def test_run_student_backtest_includes_chinext_in_default_a_share_scope(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    return pd.Series({"000001": 1.0, "300001": 100.0})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "data_start": "2023-01-02",
            "scoring_start": "2023-01-03",
            "scoring_end": "2023-01-04",
            "capital": 1_000_000,
            "group_count": 2,
        },
    )

    assert "300001" in result.positions["code"].unique().tolist()
    assert result.diagnostics["allowed_market_types"] == [1, 4, 16, 32, 64]


def test_run_student_backtest_applies_configured_industry_neutralization(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
import pandas as pd

def generate_signals(data):
    current = data.current("stock.daily_returns")
    scores = {"000001": 3.0, "000002": 1.0, "300001": 10.0}
    return pd.Series({str(code).zfill(6): scores[str(code).zfill(6)] for code in current["Symbol"]})
""",
        encoding="utf-8",
    )

    result = run_student_backtest(
        strategy_path,
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 3,
                "industry_neutralization": True,
            },
            "execution": {
                "allowed_market_types": [1, 4, 16],
                "max_participation_rate": 1.0,
                "max_position_weight": 1.0,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.5, "000002": -0.5, "300001": 0.0}
    )
    assert result.diagnostics["industry_neutralization"] == {
        "enabled": True,
        "dataset": "basic.STK_INDUSTRYCLASS",
        "industry_column": "IndustryName",
        "signal_rows": 9,
        "neutralized_rows": 9,
        "missing_industry_rows": 0,
        "industry_count": 2,
    }
    assert "short_total_return" in result.summary.columns
    assert "long_total_return" in result.summary.columns
    assert "annualized_short_profit" in result.summary.columns
    assert {"daily_return", "long_return", "short_return"}.issubset(
        set(result.daily_returns.columns)
    )


def test_run_student_backtest_longonly_rank_equal_skips_zeroed_missing_industries(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    pd.DataFrame(
        [
            {"ImplementDate": "2023-01-05", "Symbol": "000001", "IndustryName": "银行"},
            {"ImplementDate": "2023-01-05", "Symbol": "000002", "IndustryName": "银行"},
        ]
    ).to_csv(data_root / "distribute" / "basic" / "STK_INDUSTRYCLASS.csv", index=False)

    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "backtest": {
                "data_start": "2023-01-02",
                "scoring_start": "2023-01-03",
                "scoring_end": "2023-01-04",
                "capital": 1_000_000,
                "group_count": 2,
                "industry_neutralization": True,
                "long_only_min_beta_observations": 2,
            },
            "execution": {
                "long_only": True,
                "long_only_weighting": "rank_equal",
                "long_only_target_count": 2,
                "max_position_weight": 1.0,
                "max_participation_rate": 1.0,
                "min_listing_days": 0,
            },
        },
    )

    first_scoring_positions = result.positions[
        result.positions["date"] == pd.Timestamp("2023-01-03")
    ].set_index("code")["weight"].to_dict()
    assert first_scoring_positions == pytest.approx(
        {"000001": 0.0, "000002": 0.0, "300001": 0.0}
    )
    assert result.diagnostics["industry_neutralization"]["missing_industry_rows"] > 0


def test_run_student_backtest_preflights_industry_neutralization_before_strategy(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    catalog = DataCatalog.load(data_root / "data_catalog.json")
    catalog.datasets = [
        spec
        for spec in catalog.datasets
        if spec.dataset_id != "basic.STK_INDUSTRYCLASS"
    ]
    catalog.save(data_root / "data_catalog.json")
    strategy_path = tmp_path / "student_strategy.py"
    strategy_path.write_text(
        """
def generate_signals(data):
    raise RuntimeError("strategy should not execute")
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="industry_neutralization.*basic\\.STK_INDUSTRYCLASS",
    ):
        run_student_backtest(
            strategy_path,
            data_root,
            {
                "backtest": {
                    "data_start": "2023-01-02",
                    "scoring_start": "2023-01-03",
                    "scoring_end": "2023-01-04",
                    "industry_neutralization": True,
                }
            },
        )


def test_write_backtest_report_persists_required_artifacts(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    result = run_student_backtest(
        _write_strategy(tmp_path / "student_strategy.py"),
        data_root,
        {
            "data_start": "2023-01-02",
            "scoring_start": "2023-01-03",
            "scoring_end": "2023-01-04",
            "group_count": 2,
        },
    )

    written = write_backtest_report(result, tmp_path / "report")

    expected = {
        "summary.csv",
        "daily_returns.parquet",
        "net_value.parquet",
        "turnover.parquet",
        "group_daily_returns.parquet",
        "performance_by_year.csv",
        "graph_data.json",
        "diagnostics.json",
    }
    assert {path.name for path in written} == expected
    assert pd.read_csv(tmp_path / "report" / "summary.csv").loc[0, "trading_days"] == 2
    assert pd.read_csv(tmp_path / "report" / "performance_by_year.csv")["period"].tolist() == [
        "2023",
        "all",
    ]
    daily_returns = pd.read_parquet(tmp_path / "report" / "daily_returns.parquet")
    assert daily_returns.shape == (2, 4)
    assert daily_returns.columns.tolist() == [
        "date",
        "daily_return",
        "long_return",
        "short_return",
    ]
    diagnostics = json.loads((tmp_path / "report" / "diagnostics.json").read_text())
    assert diagnostics["trading_dates"] == [
        "2023-01-02",
        "2023-01-03",
        "2023-01-04",
    ]
    assert diagnostics["scoring_dates"] == ["2023-01-03", "2023-01-04"]
