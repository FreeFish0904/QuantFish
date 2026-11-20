from pathlib import Path

import pandas as pd
import pytest

from quantfish.data import DataBundle, FutureDataAccessError
from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.data.releases import build_release
from xlsx_fixtures import write_xlsx_field_dictionary


def _build_fixture_release(tmp_path: Path) -> Path:
    source = tmp_path / "new_data"

    forecast_dir = source / "teacher" / "financial_supplement" / "forecast_vs_report"
    forecast_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"Stkcd": "000001", "PubliDate": "2022-12-30", "Value": 1},
            {"Stkcd": "000001", "PubliDate": "2023-01-10", "Value": 2},
            {"Stkcd": "000002", "PubliDate": "2023-01-05", "Value": 5},
            {"Stkcd": "000001", "PubliDate": "2023-02-15", "Value": 3},
        ]
    ).to_csv(forecast_dir / "BF_FORECAST.csv", index=False)

    index_dir = source / "teacher" / "index_metadata" / "index_info"
    index_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"Indexcd": "000001", "Trddt": "2023-01-31", "Retindex": 0.01},
            {"Indexcd": "000001", "Trddt": "2023-02-01", "Retindex": 0.02},
            {"Indexcd": "000001", "Trddt": "2023-02-02", "Retindex": 0.03},
        ]
    ).to_csv(index_dir / "TRD_Index.csv", index=False)

    static_dir = source / "distribute" / "basic"
    static_dir.mkdir(parents=True)
    pd.DataFrame([{"Code": "A", "Name": "Alpha"}]).to_csv(static_dir / "lookup.csv", index=False)

    output = tmp_path / "release"
    build_release(source, output, end="2025-12-31")
    return output


def test_dated_bundle_load_current_history_latest_and_static_data(tmp_path: Path) -> None:
    release = _build_fixture_release(tmp_path)
    data = DataBundle(release).at("2023-01-31")

    forecast = data.load("BF_FORECAST")
    assert forecast["Value"].tolist() == [1, 2, 5]

    current_index = data.current("TRD_Index")
    assert current_index["Retindex"].tolist() == [0.01]

    history = data.history("TRD_Index", lookback_days=1)
    assert history["Trddt"].tolist() == ["2023-01-31"]

    latest = data.latest("BF_FORECAST", by="Stkcd").sort_values("Stkcd")
    assert latest[["Stkcd", "Value"]].to_dict("records") == [
        {"Stkcd": "000001", "Value": 2},
        {"Stkcd": "000002", "Value": 5},
    ]

    static = data.load("basic.lookup")
    assert static.to_dict("records") == [{"Code": "A", "Name": "Alpha"}]


def test_dated_bundle_rejects_future_queries(tmp_path: Path) -> None:
    release = _build_fixture_release(tmp_path)
    data = DataBundle(release).at("2023-01-31")

    with pytest.raises(FutureDataAccessError):
        data.load("BF_FORECAST", end="2023-02-01")


def test_dated_bundle_filters_with_internal_date_column_when_projecting_columns(
    tmp_path: Path,
) -> None:
    release = _build_fixture_release(tmp_path)
    data = DataBundle(release).at("2023-01-31")

    forecast = data.load("BF_FORECAST", columns=["Value"])
    current_index = data.current("TRD_Index", columns=["Retindex"])

    assert list(forecast.columns) == ["Value"]
    assert forecast["Value"].tolist() == [1, 2, 5]
    assert list(current_index.columns) == ["Retindex"]
    assert current_index["Retindex"].tolist() == [0.01]


def test_dated_bundle_latest_uses_internal_group_and_date_columns_when_projecting(
    tmp_path: Path,
) -> None:
    release = _build_fixture_release(tmp_path)
    data = DataBundle(release).at("2023-01-31")

    latest = data.latest("BF_FORECAST", by="Stkcd", columns=["Value"])

    assert list(latest.columns) == ["Value"]
    assert sorted(latest["Value"].tolist()) == [2, 5]


def test_dated_bundle_coerces_requested_numeric_columns(tmp_path: Path) -> None:
    release = tmp_path / "release"
    stock_dir = release / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Ret": "0.10",
                "Amount": "1000",
                "Note": "keep-text",
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "Ret": "bad-value",
                "Amount": "",
                "Note": "still-text",
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000001",
                "Ret": "0.03",
                "Amount": "1200",
                "Note": "next-day",
            },
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)

    forecast_dir = release / "teacher" / "forecast"
    forecast_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "Stkcd": "000001",
                "PubliDate": "2023-01-01",
                "High": "12.5",
                "Label": "old",
            },
            {
                "Stkcd": "000001",
                "PubliDate": "2023-01-03",
                "High": "not-a-number",
                "Label": "latest-bad",
            },
            {
                "Stkcd": "000002",
                "PubliDate": "2023-01-02",
                "High": "7.5",
                "Label": "latest-good",
            },
        ]
    ).to_csv(forecast_dir / "BF_FORECAST.csv", index=False)

    DataCatalog(
        root=release.as_posix(),
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
            ),
            DatasetSpec(
                dataset_id="financial_supplement.forecast.BF_FORECAST",
                aliases=["BF_FORECAST"],
                csmar_table_code="BF_FORECAST",
                relative_path="teacher/forecast/BF_FORECAST.csv",
                format="csv",
                is_static=False,
                date_columns=["PubliDate"],
                primary_asof_column="PubliDate",
                symbol_column="Stkcd",
            ),
        ],
    ).save(release / "data_catalog.json")
    data = DataBundle(release).at("2023-01-03")

    current = data.current(
        "stock.daily_returns",
        columns=["Symbol", "Ret", "Amount", "Note"],
        numeric_columns=["Ret", "Amount"],
    )
    assert current["Ret"].tolist()[0] == pytest.approx(0.10)
    assert pd.isna(current["Ret"].tolist()[1])
    assert current["Amount"].tolist()[0] == pytest.approx(1000.0)
    assert pd.isna(current["Amount"].tolist()[1])
    assert current["Symbol"].tolist() == ["000001", "000002"]
    assert current["Note"].tolist() == ["keep-text", "still-text"]

    history = data.history(
        "stock.daily_returns",
        lookback_days=1,
        columns=["Ret"],
        numeric_columns=["Ret"],
    )
    assert history["Ret"].tolist()[0] == pytest.approx(0.10)
    assert pd.isna(history["Ret"].tolist()[1])

    loaded = data.load(
        "stock.daily_returns",
        start="2023-01-03",
        end="2023-01-03",
        columns=["Ret", "Note"],
        numeric_columns=["Ret"],
    )
    assert pd.isna(loaded["Ret"].tolist()[1])
    assert loaded["Note"].tolist() == ["keep-text", "still-text"]

    latest = data.latest(
        "BF_FORECAST",
        by="Stkcd",
        columns=["Stkcd", "High", "Label"],
        numeric_columns=["High"],
    ).sort_values("Stkcd")
    assert pd.isna(latest.iloc[0]["High"])
    assert latest.iloc[0]["Label"] == "latest-bad"
    assert latest.iloc[1]["High"] == pytest.approx(7.5)


def test_dated_bundle_rejects_unknown_numeric_columns(tmp_path: Path) -> None:
    release = _build_fixture_release(tmp_path)
    data = DataBundle(release).at("2023-01-31")

    with pytest.raises(KeyError, match="MissingValue"):
        data.current("TRD_Index", columns=["Retindex"], numeric_columns=["MissingValue"])


def test_dated_bundle_loads_datago_tables_by_alias_with_pub_date_bounds(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    table_dir = (
        source
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "股吧量化舆情表(交易时段分组)_fullpacked_data"
    )
    table_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "Stock_Id": "600153",
                "Pub_Date": "2023-01-03",
                "Trade_Time": 1,
                "Reads_Announce_Sum": "10",
            },
            {
                "Stock_Id": "600745",
                "Pub_Date": "2023-02-01",
                "Trade_Time": 0,
                "Reads_Announce_Sum": "25",
            },
        ]
    ).to_csv(table_dir / "股吧量化舆情表(交易时段分组).csv", index=False)
    write_xlsx_field_dictionary(
        table_dir / "《股吧量化舆情数据库》字段说明.xlsx",
        "股吧量化舆情表(交易时段分组)",
        [
            ["字段", "数据类型", "字段说明"],
            ["Stock_Id", "char", "股票代码"],
            ["Pub_Date", "datetime", "日期"],
            ["Reads_Announce_Sum", "int", "公告被阅读总数"],
        ],
    )
    release = tmp_path / "release"
    build_release(source, release, start="2023-01-01", end="2025-12-31")

    data = DataBundle(release).at("2023-01-31")
    loaded = data.load(
        "股吧量化舆情表(交易时段分组)",
        columns=["Stock_Id", "Reads_Announce_Sum"],
        numeric_columns=["Reads_Announce_Sum"],
    )

    assert loaded["Stock_Id"].tolist() == ["600153"]
    assert loaded["Reads_Announce_Sum"].tolist() == [pytest.approx(10.0)]

    with pytest.raises(FutureDataAccessError):
        data.load("股吧量化舆情表(交易时段分组)", end="2023-02-01")
