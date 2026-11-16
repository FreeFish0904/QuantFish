from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from quantfish.data.scoring_datasets import INDUSTRY_DATASET
from quantfish.stock_codes import normalize_stock_code


DEFAULT_INDUSTRY_DATASET = INDUSTRY_DATASET
INDUSTRY_COLUMN_CANDIDATES = [
    "IndustryName",
    "IndustryClassificationName",
    "industry",
    "indnme",
]


@dataclass(frozen=True)
class IndustryNeutralizationSummary:
    enabled: bool
    dataset: str
    industry_column: str | None
    signal_rows: int
    neutralized_rows: int
    missing_industry_rows: int
    industry_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def disabled_summary(signal_rows: int = 0) -> IndustryNeutralizationSummary:
    return IndustryNeutralizationSummary(
        enabled=False,
        dataset=DEFAULT_INDUSTRY_DATASET,
        industry_column=None,
        signal_rows=signal_rows,
        neutralized_rows=0,
        missing_industry_rows=0,
        industry_count=0,
    )


def industry_column_for(industry_rows: pd.DataFrame) -> str:
    return _find_column(industry_rows, INDUSTRY_COLUMN_CANDIDATES)


def neutralize_scores_by_industry(
    scores: pd.DataFrame,
    industry_rows: pd.DataFrame,
    *,
    dataset: str = DEFAULT_INDUSTRY_DATASET,
) -> tuple[pd.DataFrame, IndustryNeutralizationSummary]:
    if scores.empty:
        return (
            scores.copy(),
            IndustryNeutralizationSummary(
                enabled=True,
                dataset=dataset,
                industry_column=None,
                signal_rows=0,
                neutralized_rows=0,
                missing_industry_rows=0,
                industry_count=0,
            ),
        )

    industry_column = industry_column_for(industry_rows)
    merged = _with_asof_industry(scores, industry_rows, industry_column)
    neutralized = merged.loc[:, ["date", "code", "score"]].copy()
    neutralized["score"] = pd.to_numeric(neutralized["score"], errors="coerce")

    score_present = neutralized["score"].notna()
    known_industry = merged["industry"].notna()
    neutralizable = score_present & known_industry
    missing_industry = score_present & ~known_industry

    if neutralizable.any():
        industry_means = merged.loc[neutralizable].groupby(
            ["date", "industry"]
        )["score"].transform("mean")
        neutralized.loc[neutralizable, "score"] = (
            merged.loc[neutralizable, "score"].astype(float).to_numpy()
            - industry_means.astype(float).to_numpy()
        )
    neutralized.loc[missing_industry, "score"] = 0.0

    summary = IndustryNeutralizationSummary(
        enabled=True,
        dataset=dataset,
        industry_column=industry_column,
        signal_rows=int(len(scores)),
        neutralized_rows=int(neutralizable.sum()),
        missing_industry_rows=int(missing_industry.sum()),
        industry_count=int(merged.loc[known_industry, "industry"].nunique()),
    )
    return neutralized, summary


def _with_asof_industry(
    scores: pd.DataFrame,
    industry_rows: pd.DataFrame,
    industry_column: str,
) -> pd.DataFrame:
    score_rows = scores.loc[:, ["date", "code", "score"]].copy()
    score_rows["_order"] = range(len(score_rows))
    score_rows["date"] = _normalized_datetime_key(score_rows["date"])
    score_rows["code"] = score_rows["code"].map(normalize_stock_code)
    score_rows["score"] = pd.to_numeric(score_rows["score"], errors="coerce")

    industry_date = _find_column(industry_rows, ["ImplementDate", "date", "TradingDate"])
    industry_symbol = _find_column(industry_rows, ["Symbol", "code", "Stkcd", "stkcd"])
    industries = industry_rows.loc[
        :, [industry_date, industry_symbol, industry_column]
    ].rename(
        columns={
            industry_date: "date",
            industry_symbol: "code",
            industry_column: "industry",
        }
    )
    industries["date"] = _normalized_datetime_key(industries["date"])
    industries["code"] = industries["code"].map(normalize_stock_code)
    industries["industry"] = industries["industry"].replace("", pd.NA)
    industries = industries.dropna(subset=["date", "code", "industry"])

    if score_rows.empty:
        return score_rows.assign(industry=pd.NA)
    if industries.empty:
        return score_rows.assign(industry=pd.NA)
    merged = pd.merge_asof(
        score_rows.sort_values(["date", "code"]).reset_index(drop=True),
        industries.loc[:, ["date", "code", "industry"]]
        .sort_values(["date", "code"])
        .reset_index(drop=True),
        on="date",
        by="code",
        direction="backward",
    )
    return merged.sort_values("_order").reset_index(drop=True)


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    raise KeyError(f"missing required column; tried {', '.join(candidates)}")


def _normalized_datetime_key(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values).dt.normalize().astype("datetime64[ns]")
