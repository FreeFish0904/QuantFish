import pandas as pd
import pytest

import quantfish.backtest.industry_neutralization as neutralization_module
from quantfish.backtest.industry_neutralization import (
    IndustryNeutralizationSummary,
    neutralize_scores_by_industry,
)


def test_neutralize_scores_by_industry_subtracts_date_industry_mean() -> None:
    scores = pd.DataFrame(
        [
            {"date": "2023-01-03", "code": "1", "score": 3.0},
            {"date": "2023-01-03", "code": "000002", "score": 1.0},
            {"date": "2023-01-03", "code": "300001", "score": 10.0},
            {"date": "2023-01-03", "code": "600001", "score": None},
        ]
    )
    industries = pd.DataFrame(
        [
            {"ImplementDate": "2022-12-31", "Symbol": "000001", "IndustryName": "银行"},
            {"ImplementDate": "2022-12-31", "Symbol": "000002", "IndustryName": "银行"},
            {"ImplementDate": "2022-12-31", "Symbol": "300001", "IndustryName": "软件"},
            {"ImplementDate": "2022-12-31", "Symbol": "600001", "IndustryName": "证券"},
        ]
    )

    neutralized, summary = neutralize_scores_by_industry(scores, industries)

    assert neutralized[["date", "code"]].to_dict("records") == [
        {"date": pd.Timestamp("2023-01-03"), "code": "000001"},
        {"date": pd.Timestamp("2023-01-03"), "code": "000002"},
        {"date": pd.Timestamp("2023-01-03"), "code": "300001"},
        {"date": pd.Timestamp("2023-01-03"), "code": "600001"},
    ]
    assert neutralized["score"].tolist()[:3] == pytest.approx([1.0, -1.0, 0.0])
    assert pd.isna(neutralized.loc[3, "score"])
    assert summary == IndustryNeutralizationSummary(
        enabled=True,
        dataset="basic.STK_INDUSTRYCLASS",
        industry_column="IndustryName",
        signal_rows=4,
        neutralized_rows=3,
        missing_industry_rows=0,
        industry_count=3,
    )


def test_neutralize_scores_by_industry_uses_latest_asof_industry() -> None:
    scores = pd.DataFrame(
        [
            {"date": "2023-01-03", "code": "000001", "score": 3.0},
            {"date": "2023-01-03", "code": "000002", "score": 1.0},
            {"date": "2023-01-03", "code": "000003", "score": 7.0},
        ]
    )
    industries = pd.DataFrame(
        [
            {"ImplementDate": "2022-01-01", "Symbol": "000001", "IndustryName": "旧行业"},
            {"ImplementDate": "2023-01-02", "Symbol": "000001", "IndustryName": "新行业"},
            {"ImplementDate": "2023-01-01", "Symbol": "000002", "IndustryName": "新行业"},
            {"ImplementDate": "2023-01-04", "Symbol": "000003", "IndustryName": "未来行业"},
        ]
    )

    neutralized, summary = neutralize_scores_by_industry(scores, industries)

    assert neutralized["score"].tolist() == pytest.approx([1.0, -1.0, 0.0])
    assert summary.missing_industry_rows == 1
    assert summary.industry_count == 1


def test_neutralize_scores_by_industry_accepts_classification_name_fallback() -> None:
    scores = pd.DataFrame(
        [
            {"date": "2023-01-03", "code": "000001", "score": 4.0},
            {"date": "2023-01-03", "code": "000002", "score": 2.0},
        ]
    )
    industries = pd.DataFrame(
        [
            {
                "ImplementDate": "2022-12-31",
                "Symbol": "000001",
                "IndustryClassificationName": "制造业",
            },
            {
                "ImplementDate": "2022-12-31",
                "Symbol": "000002",
                "IndustryClassificationName": "制造业",
            },
        ]
    )

    neutralized, summary = neutralize_scores_by_industry(scores, industries)

    assert neutralized["score"].tolist() == pytest.approx([1.0, -1.0])
    assert summary.industry_column == "IndustryClassificationName"


def test_neutralize_scores_by_industry_accepts_mixed_datetime_units() -> None:
    scores = pd.DataFrame(
        {
            "date": pd.Series(["2023-01-03", "2023-01-03"], dtype="datetime64[ns]"),
            "code": ["000001", "000002"],
            "score": [4.0, 2.0],
        }
    )
    industries = pd.DataFrame(
        {
            "ImplementDate": pd.Series(
                ["2022-12-31", "2022-12-31"], dtype="datetime64[us]"
            ),
            "Symbol": ["000001", "000002"],
            "IndustryName": ["制造业", "制造业"],
        }
    )

    neutralized, summary = neutralize_scores_by_industry(scores, industries)

    assert neutralized["score"].tolist() == pytest.approx([1.0, -1.0])
    assert summary.neutralized_rows == 2


def test_neutralize_scores_by_industry_uses_grouped_merge_once_and_restores_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores = pd.DataFrame(
        [
            {"date": "2023-01-04", "code": "000002", "score": 1.0},
            {"date": "2023-01-03", "code": "000001", "score": 3.0},
            {"date": "2023-01-04", "code": "000001", "score": 5.0},
            {"date": "2023-01-04", "code": "000003", "score": 7.0},
        ]
    )
    industries = pd.DataFrame(
        [
            {"ImplementDate": "2023-01-02", "Symbol": "000001", "IndustryName": "银行"},
            {"ImplementDate": "2023-01-04", "Symbol": "000001", "IndustryName": "券商"},
            {"ImplementDate": "2023-01-03", "Symbol": "000002", "IndustryName": "银行"},
            {"ImplementDate": "2023-01-05", "Symbol": "000003", "IndustryName": "未来"},
        ]
    )
    original_merge_asof = neutralization_module.pd.merge_asof
    calls = {"count": 0}

    def counting_merge_asof(*args, **kwargs):
        calls["count"] += 1
        return original_merge_asof(*args, **kwargs)

    monkeypatch.setattr(neutralization_module.pd, "merge_asof", counting_merge_asof)

    neutralized, summary = neutralize_scores_by_industry(scores, industries)

    assert calls["count"] == 1
    assert neutralized["code"].tolist() == ["000002", "000001", "000001", "000003"]
    assert neutralized["date"].tolist() == [
        pd.Timestamp("2023-01-04"),
        pd.Timestamp("2023-01-03"),
        pd.Timestamp("2023-01-04"),
        pd.Timestamp("2023-01-04"),
    ]
    assert neutralized["score"].tolist() == pytest.approx([0.0, 0.0, 0.0, 0.0])
    assert summary.missing_industry_rows == 1
    assert summary.industry_count == 2
