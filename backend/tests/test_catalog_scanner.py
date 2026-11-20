from pathlib import Path

import pandas as pd

from quantfish.data.catalog import DataCatalog
from quantfish.data.scanner import scan_catalog
from xlsx_fixtures import write_xlsx_field_dictionary


def test_scanner_detects_csmar_aliases_descriptions_and_dates(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    table_dir = source / "teacher" / "financial_supplement" / "forecast_vs_report"
    table_dir.mkdir(parents=True)
    (table_dir / ".DS_Store").write_text("ignored")
    (table_dir / "BF_FORECAST[DES][csv].txt").write_text(
        "\n".join(
            [
                "Stkcd [证券代码] - ",
                "EndDate [截止日期] - YYYY-12-31、YYYY-03-31、YYYY-09-30、YYYY-06-30。",
                "Anondt [定期报告发布日期] - ",
                "PubliDate [预告日期] - ",
            ]
        ),
        encoding="utf-8",
    )
    (table_dir / "版权声明.pdf").write_bytes(b"%PDF fixture")
    pd.DataFrame(
        [
            {
                "Stkcd": "000001",
                "EndDate": "2022-12-31",
                "Anondt": "2023-03-31",
                "PubliDate": "2023-01-10",
                "Value": 1.5,
            }
        ]
    ).to_csv(table_dir / "BF_FORECAST.csv", index=False)

    parquet_dir = source / "distribute" / "stock"
    parquet_dir.mkdir(parents=True)
    pd.DataFrame([{"TradingDate": "2023-01-03", "Symbol": "000001", "Ret": 0.02}]).to_parquet(
        parquet_dir / "daily_returns.parquet", index=False
    )

    catalog = scan_catalog(source)

    forecast = catalog.resolve("BF_FORECAST")
    assert forecast.dataset_id == "financial_supplement.forecast_vs_report.BF_FORECAST"
    assert forecast.csmar_table_code == "BF_FORECAST"
    assert "BF_FORECAST" in forecast.aliases
    assert forecast.symbol_column == "Stkcd"
    assert forecast.date_columns == ["EndDate", "Anondt", "PubliDate"]
    assert forecast.primary_asof_column == "PubliDate"
    assert forecast.column_descriptions["Stkcd"]["label_zh"] == "证券代码"
    assert "BF_FORECAST[DES][csv].txt" in forecast.doc_paths
    assert "版权声明.pdf" in forecast.doc_paths

    returns = catalog.resolve("stock.daily_returns")
    assert returns.format == "parquet"
    assert returns.primary_asof_column == "TradingDate"
    assert returns.symbol_column == "Symbol"

    reloaded = DataCatalog.from_json(catalog.to_json())
    assert reloaded.resolve("BF_FORECAST").primary_asof_column == "PubliDate"


def test_scanner_marks_tables_without_date_columns_as_static(tmp_path: Path) -> None:
    source = tmp_path / "new_data"
    table_dir = source / "distribute" / "basic"
    table_dir.mkdir(parents=True)
    pd.DataFrame([{"Code": "A", "Name": "Alpha"}]).to_csv(table_dir / "lookup.csv", index=False)

    catalog = scan_catalog(source)

    spec = catalog.resolve("basic.lookup")
    assert spec.is_static is True
    assert spec.primary_asof_column is None


def test_scanner_detects_datago_dates_symbols_aliases_and_xlsx_descriptions(
    tmp_path: Path,
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
                "figi": "BBG000BZDPV5",
                "pub_date": "2022-12-30",
                "index_all": 100,
            }
        ]
    ).to_csv(table_dir / "上市公司网络搜索分析数据表.csv", index=False)
    write_xlsx_field_dictionary(
        table_dir / "《上市公司网络搜索分析数据库》字段说明.xlsx",
        "上市公司网络搜索分析数据表",
        [
            ["字段", "数据类型", "字段说明"],
            ["stock_id", "char", "包含市场信息的股票代码"],
            ["pub_date", "date", "统计日期，可在次日之后获取"],
            ["index_all", "int", "全部设备搜索流量指数"],
        ],
    )
    (table_dir / "版权说明.pdf").write_bytes(b"%PDF fixture")

    catalog = scan_catalog(source)

    spec = catalog.resolve("上市公司网络搜索分析数据表")
    assert (
        spec.dataset_id
        == "behavioral_finance.datago.上市公司网络搜索分析数据表_fullpacked_data.上市公司网络搜索分析数据表"
    )
    assert spec.relative_path.endswith("上市公司网络搜索分析数据表.csv")
    assert spec.primary_asof_column == "pub_date"
    assert spec.date_columns == ["pub_date"]
    assert spec.symbol_column == "stock_id"
    assert spec.is_static is False
    assert "上市公司网络搜索分析数据表" in spec.aliases
    assert "《上市公司网络搜索分析数据库》字段说明.xlsx" in spec.doc_paths
    assert "版权说明.pdf" in spec.doc_paths
    assert spec.column_descriptions["pub_date"]["data_type"] == "date"
    assert "统计日期" in spec.column_descriptions["pub_date"]["description"]


def test_scanner_detects_datago_title_case_pub_date_and_stock_id(
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
                "Reads_Announce_Sum": 10,
            }
        ]
    ).to_csv(table_dir / "股吧量化舆情表(交易时段分组).csv", index=False)

    catalog = scan_catalog(source)

    spec = catalog.resolve("股吧量化舆情表(交易时段分组)")
    assert spec.primary_asof_column == "Pub_Date"
    assert spec.date_columns == ["Pub_Date"]
    assert spec.symbol_column == "Stock_Id"
    assert spec.is_static is False
