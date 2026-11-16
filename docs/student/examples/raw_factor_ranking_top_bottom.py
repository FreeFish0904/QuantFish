"""Raw-data factor ranking lab.

This script is a local practice file, not a web-submission strategy.
It reads the raw `new_data/distribute` files with pandas/numpy, builds one
cross-sectional score, converts it into long-short weights, then prints the
top 20 and bottom 20 stocks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DAILY_PATH = (
    PROJECT_ROOT / "new_data" / "distribute" / "stock" / "daily_returns.parquet"
)
RAW_COMPANY_PATH = PROJECT_ROOT / "new_data" / "distribute" / "basic" / "company_info.csv"
LEARNING_DAILY_PATH = (
    PROJECT_ROOT
    / "data_releases"
    / "learning"
    / "distribute"
    / "stock"
    / "daily_returns.parquet"
)
LEARNING_COMPANY_PATH = (
    PROJECT_ROOT
    / "data_releases"
    / "learning"
    / "distribute"
    / "basic"
    / "company_info.csv"
)

DAILY_COLUMNS = [
    "stkcd",
    "trddt",
    "opnprc",
    "hiprc",
    "loprc",
    "clsprc",
    "dnshrtrd",
    "dnvaltrd",
    "dretwd",
    "dsmvosd",
    "markettype",
    "limitstatus",
]
NUMERIC_DAILY_COLUMNS = [
    "opnprc",
    "hiprc",
    "loprc",
    "clsprc",
    "dnshrtrd",
    "dnvaltrd",
    "dretwd",
    "dsmvosd",
    "markettype",
    "limitstatus",
]
COMPANY_COLUMNS = [
    "stkcd",
    "stknme",
    "conme",
    "indnme",
    "province",
    "city",
    "markettype",
    "listdt",
]
DISPLAY_COLUMNS = [
    "code",
    "stknme",
    "indnme",
    "province",
    "city",
    "side",
    "clsprc",
    "raw_vwap",
    "vwap_close_gap",
    "dretwd",
    "dnvaltrd",
    "score",
    "centered_score",
    "weighted_score",
]
FULL_OUTPUT_COLUMNS = [
    "rank",
    "code",
    "stknme",
    "conme",
    "indnme",
    "province",
    "city",
    "trddt",
    "side",
    "score",
    "centered_score",
    "abs_centered_score",
    "weighted_score",
    "raw_vwap",
    "clsprc",
    "vwap_close_gap",
    "intraday_return",
    "dretwd",
    "dnvaltrd",
    "dsmvosd",
    "markettype",
    "limitstatus",
]


def main() -> None:
    args = parse_args()
    daily_path, company_path, source_label = choose_data_paths()
    target_date = choose_target_date(daily_path, args.date)
    market_types = parse_market_types(args.market_types)

    daily = load_daily_slice(daily_path, target_date)
    ranked = build_factor_ranking(daily, company_path, market_types=market_types)

    print(f"Data source: {source_label}")
    print(f"Raw data date: {target_date.date().isoformat()}")
    print(f"Market types: {args.market_types}")
    print(f"Stocks after cleaning: {len(ranked)}")
    print(
        "Longshort rule: weighted_score = (score - mean(score)) / "
        "sum(abs(score - mean(score)))"
    )
    print("This stops before converting weights into VWAP execution or shares.")

    if ranked.empty:
        print("No valid stocks for this date. Try another --date.")
        return

    output_path = Path(args.output)
    write_full_weighted_scores(ranked, output_path)
    print(f"Full weighted-score list saved to: {output_path}")
    print_weight_summary(ranked)

    top = ranked.head(args.top)
    bottom = ranked.tail(args.top).sort_values("score", ascending=True)
    print_table(f"Top {args.top}: high score, long candidates", top)
    print_table(f"Bottom {args.top}: low score, short candidates", bottom)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute one raw-data factor and print top/bottom ranked stocks."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Trading date such as 2026-05-29. Defaults to the latest raw-data date.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many stocks to print on each side.",
    )
    parser.add_argument(
        "--market-types",
        default="1,4",
        help="Comma-separated markettype values. Use 'all' to keep every market.",
    )
    parser.add_argument(
        "--output",
        default="output/raw_factor_weighted_scores.csv",
        help="CSV path for the full score/weight list.",
    )
    return parser.parse_args()


def choose_data_paths() -> tuple[Path, Path, str]:
    candidates = [
        (RAW_DAILY_PATH, RAW_COMPANY_PATH, "new_data/distribute"),
        (LEARNING_DAILY_PATH, LEARNING_COMPANY_PATH, "data_releases/learning/distribute"),
    ]
    for daily_path, company_path, label in candidates:
        if daily_path.exists():
            return daily_path, company_path, label
    raise FileNotFoundError(
        "cannot find daily_returns.parquet under new_data/distribute or "
        "data_releases/learning/distribute"
    )


def choose_target_date(daily_path: Path, requested_date: str | None) -> pd.Timestamp:
    if requested_date:
        return pd.Timestamp(requested_date).normalize()

    dates = pd.read_parquet(daily_path, columns=["trddt"])
    latest = pd.to_datetime(dates["trddt"], errors="coerce").max()
    if pd.isna(latest):
        raise ValueError(f"cannot find any trading date in {daily_path}")
    return pd.Timestamp(latest).normalize()


def parse_market_types(value: str) -> set[int] | None:
    if value.strip().lower() == "all":
        return None
    market_types = set()
    for item in value.split(","):
        stripped = item.strip()
        if stripped:
            market_types.add(int(stripped))
    return market_types


def load_daily_slice(daily_path: Path, target_date: pd.Timestamp) -> pd.DataFrame:
    if not daily_path.exists():
        raise FileNotFoundError(f"raw daily file not found: {daily_path}")

    return pd.read_parquet(
        daily_path,
        columns=DAILY_COLUMNS,
        filters=[("trddt", "=", pd.Timestamp(target_date).normalize())],
    )


def build_factor_ranking(
    daily: pd.DataFrame,
    company_path: Path,
    *,
    market_types: set[int] | None,
) -> pd.DataFrame:
    rows = clean_daily_rows(daily, market_types=market_types)
    if rows.empty:
        return rows

    rows["raw_vwap"] = rows["dnvaltrd"] / rows["dnshrtrd"]
    rows["vwap_close_gap"] = rows["raw_vwap"] / rows["clsprc"] - 1.0
    rows["intraday_return"] = rows["clsprc"] / rows["opnprc"] - 1.0
    rows["liquidity_log"] = np.log1p(rows["dnvaltrd"])

    # A simple teaching factor:
    # - prefer stocks whose close is below the day's VWAP;
    # - add a small liquidity bonus;
    # - mildly avoid extreme intraday moves.
    rows["score"] = (
        zscore(rows["vwap_close_gap"])
        + 0.20 * zscore(rows["liquidity_log"])
        - 0.10 * zscore(rows["intraday_return"].abs())
    )
    weights = longshort_weight_table(rows["score"])
    rows["centered_score"] = weights["centered_score"]
    rows["abs_centered_score"] = weights["abs_centered_score"]
    rows["weighted_score"] = weights["weighted_score"]
    rows["side"] = np.select(
        [
            rows["weighted_score"] > 0,
            rows["weighted_score"] < 0,
        ],
        [
            "long",
            "short",
        ],
        default="flat",
    )

    info = load_company_info(company_path)
    ranked = rows.merge(info, on="code", how="left", suffixes=("", "_company"))
    ranked = ranked.dropna(subset=["score"]).sort_values(
        "score",
        ascending=False,
        kind="stable",
    )
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    return ranked.reset_index(drop=True)


def clean_daily_rows(
    daily: pd.DataFrame,
    *,
    market_types: set[int] | None,
) -> pd.DataFrame:
    rows = daily.copy()
    rows["code"] = normalize_code(rows["stkcd"])
    rows["trddt"] = pd.to_datetime(rows["trddt"], errors="coerce")
    for column in NUMERIC_DAILY_COLUMNS:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")

    if market_types is not None:
        rows = rows[rows["markettype"].isin(market_types)]

    valid = (
        rows["code"].notna()
        & rows["trddt"].notna()
        & (rows["opnprc"] > 0)
        & (rows["clsprc"] > 0)
        & (rows["dnshrtrd"] > 0)
        & (rows["dnvaltrd"] > 0)
    )
    return rows.loc[valid].reset_index(drop=True)


def load_company_info(company_path: Path) -> pd.DataFrame:
    if not company_path.exists():
        return pd.DataFrame({"code": pd.Series(dtype="object")})

    info = pd.read_csv(
        company_path,
        usecols=lambda column: column in COMPANY_COLUMNS,
        dtype={"stkcd": "string"},
    )
    info["code"] = normalize_code(info["stkcd"])
    keep = [
        column
        for column in COMPANY_COLUMNS
        if column in info.columns and column != "stkcd"
    ]
    return info.loc[:, ["code", *keep]].drop_duplicates("code", keep="last")


def normalize_code(values: pd.Series) -> pd.Series:
    text = pd.Series(values, copy=False).astype("string").str.strip()
    text = text.str.replace(r"\.0$", "", regex=True)
    return text.str.zfill(6).str[-6:]


def zscore(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(pd.Series(values, copy=False), errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


def longshort_weight_table(score: pd.Series) -> pd.DataFrame:
    numeric = pd.to_numeric(pd.Series(score, copy=False), errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    centered = numeric - numeric.mean(skipna=True)
    abs_centered = centered.abs()
    gross = centered.abs().sum(skipna=True)
    if not np.isfinite(gross) or gross == 0:
        weighted = centered.fillna(0.0) * 0.0
    else:
        weighted = (centered / gross).fillna(0.0)
    return pd.DataFrame(
        {
            "centered_score": centered.fillna(0.0),
            "abs_centered_score": abs_centered.fillna(0.0),
            "weighted_score": weighted,
        },
        index=score.index,
    )


def write_full_weighted_scores(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    available = [column for column in FULL_OUTPUT_COLUMNS if column in frame.columns]
    frame.loc[:, available].to_csv(output_path, index=False, encoding="utf-8-sig")


def print_weight_summary(frame: pd.DataFrame) -> None:
    weights = pd.to_numeric(frame["weighted_score"], errors="coerce").fillna(0.0)
    long_sum = float(weights[weights > 0].sum())
    short_sum = float(weights[weights < 0].sum())
    gross = float(weights.abs().sum())
    print(
        "Weight summary: "
        f"long={long_sum:.6f}, short={short_sum:.6f}, gross={gross:.6f}"
    )


def print_table(title: str, frame: pd.DataFrame) -> None:
    print()
    print(title)
    available = [column for column in DISPLAY_COLUMNS if column in frame.columns]
    table = frame.loc[:, available].copy()
    formatters = {
        "clsprc": "{:.3f}".format,
        "raw_vwap": "{:.3f}".format,
        "vwap_close_gap": "{:.4%}".format,
        "dretwd": "{:.4%}".format,
        "dnvaltrd": "{:,.0f}".format,
        "score": "{:.4f}".format,
        "centered_score": "{:.4f}".format,
        "weighted_score": "{:.6f}".format,
    }
    print(table.to_string(index=False, formatters=formatters))


if __name__ == "__main__":
    main()
