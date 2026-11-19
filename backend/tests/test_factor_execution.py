from pathlib import Path

import pandas as pd
import pytest

from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.factor_execution import (
    StrategyExecutionConfig,
    StrategySignalError,
    execute_student_strategy,
)
from quantfish.factor_execution.strategy_execution import CachedDataBundle


def _write_release(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2023-01-03", "Symbol": "1", "Ret": 0.10, "Markettype": 1},
            {"TradingDate": "2023-01-03", "Symbol": "000002", "Ret": -0.05, "Markettype": 4},
            {"TradingDate": "2023-01-03", "Symbol": "300001", "Ret": 0.90, "Markettype": 16},
            {"TradingDate": "2023-01-04", "Symbol": "1", "Ret": 0.03, "Markettype": 1},
            {"TradingDate": "2023-01-04", "Symbol": "000002", "Ret": 0.04, "Markettype": 4},
            {"TradingDate": "2023-01-04", "Symbol": "300001", "Ret": -0.30, "Markettype": 16},
            {"TradingDate": "2023-01-05", "Symbol": "000002", "Ret": 0.01, "Markettype": 4},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    catalog = DataCatalog(
        root=root.as_posix(),
        datasets=[
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
            )
        ],
    )
    catalog.save(root / "data_catalog.json")


def _write_strategy(path: Path, body: str) -> Path:
    path.write_text("import pandas as pd\n" + body, encoding="utf-8")
    return path


def test_execute_student_strategy_iterates_canonical_dates_and_normalizes_scores(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    calls_path = tmp_path / "calls.txt"
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        f"""
from pathlib import Path

CALLS = Path({str(calls_path)!r})

def generate_signals(data):
    current = data.current("stock.daily_returns")
    CALLS.write_text(CALLS.read_text() + str(data.date.date()) + "\\n" if CALLS.exists() else str(data.date.date()) + "\\n")
    return pd.DataFrame({{"code": current["Symbol"], "score": [2, -1, 0][:len(current)]}})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-04"),
    )

    assert calls_path.read_text(encoding="utf-8").splitlines() == [
        "2023-01-03",
        "2023-01-04",
    ]
    assert result.scores.to_dict("records") == [
        {"date": pd.Timestamp("2023-01-03"), "code": "000001", "score": 2.0},
        {"date": pd.Timestamp("2023-01-03"), "code": "000002", "score": -1.0},
        {"date": pd.Timestamp("2023-01-03"), "code": "300001", "score": 0.0},
        {"date": pd.Timestamp("2023-01-04"), "code": "000001", "score": 2.0},
        {"date": pd.Timestamp("2023-01-04"), "code": "000002", "score": -1.0},
        {"date": pd.Timestamp("2023-01-04"), "code": "300001", "score": 0.0},
    ]
    assert result.diagnostics["trading_dates"] == ["2023-01-03", "2023-01-04"]
    assert result.diagnostics["allowed_market_types"] == [1, 4, 16, 32, 64]


def test_execute_student_strategy_uses_configured_market_scope(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    current = data.current("stock.daily_returns", columns=["Symbol"])
    return pd.Series(range(len(current)), index=current["Symbol"])
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(
            data_start="2023-01-03",
            scoring_end="2023-01-04",
            allowed_market_types=(16,),
        ),
    )

    assert result.scores["code"].unique().tolist() == ["300001"]
    assert result.diagnostics["allowed_market_types"] == [16]


def test_execute_student_strategy_accepts_series_output(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    return pd.Series({"1": 1.25, "000002": -0.5})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
    )

    assert result.scores[["code", "score"]].to_dict("records") == [
        {"code": "000001", "score": 1.25},
        {"code": "000002", "score": -0.5},
    ]


def test_execute_student_strategy_normalizes_exchange_qualified_codes(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    return pd.Series({"1.SH": 1.0, "SZ000002": 2.0, "300001.XSHE": 3.0})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
    )

    assert result.scores[["code", "score"]].to_dict("records") == [
        {"code": "000001", "score": 1.0},
        {"code": "000002", "score": 2.0},
        {"code": "300001", "score": 3.0},
    ]


def test_execute_student_strategy_passes_bound_date_and_allows_nan_scores(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data, date):
    assert str(data.date.date()) == str(date.date())
    return pd.DataFrame({"code": ["1", "000002"], "score": [float("nan"), 3.0]})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
    )

    assert pd.isna(result.scores.loc[result.scores["code"] == "000001", "score"].iloc[0])
    assert result.scores.loc[result.scores["code"] == "000002", "score"].iloc[0] == 3.0


def test_execute_student_strategy_compiles_generate_signals_signature_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data, date):
    current = data.current("stock.daily_returns", columns=["Symbol"])
    return pd.Series(range(len(current)), index=current["Symbol"])
""",
    )
    import quantfish.factor_execution.strategy_execution as strategy_execution

    original_signature = strategy_execution.inspect.signature
    calls = {"count": 0}

    def counting_signature(callable_obj):
        calls["count"] += 1
        return original_signature(callable_obj)

    monkeypatch.setattr(strategy_execution.inspect, "signature", counting_signature)

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-04"),
    )

    assert calls["count"] == 1
    assert result.diagnostics["trading_dates"] == ["2023-01-03", "2023-01-04"]


def test_execute_student_strategy_converts_infinite_scores_to_nan(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    numerator = pd.Series([1.0, -2.0])
    denominator = pd.Series([0.0, 0.0])
    score = numerator / denominator
    return pd.DataFrame({"code": ["1", "000002"], "score": score})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
    )

    scores = result.scores.set_index("code")["score"]
    assert pd.isna(scores["000001"])
    assert pd.isna(scores["000002"])


def test_execute_student_strategy_exposes_numeric_column_coercion(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    stock_dir = data_root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2023-01-03", "Symbol": "1", "Ret": "0.10"},
            {"TradingDate": "2023-01-03", "Symbol": "000002", "Ret": "bad-value"},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    DataCatalog(
        root=data_root.as_posix(),
        datasets=[
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
            )
        ],
    ).save(data_root / "data_catalog.json")
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    current = data.current(
        "stock.daily_returns",
        columns=["Symbol", "Ret"],
        numeric_columns=["Ret"],
    )
    return pd.Series(-current["Ret"].values, index=current["Symbol"])
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
    )

    scores = result.scores.set_index("code")["score"]
    assert scores["000001"] == pytest.approx(-0.10)
    assert pd.isna(scores["000002"])


def test_execute_student_strategy_hides_raw_bundle_escape_hatch(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    raw = data.bundle.load_raw("stock.daily_returns")
    has_future = (pd.to_datetime(raw["TradingDate"]) > data.date).any()
    return pd.Series({"000001": int(has_future)})
""",
    )

    with pytest.raises(AttributeError, match="bundle"):
        execute_student_strategy(
            strategy_path,
            data_root,
            StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
        )


def test_cached_data_bundle_reuses_parsed_date_series(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    calls = {"count": 0}

    import quantfish.data.bundle as bundle_module

    original_date_series = bundle_module._date_series

    def counting_date_series(series: pd.Series) -> pd.Series:
        calls["count"] += 1
        return original_date_series(series)

    monkeypatch.setattr(bundle_module, "_date_series", counting_date_series)
    bundle = CachedDataBundle(data_root)

    bundle.at("2023-01-03").current("stock.daily_returns")
    bundle.at("2023-01-04").current("stock.daily_returns")

    assert calls["count"] == 1


def test_cached_data_bundle_current_results_do_not_mutate_cached_raw_data(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    bundle = CachedDataBundle(data_root)

    current = bundle.at("2023-01-03").current("stock.daily_returns")
    current.loc[:, "Ret"] = 999.0

    reloaded = bundle.at("2023-01-03").current("stock.daily_returns")
    next_day = bundle.at("2023-01-04").current("stock.daily_returns")

    assert reloaded["Ret"].tolist() == [0.10, -0.05, 0.90]
    assert next_day["Ret"].tolist() == [0.03, 0.04, -0.30]


def test_cached_data_bundle_bounds_raw_and_date_caches(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    bundle = CachedDataBundle(data_root, max_cache_entries=1)

    bundle.at("2023-01-03").current("stock.daily_returns", columns=["Symbol"])
    bundle.at("2023-01-04").current("stock.daily_returns", columns=["TradingDate"])

    assert len(bundle._raw_cache) <= 1
    assert len(bundle._date_cache) <= 1
    assert len(bundle._date_index_cache) <= 1


def test_execute_student_strategy_requires_generate_signals_callable(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(tmp_path / "student_strategy.py", "generate_signals = 1\n")

    with pytest.raises(StrategySignalError, match="generate_signals"):
        execute_student_strategy(
            strategy_path,
            data_root,
            StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
        )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
def generate_signals(data):
    return pd.DataFrame({"code": ["1", "000001"], "score": [1, 2]})
""",
            "duplicate",
        ),
        (
            """
def generate_signals(data):
    return pd.DataFrame({"code": ["1"], "score": ["not-a-number"]})
""",
            "numeric",
        ),
    ],
)
def test_execute_student_strategy_rejects_invalid_scores(
    tmp_path: Path, body: str, message: str
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(tmp_path / "student_strategy.py", body)

    with pytest.raises(StrategySignalError, match=message):
        execute_student_strategy(
            strategy_path,
            data_root,
            StrategyExecutionConfig(data_start="2023-01-03", scoring_end="2023-01-03"),
        )


def test_max_trading_dates_visits_only_the_most_recent_dates(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    current = data.current("stock.daily_returns")
    return pd.DataFrame({"code": current["Symbol"], "score": range(len(current))})
""",
    )

    result = execute_student_strategy(
        strategy_path,
        data_root,
        StrategyExecutionConfig(
            data_start="2023-01-03",
            scoring_end="2023-01-05",
            max_trading_dates=2,
        ),
    )

    assert result.diagnostics["trading_dates"] == ["2023-01-04", "2023-01-05"]
    assert result.diagnostics["trading_dates_checked"] == 2
    assert result.diagnostics["max_trading_dates"] == 2
    assert sorted(result.scores["date"].unique().tolist()) == [
        pd.Timestamp("2023-01-04"),
        pd.Timestamp("2023-01-05"),
    ]


def test_max_trading_dates_must_be_positive(tmp_path: Path) -> None:
    data_root = tmp_path / "release"
    _write_release(data_root)
    strategy_path = _write_strategy(
        tmp_path / "student_strategy.py",
        """
def generate_signals(data):
    return pd.DataFrame({"code": ["1"], "score": [1.0]})
""",
    )

    with pytest.raises(StrategySignalError, match="max_trading_dates must be positive"):
        execute_student_strategy(
            strategy_path,
            data_root,
            StrategyExecutionConfig(
                data_start="2023-01-03",
                scoring_end="2023-01-05",
                max_trading_dates=0,
            ),
        )
