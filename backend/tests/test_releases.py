import re
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import quantfish.data.releases as releases_module
from quantfish.data.catalog import DataCatalog
from quantfish.data.releases import build_release, build_releases_from_config, main
from quantfish.data.scoring_datasets import scoring_required_dataset_ids
from quantfish.platform_config import (
    ConfigRepository,
    DataReleasesConfig,
    PlatformConfig,
)
from xlsx_fixtures import write_xlsx_field_dictionary


def test_scoring_dataset_requirements_follow_enabled_backtest_features() -> None:
    default = PlatformConfig.default()

    assert scoring_required_dataset_ids(default) == (
        "stock.daily_returns",
        "factor_benchmark.adj_factor",
        "basic.company_info",
        "market.index_daily",
    )

    long_short = replace(
        default,
        execution=replace(default.execution, long_only=False),
    )
    assert scoring_required_dataset_ids(long_short) == (
        "stock.daily_returns",
        "factor_benchmark.adj_factor",
    )

    long_only_without_listing_filter = replace(
        default,
        execution=replace(default.execution, min_listing_days=0),
    )
    assert scoring_required_dataset_ids(long_only_without_listing_filter) == (
        "stock.daily_returns",
        "factor_benchmark.adj_factor",
        "market.index_daily",
    )

    unbenchmarked_long_only = replace(
        default,
        backtest=replace(default.backtest, long_only_benchmark="none"),
    )
    assert scoring_required_dataset_ids(unbenchmarked_long_only) == (
        "stock.daily_returns",
        "factor_benchmark.adj_factor",
        "basic.company_info",
    )

    configured = replace(
        default,
        backtest=replace(default.backtest, industry_neutralization=True),
        execution=replace(default.execution, long_only=True),
    )
    assert scoring_required_dataset_ids(configured) == (
        "stock.daily_returns",
        "factor_benchmark.adj_factor",
        "basic.STK_INDUSTRYCLASS",
        "basic.company_info",
        "market.index_daily",
    )


def test_release_builder_preserves_structure_and_filters_hidden_test_dates(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2022-12-30", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2023-01-03", "Symbol": "000001", "Ret": 0.02},
            {"TradingDate": "2025-12-31", "Symbol": "000002", "Ret": 0.03},
            {"TradingDate": "2026-01-02", "Symbol": "000003", "Ret": 0.04},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)

    forecast_dir = source / "teacher" / "financial_supplement" / "forecast_vs_report"
    forecast_dir.mkdir(parents=True)
    (forecast_dir / "BF_FORECAST[DES][csv].txt").write_text(
        "Stkcd [证券代码] - \nPubliDate [预告日期] - ",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"Stkcd": "000001", "PubliDate": "2022-12-31", "Value": 1},
            {"Stkcd": "000001", "PubliDate": "2023-01-01", "Value": 2},
            {"Stkcd": "000002", "PubliDate": "2025-12-31", "Value": 3},
            {"Stkcd": "000003", "PubliDate": "2026-01-01", "Value": 4},
        ]
    ).to_csv(forecast_dir / "BF_FORECAST.csv", index=False)

    static_dir = source / "distribute" / "basic"
    static_dir.mkdir(parents=True)
    pd.DataFrame([{"Code": "A", "Name": "Alpha"}]).to_csv(static_dir / "lookup.csv", index=False)
    (static_dir / "manual.pdf").write_bytes(b"%PDF fixture")

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2023-01-01", end="2025-12-31")

    returns = pd.read_parquet(output / "distribute" / "stock" / "daily_returns.parquet")
    assert returns["TradingDate"].tolist() == ["2023-01-03", "2025-12-31"]

    forecast = pd.read_csv(
        output / "teacher" / "financial_supplement" / "forecast_vs_report" / "BF_FORECAST.csv",
        dtype={"Stkcd": str},
    )
    assert forecast["PubliDate"].tolist() == ["2023-01-01", "2025-12-31"]
    assert forecast["Stkcd"].tolist() == ["000001", "000002"]

    assert (output / "distribute" / "basic" / "lookup.csv").exists()
    assert (output / "distribute" / "basic" / "manual.pdf").exists()

    catalog = DataCatalog.load(output / "data_catalog.json")
    assert catalog.metadata["release_start"] == "2023-01-01"
    assert catalog.metadata["release_end"] == "2025-12-31"
    assert catalog.resolve("BF_FORECAST").row_count == 2
    assert catalog.resolve("stock.daily_returns").source_row_count == 4


def test_release_builder_learning_default_keeps_rows_before_2023(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    table_dir = source / "teacher" / "factor_benchmark" / "momentum_factor"
    table_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingMonth": "2022-12", "MarkettypeID": "P9701", "MomRe1": 0.1},
            {"TradingMonth": "2023-01", "MarkettypeID": "P9701", "MomRe1": 0.2},
        ]
    ).to_csv(table_dir / "STK_MKT_MOMENTUM.csv", index=False)

    output = tmp_path / "data_releases" / "learning"
    build_release(source, output, end="2022-12-31")

    momentum = pd.read_csv(
        output / "teacher" / "factor_benchmark" / "momentum_factor" / "STK_MKT_MOMENTUM.csv"
    )
    assert momentum["TradingMonth"].tolist() == ["2022-12"]


def test_release_builder_rejects_an_output_that_contains_the_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    source.mkdir()
    source_file = source / "fixture.csv"
    source_file.write_text("date,value\n2022-01-01,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cannot contain each other"):
        build_release(source, tmp_path)

    assert source_file.exists()


def test_multi_release_builder_rejects_nested_outputs_before_writing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    source.mkdir()
    output = tmp_path / "data_releases" / "learning"
    nested_output = output / "learning_1"
    nested_output.mkdir(parents=True)
    sentinel = nested_output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="output roots cannot contain each other"):
        releases_module._build_release_targets(
            source,
            DataCatalog(root=source.as_posix(), datasets=[]),
            [
                releases_module._ReleaseTarget(
                    name="learning",
                    output_root=output,
                    start_date=None,
                    end_date=None,
                    metadata={},
                ),
                releases_module._ReleaseTarget(
                    name="learning_1",
                    output_root=nested_output,
                    start_date=None,
                    end_date=None,
                    metadata={},
                ),
            ],
        )

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_release_builder_allows_configured_hidden_test_window(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    table_dir = source / "distribute" / "stock"
    table_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2023-12-29", "Symbol": "000000", "Ret": 0.00},
            {"TradingDate": "2024-01-03", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2024-12-31", "Symbol": "000002", "Ret": 0.02},
            {"TradingDate": "2025-01-02", "Symbol": "000003", "Ret": 0.03},
        ]
    ).to_csv(table_dir / "daily_returns.csv", index=False)

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2024-01-01", end="2024-12-31")

    returns = pd.read_csv(output / "distribute" / "stock" / "daily_returns.csv")
    assert returns["TradingDate"].tolist() == ["2024-01-03", "2024-12-31"]


def test_release_builder_carries_adjustment_factor_baseline_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    factor_dir = source / "teacher" / "factor_benchmark"
    factor_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "tradingdate": "2022-12-30",
                "symbol": "000001",
                "cumulatefwardfactor": 2.0,
            },
            {
                "tradingdate": "2023-01-10",
                "symbol": "000001",
                "cumulatefwardfactor": 2.5,
            },
            {
                "tradingdate": "2022-12-29",
                "symbol": "000002",
                "cumulatefwardfactor": 3.0,
            },
            {
                "tradingdate": "2026-01-05",
                "symbol": "000003",
                "cumulatefwardfactor": 4.0,
            },
        ]
    ).to_csv(factor_dir / "adj_factor.csv", index=False)

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2023-01-01", end="2025-12-31")

    factors = pd.read_csv(
        output / "teacher" / "factor_benchmark" / "adj_factor.csv",
        dtype={"symbol": str},
    )

    assert factors[["tradingdate", "symbol", "cumulatefwardfactor"]].to_dict("records") == [
        {
            "tradingdate": "2022-12-30",
            "symbol": "000001",
            "cumulatefwardfactor": 2.0,
        },
        {
            "tradingdate": "2022-12-29",
            "symbol": "000002",
            "cumulatefwardfactor": 3.0,
        },
        {
            "tradingdate": "2023-01-10",
            "symbol": "000001",
            "cumulatefwardfactor": 2.5,
        },
    ]


def test_release_builder_carries_industry_classification_baseline_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    industry_dir = source / "teacher" / "basic"
    industry_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "ImplementDate": "2009-12-31",
                "Symbol": "000001",
                "IndustryName": "Finance",
            },
            {
                "ImplementDate": "2012-01-03",
                "Symbol": "000001",
                "IndustryName": "Banking",
            },
            {
                "ImplementDate": "2008-01-01",
                "Symbol": "000002",
                "IndustryName": "Industry",
            },
            {
                "ImplementDate": "2016-01-04",
                "Symbol": "000003",
                "IndustryName": "Technology",
            },
        ]
    ).to_csv(industry_dir / "STK_INDUSTRYCLASS.csv", index=False)

    output = tmp_path / "data_releases" / "learning_1"
    build_release(source, output, start="2010-01-01", end="2015-12-31")

    industry = pd.read_csv(
        output / "teacher" / "basic" / "STK_INDUSTRYCLASS.csv",
        dtype={"Symbol": str},
    )
    assert industry[["ImplementDate", "Symbol", "IndustryName"]].to_dict("records") == [
        {
            "ImplementDate": "2009-12-31",
            "Symbol": "000001",
            "IndustryName": "Finance",
        },
        {
            "ImplementDate": "2008-01-01",
            "Symbol": "000002",
            "IndustryName": "Industry",
        },
        {
            "ImplementDate": "2012-01-03",
            "Symbol": "000001",
            "IndustryName": "Banking",
        },
    ]


def test_release_builder_replaces_stale_outputs_and_does_not_copy_zip_payloads(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    table_dir = source / "teacher" / "financial_supplement" / "forecast_vs_report"
    table_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"Stkcd": "000001", "PubliDate": "2023-01-01", "Value": 1},
            {"Stkcd": "000002", "PubliDate": "2026-01-01", "Value": 2},
        ]
    ).to_csv(table_dir / "BF_FORECAST.csv", index=False)
    (table_dir / "BF_FORECAST[DES][csv].txt").write_text(
        "Stkcd [证券代码] - \nPubliDate [发布日期] - ",
        encoding="utf-8",
    )
    (table_dir / "raw_vendor_payload.zip").write_bytes(b"unfiltered payload")

    output = tmp_path / "data_releases" / "hidden_test"
    stale_dir = output / "teacher" / "old"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.csv").write_text("old data", encoding="utf-8")

    build_release(source, output, start="2023-01-01", end="2025-12-31")

    assert not (stale_dir / "stale.csv").exists()
    assert not (
        output
        / "teacher"
        / "financial_supplement"
        / "forecast_vs_report"
        / "raw_vendor_payload.zip"
    ).exists()
    assert (
        output
        / "teacher"
        / "financial_supplement"
        / "forecast_vs_report"
        / "BF_FORECAST[DES][csv].txt"
    ).exists()


def test_release_builder_repairs_malformed_csmar_text_fields(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    forecast_dir = source / "teacher" / "financial_supplement" / "forecast_vs_report"
    forecast_dir.mkdir(parents=True)
    (forecast_dir / "BF_FORECAST[DES][csv].txt").write_text(
        "Stkcd [证券代码] - \nPubliDate [预告日期] - \nReaFinResuVari [业绩变动原因] - ",
        encoding="utf-8",
    )
    (forecast_dir / "BF_FORECAST.csv").write_text(
        "\n".join(
            [
                '"Stkcd","PubliDate","ReaFinResuVari","Value"',
                '"000001","2023-01-01","normal reason","1"',
                '"000002","2023-01-02","reason with a bad "quote", and comma","2"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2023-01-01", end="2025-12-31")

    forecast = pd.read_csv(
        output / "teacher" / "financial_supplement" / "forecast_vs_report" / "BF_FORECAST.csv",
        dtype={"Stkcd": str},
    )
    assert forecast["Stkcd"].tolist() == ["000001", "000002"]
    assert forecast["ReaFinResuVari"].tolist() == [
        "normal reason",
        'reason with a bad quote", and comma',
    ]


def test_release_builder_filters_datago_csvs_and_copies_field_dictionary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "new_data"
    table_dir = (
        source
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
    )
    table_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "stock_id": "000001.SZ",
                "pub_date": "2022-12-30",
                "index_all": 100,
            },
            {
                "stock_id": "000002.SZ",
                "pub_date": "2023-01-03",
                "index_all": 200,
            },
            {
                "stock_id": "000003.SZ",
                "pub_date": "2025-12-31",
                "index_all": 300,
            },
            {
                "stock_id": "000004.SZ",
                "pub_date": "2026-01-02",
                "index_all": 400,
            },
        ]
    ).to_csv(table_dir / "上市公司网络搜索分析数据表.csv", index=False)
    write_xlsx_field_dictionary(
        table_dir / "《上市公司网络搜索分析数据库》字段说明.xlsx",
        "上市公司网络搜索分析数据表",
        [
            ["字段", "数据类型", "字段说明"],
            ["stock_id", "char", "包含市场信息的股票代码"],
            ["pub_date", "date", "统计日期"],
            ["index_all", "int", "全部设备搜索流量指数"],
        ],
    )
    (table_dir / "版权说明.pdf").write_bytes(b"%PDF fixture")
    (table_dir.parent / "上市公司网络搜索分析数据表_fullpacked_data.zip").write_bytes(
        b"raw vendor payload"
    )
    monkeypatch.setattr("quantfish.data.releases.CSV_RELEASE_CHUNK_SIZE", 2)

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2023-01-01", end="2025-12-31")

    released = pd.read_csv(
        output
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
        / "上市公司网络搜索分析数据表.csv"
    )
    assert released["stock_id"].tolist() == ["000002.SZ", "000003.SZ"]
    assert released["index_all"].tolist() == [200, 300]
    assert (
        output
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
        / "《上市公司网络搜索分析数据库》字段说明.xlsx"
    ).exists()
    assert (
        output
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
        / "版权说明.pdf"
    ).exists()
    assert not (
        output
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data.zip"
    ).exists()

    catalog = DataCatalog.load(output / "data_catalog.json")
    spec = catalog.resolve("上市公司网络搜索分析数据表")
    assert spec.primary_asof_column == "pub_date"
    assert spec.symbol_column == "stock_id"
    assert spec.row_count == 2
    assert spec.source_row_count == 4


def test_release_builder_streamed_csv_empty_output_avoids_header_reread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "new_data"
    table_dir = (
        source
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
    )
    table_dir.mkdir(parents=True)
    source_csv = table_dir / "上市公司网络搜索分析数据表.csv"
    pd.DataFrame(
        [
            {
                "stock_id": "000001.SZ",
                "pub_date": "2022-12-30",
                "index_all": 100,
            },
            {
                "stock_id": "000002.SZ",
                "pub_date": "2022-12-31",
                "index_all": 200,
            },
        ]
    ).to_csv(source_csv, index=False)
    write_xlsx_field_dictionary(
        table_dir / "《上市公司网络搜索分析数据库》字段说明.xlsx",
        "上市公司网络搜索分析数据表",
        [
            ["字段", "数据类型", "字段说明"],
            ["stock_id", "char", "包含市场信息的股票代码"],
            ["pub_date", "date", "统计日期"],
            ["index_all", "int", "全部设备搜索流量指数"],
        ],
    )
    catalog = releases_module.scan_catalog(source)
    read_calls = 0
    original_read_csv = releases_module.pd.read_csv

    def recording_read_csv(path: object, *args: object, **kwargs: object) -> pd.DataFrame:
        nonlocal read_calls
        if Path(path) == source_csv:
            read_calls += 1
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr("quantfish.data.releases.CSV_RELEASE_CHUNK_SIZE", 1)
    monkeypatch.setattr(releases_module.pd, "read_csv", recording_read_csv)

    output = tmp_path / "data_releases" / "hidden_test"
    releases_module._build_release_targets(
        source,
        catalog,
        [
            releases_module._ReleaseTarget(
                name=None,
                output_root=output,
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2025-12-31"),
                metadata={},
            )
        ],
    )

    released = pd.read_csv(
        output
        / "teacher"
        / "behavioral_finance"
        / "datago"
        / "上市公司网络搜索分析数据表_fullpacked_data"
        / "上市公司网络搜索分析数据表.csv"
    )
    assert read_calls == 1
    assert released.empty
    assert released.columns.tolist() == ["stock_id", "pub_date", "index_all"]


def test_release_builder_repairs_malformed_index_metadata_text_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    index_dir = source / "teacher" / "index_metadata" / "index_info"
    index_dir.mkdir(parents=True)
    (index_dir / "IDX_Idxinfo[DES][csv].txt").write_text(
        "\n".join(
            [
                "Indexcd [交易所指数代码] - ",
                "Idxinfo04 [样本范围] - 以实际披露录入",
                "Idxinfo10 [计算公式] - 以实际披露为准",
            ]
        ),
        encoding="utf-8",
    )
    (index_dir / "IDX_Idxinfo.csv").write_text(
        "\n".join(
            [
                '"Indexcd","Idxinfo01","Idxinfo11","Idxinfo02","Idxinfo03","Idxinfo04","Idxinfo05","Idxinfo06","Idxinfo07","Idxinfo08","Idxinfo09","Idxinfo10"',
                '"399296","指数A","2019-01-23","2012-12-31","1000.000","sample scope","1","2","1","2","2","formula with a bad "quote", and comma"',
                '"483087","指数B","2018-03-08","2011-12-30","1000.000","scope with a bad "quote", comma one, comma two","1","2","1","3","9","formula"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "data_releases" / "hidden_test"
    build_release(source, output, start="2023-01-01", end="2025-12-31")

    metadata = pd.read_csv(output / "teacher" / "index_metadata" / "index_info" / "IDX_Idxinfo.csv")
    assert metadata["Idxinfo04"].tolist() == [
        "sample scope",
        'scope with a bad quote", comma one, comma two',
    ]
    assert metadata["Idxinfo10"].tolist() == [
        'formula with a bad quote", and comma',
        "formula",
    ]


def test_config_release_builder_builds_all_configured_releases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2014-12-31", "Symbol": "000000", "Ret": 0.00},
            {"TradingDate": "2015-06-01", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2019-12-31", "Symbol": "000002", "Ret": 0.02},
            {"TradingDate": "2020-06-01", "Symbol": "000003", "Ret": 0.03},
            {"TradingDate": "2022-12-30", "Symbol": "000004", "Ret": 0.04},
            {"TradingDate": "2023-01-03", "Symbol": "000005", "Ret": 0.05},
            {"TradingDate": "2025-12-31", "Symbol": "000006", "Ret": 0.06},
            {"TradingDate": "2026-01-02", "Symbol": "000007", "Ret": 0.07},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)

    release_root = tmp_path / "data_releases"
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_start=date(2010, 1, 2),
            learning_end=date(2022, 12, 31),
        ),
        backtest=PlatformConfig.default().backtest,
    )
    catalogs = build_releases_from_config(config)

    assert sorted(catalogs) == [
        "hidden_test",
        "learning",
        "learning_1",
        "learning_2",
        "learning_3",
    ]

    learning = pd.read_parquet(
        release_root / "learning" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning["TradingDate"].tolist() == [
        "2014-12-31",
        "2015-06-01",
        "2019-12-31",
        "2020-06-01",
        "2022-12-30",
    ]

    learning_1 = pd.read_parquet(
        release_root / "learning_1" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning_1["TradingDate"].tolist() == ["2014-12-31", "2015-06-01"]

    learning_2 = pd.read_parquet(
        release_root / "learning_2" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning_2["TradingDate"].tolist() == [
        "2015-06-01",
        "2019-12-31",
        "2020-06-01",
    ]

    learning_3 = pd.read_parquet(
        release_root / "learning_3" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning_3["TradingDate"].tolist() == ["2020-06-01", "2022-12-30"]

    hidden = pd.read_parquet(
        release_root / "hidden_test" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert hidden["TradingDate"].tolist() == ["2023-01-03", "2025-12-31"]

    hidden_catalog = DataCatalog.load(release_root / "hidden_test" / "data_catalog.json")
    assert hidden_catalog.metadata["release_name"] == "hidden_test"
    assert hidden_catalog.metadata["price_policy"] == "front_adjusted"
    assert hidden_catalog.metadata["configured_hidden_start"] == "2023-01-01"
    assert hidden_catalog.metadata["configured_hidden_end"] == "2025-12-31"


def test_config_release_builder_scans_source_catalog_once_for_all_releases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2022-06-01", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2023-06-01", "Symbol": "000002", "Ret": 0.02},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)

    release_root = tmp_path / "data_releases"
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )
    scan_calls: list[Path] = []
    original_scan_catalog = releases_module.scan_catalog

    def recording_scan_catalog(root: Path | str) -> DataCatalog:
        scan_calls.append(Path(root))
        return original_scan_catalog(root)

    monkeypatch.setattr(releases_module, "scan_catalog", recording_scan_catalog)

    build_releases_from_config(config)

    assert scan_calls == [source]


def test_config_release_builder_can_build_only_selected_learning_windows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2019-12-31", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2021-06-01", "Symbol": "000002", "Ret": 0.02},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    release_root = tmp_path / "data_releases"
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )

    progress = []
    catalogs = build_releases_from_config(
        config,
        release_names=["learning_2", "learning_3"],
        progress_callback=progress.append,
    )

    assert list(catalogs) == ["learning_2", "learning_3"]
    assert not (release_root / "learning").exists()
    assert not (release_root / "hidden_test").exists()
    assert pd.read_parquet(
        release_root / "learning_2" / "distribute" / "stock" / "daily_returns.parquet"
    )["Symbol"].tolist() == ["000001"]
    assert pd.read_parquet(
        release_root / "learning_3" / "distribute" / "stock" / "daily_returns.parquet"
    )["Symbol"].tolist() == ["000002"]
    assert [event.phase for event in progress] == [
        "scanning",
        "preparing",
        "building",
        "building",
        "cataloging",
        "publishing",
        "completed",
    ]
    assert progress[3].completed_datasets == 1
    assert progress[3].total_datasets == 1
    assert progress[3].current_dataset == "stock.daily_returns"
    assert progress[-1].percent == 100


def test_release_publication_restores_previous_output_when_swap_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "learning_1"
    output_root.mkdir()
    sentinel = output_root / "sentinel.txt"
    sentinel.write_text("previous release", encoding="utf-8")
    temp_output_root = tmp_path / ".learning_1.build.tmp"
    temp_output_root.mkdir()
    (temp_output_root / "data_catalog.json").write_text("{}", encoding="utf-8")
    original_rename = Path.rename

    def fail_new_release_rename(self: Path, target: Path) -> Path:
        if self == temp_output_root:
            raise OSError("simulated publication failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_new_release_rename)

    with pytest.raises(OSError, match="simulated publication failure"):
        releases_module._replace_output(temp_output_root, output_root)

    assert sentinel.read_text(encoding="utf-8") == "previous release"
    assert temp_output_root.exists()
    assert not temp_output_root.with_name(f"{temp_output_root.name}.previous").exists()


def test_release_publication_keeps_new_output_when_backup_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    output_root = tmp_path / "learning_1"
    output_root.mkdir()
    (output_root / "sentinel.txt").write_text("previous", encoding="utf-8")
    temp_output_root = tmp_path / ".learning_1.build.tmp"
    temp_output_root.mkdir()
    (temp_output_root / "data_catalog.json").write_text("new", encoding="utf-8")

    def fail_backup_cleanup(_path: Path) -> None:
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(shutil, "rmtree", fail_backup_cleanup)

    releases_module._replace_output(temp_output_root, output_root)

    assert (output_root / "data_catalog.json").read_text(encoding="utf-8") == "new"
    backup = temp_output_root.with_name(f"{temp_output_root.name}.previous")
    assert (backup / "sentinel.txt").read_text(encoding="utf-8") == "previous"
    assert "release published, but previous output could not be removed" in caplog.text


def test_config_release_builder_rejects_empty_source_without_replacing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty_source"
    source.mkdir()
    release_root = tmp_path / "data_releases"
    learning_1_root = release_root / "learning_1"
    learning_1_root.mkdir(parents=True)
    sentinel = learning_1_root / "sentinel.txt"
    sentinel.write_text("previous release", encoding="utf-8")
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_1_output_root=learning_1_root.as_posix(),
            learning_2_output_root=(release_root / "learning_2").as_posix(),
            learning_3_output_root=(release_root / "learning_3").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )

    with pytest.raises(ValueError, match="no supported datasets found"):
        build_releases_from_config(config, release_names=["learning_1"])

    assert sentinel.read_text(encoding="utf-8") == "previous release"
    assert not list(release_root.glob(".learning_1.*.tmp"))


def test_config_release_builder_rejects_incomplete_scoring_source_without_replacing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incomplete_source"
    source.mkdir()
    (source / "irrelevant.csv").write_text(
        "date,value\n2020-01-01,1\n",
        encoding="utf-8",
    )
    release_root = tmp_path / "data_releases"
    learning_1_root = release_root / "learning_1"
    learning_1_root.mkdir(parents=True)
    sentinel = learning_1_root / "sentinel.txt"
    sentinel.write_text("previous release", encoding="utf-8")
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_1_output_root=learning_1_root.as_posix(),
            learning_2_output_root=(release_root / "learning_2").as_posix(),
            learning_3_output_root=(release_root / "learning_3").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )

    with pytest.raises(
        ValueError,
        match=re.escape("stock.daily_returns, factor_benchmark.adj_factor"),
    ):
        build_releases_from_config(
            config,
            release_names=["learning_1"],
            required_dataset_ids=(
                "stock.daily_returns",
                "factor_benchmark.adj_factor",
            ),
        )

    assert sentinel.read_text(encoding="utf-8") == "previous release"
    assert not list(release_root.glob(".learning_1.*.tmp"))


def test_config_release_builder_rejects_company_info_without_listing_columns(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid_company_info_source"
    basic_dir = source / "distribute" / "basic"
    basic_dir.mkdir(parents=True)
    pd.DataFrame([{"issuer": "Example", "founded": "2000-01-01"}]).to_csv(
        basic_dir / "company_info.csv",
        index=False,
    )
    release_root = tmp_path / "data_releases"
    learning_1_root = release_root / "learning_1"
    learning_1_root.mkdir(parents=True)
    sentinel = learning_1_root / "sentinel.txt"
    sentinel.write_text("previous release", encoding="utf-8")
    default = PlatformConfig.default()
    config = replace(
        default,
        data_releases=replace(
            default.data_releases,
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_1_output_root=learning_1_root.as_posix(),
            learning_2_output_root=(release_root / "learning_2").as_posix(),
            learning_3_output_root=(release_root / "learning_3").as_posix(),
        ),
    )

    with pytest.raises(
        ValueError,
        match=r"basic\.company_info.*missing required columns.*symbol.*listdt",
    ):
        build_releases_from_config(
            config,
            release_names=["learning_1"],
            required_dataset_ids=("basic.company_info",),
        )

    assert sentinel.read_text(encoding="utf-8") == "previous release"
    assert not list(release_root.glob(".learning_1.*.tmp"))


def test_config_release_builder_rejects_empty_required_window_without_replacing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "future_source"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2020-01-02",
                "Symbol": "000001",
                "Clsprc": 10.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1000.0,
            }
        ]
    ).to_csv(stock_dir / "daily_returns.csv", index=False)
    factor_dir = source / "teacher" / "factor_benchmark"
    factor_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "TradingDate": "2020-01-02",
                "Symbol": "000001",
                "CumulateFwardFactor": 1.0,
            }
        ]
    ).to_csv(factor_dir / "adj_factor.csv", index=False)
    release_root = tmp_path / "data_releases"
    learning_1_root = release_root / "learning_1"
    learning_1_root.mkdir(parents=True)
    sentinel = learning_1_root / "sentinel.txt"
    sentinel.write_text("previous release", encoding="utf-8")
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_1_output_root=learning_1_root.as_posix(),
            learning_2_output_root=(release_root / "learning_2").as_posix(),
            learning_3_output_root=(release_root / "learning_3").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )

    with pytest.raises(
        ValueError,
        match=r"learning_1 release has no usable rows.*stock\.daily_returns",
    ):
        build_releases_from_config(
            config,
            release_names=["learning_1"],
            required_dataset_ids=(
                "stock.daily_returns",
                "factor_benchmark.adj_factor",
            ),
        )

    assert sentinel.read_text(encoding="utf-8") == "previous release"
    assert not list(release_root.glob(".learning_1.*.tmp"))

    catalogs = build_releases_from_config(
        config,
        release_names=["learning_2"],
        required_dataset_ids=(
            "stock.daily_returns",
            "factor_benchmark.adj_factor",
        ),
    )
    generation = catalogs["learning_2"].metadata["release_generation"]
    assert isinstance(generation, str)
    assert len(generation) == 32


def test_config_release_builder_streams_parquet_without_full_dataframe_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2021-12-31", "Symbol": "000000", "Ret": 0.00},
            {"TradingDate": "2022-01-03", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2022-12-30", "Symbol": "000002", "Ret": 0.02},
            {"TradingDate": "2023-01-03", "Symbol": "000003", "Ret": 0.03},
            {"TradingDate": "2025-12-31", "Symbol": "000004", "Ret": 0.04},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)

    release_root = tmp_path / "data_releases"
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )
    original_read_dataset = releases_module._read_dataset

    def fail_on_full_parquet_read(
        path: Path,
        spec: releases_module.DatasetSpec,
    ) -> pd.DataFrame:
        if spec.format == "parquet":
            raise AssertionError(f"full parquet read was used for {path}")
        return original_read_dataset(path, spec)

    monkeypatch.setattr(releases_module, "_read_dataset", fail_on_full_parquet_read)

    build_releases_from_config(config)

    learning = pd.read_parquet(
        release_root / "learning" / "distribute" / "stock" / "daily_returns.parquet"
    )
    hidden = pd.read_parquet(
        release_root / "hidden_test" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning["Symbol"].tolist() == ["000001", "000002"]
    assert hidden["Symbol"].tolist() == ["000003", "000004"]


def test_release_chunk_sizes_can_be_configured_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFISH_RELEASE_CSV_CHUNK_SIZE", "7")
    monkeypatch.setenv("QUANTFISH_RELEASE_PARQUET_BATCH_ROWS", "11")

    assert releases_module._csv_release_chunk_size() == 7
    assert releases_module._parquet_release_batch_rows() == 11


def test_config_release_builder_keeps_hidden_hs300_rows_when_index_daily_exists(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    market_dir = source / "distribute" / "market"
    market_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "indexcd": "000300",
                "idxtrd01": "2022-12-30",
                "idxtrd02": 3900.0,
                "idxtrd03": 3910.0,
                "idxtrd04": 3890.0,
                "idxtrd05": 3900.0,
                "idxtrd06": 1.0,
                "idxtrd07": 2.0,
                "idxtrd08": 0.1,
                "idxtrd09": "沪深300",
            },
            {
                "indexcd": "000300",
                "idxtrd01": "2023-01-03",
                "idxtrd02": 3864.836,
                "idxtrd03": 3893.99,
                "idxtrd04": 3831.245,
                "idxtrd05": 3887.899,
                "idxtrd06": 1.0,
                "idxtrd07": 2.0,
                "idxtrd08": 0.4201,
                "idxtrd09": "沪深300",
            },
            {
                "indexcd": "000001",
                "idxtrd01": "2023-01-03",
                "idxtrd02": 3100.0,
                "idxtrd03": 3120.0,
                "idxtrd04": 3090.0,
                "idxtrd05": 3110.0,
                "idxtrd06": 1.0,
                "idxtrd07": 2.0,
                "idxtrd08": 0.2,
                "idxtrd09": "上证指数",
            },
        ]
    ).to_csv(market_dir / "index_daily.csv", index=False)

    release_root = tmp_path / "data_releases"
    build_releases_from_config(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=DataReleasesConfig(
                raw_data_root=source.as_posix(),
                learning_output_root=(release_root / "learning").as_posix(),
                hidden_output_root=(release_root / "hidden_test").as_posix(),
            ),
            backtest=PlatformConfig.default().backtest,
        )
    )

    hidden_index = pd.read_csv(
        release_root / "hidden_test" / "distribute" / "market" / "index_daily.csv",
        dtype={"indexcd": str},
    )

    assert hidden_index.loc[hidden_index["indexcd"] == "000300", "idxtrd01"].tolist() == [
        "2023-01-03"
    ]


def test_config_release_builder_fails_when_hidden_hs300_rows_are_missing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "new_data"
    market_dir = source / "distribute" / "market"
    market_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "indexcd": "000300",
                "idxtrd01": "2022-12-30",
                "idxtrd02": 3900.0,
                "idxtrd03": 3910.0,
                "idxtrd04": 3890.0,
                "idxtrd05": 3900.0,
                "idxtrd06": 1.0,
                "idxtrd07": 2.0,
                "idxtrd08": 0.1,
                "idxtrd09": "沪深300",
            }
        ]
    ).to_csv(market_dir / "index_daily.csv", index=False)

    release_root = tmp_path / "data_releases"
    config = PlatformConfig(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=source.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
        ),
        backtest=PlatformConfig.default().backtest,
    )

    learning_catalogs = build_releases_from_config(
        config,
        release_names=["learning_1"],
    )
    assert list(learning_catalogs) == ["learning_1"]

    with pytest.raises(ValueError, match="hidden_test release has no HS300"):
        build_releases_from_config(config, release_names=["hidden_test"])


def test_release_cli_build_from_config_uses_yaml_config(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    stock_dir = source / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2019-12-30", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2023-01-03", "Symbol": "000002", "Ret": 0.02},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=DataReleasesConfig(
                raw_data_root=source.as_posix(),
                learning_output_root=(tmp_path / "data_releases" / "learning").as_posix(),
                hidden_output_root=(tmp_path / "data_releases" / "hidden_test").as_posix(),
            ),
            backtest=PlatformConfig.default().backtest,
        )
    )

    exit_code = main(
        [
            "build-from-config",
            "--config",
            config_path.as_posix(),
            "--release",
            "learning_2",
        ]
    )

    assert exit_code == 0
    learning_2 = pd.read_parquet(
        tmp_path / "data_releases" / "learning_2" / "distribute" / "stock" / "daily_returns.parquet"
    )
    assert learning_2["Symbol"].tolist() == ["000001"]
    assert not (tmp_path / "data_releases" / "learning").exists()
    assert not (tmp_path / "data_releases" / "hidden_test").exists()
