"""Raw-data VWAP / close z-score ranking example.

这个脚本不是平台上传策略文件，而是给学生看的本地 raw data 练习脚本。

它做的事情：
1. 从 data_releases/learning/distribute 或 new_data/distribute 读取原始日行情。
2. 计算 raw_vwap = dnvaltrd / dnshrtrd。
3. 计算原始因子 factor = raw_vwap / clsprc。
4. 对当天所有股票的 factor 做横截面 z-score。
5. 把 score 转成 long-short weighted_score。
6. 保存全量 pre-return long-short ranking CSV。
7. 按 score 从高到低排序，打印前 20 和最后 20 只股票。

这个脚本故意停在 weighted_score，不计算 weighted_score * current_stock_return。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_FILENAME = "raw_vwap_close_pre_return_long_short_ranking.csv"

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
RAW_DAILY_PATH = (
    PROJECT_ROOT / "new_data" / "distribute" / "stock" / "daily_returns.parquet"
)
RAW_COMPANY_PATH = (
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
    "clsprc",
    "dnshrtrd",
    "dnvaltrd",
    "markettype",
    "limitstatus",
]
NUMERIC_DAILY_COLUMNS = [
    "opnprc",
    "clsprc",
    "dnshrtrd",
    "dnvaltrd",
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
PRINT_COLUMNS = [
    "rank",
    "code",
    "stknme",
    "indnme",
    "province",
    "city",
    "trddt",
    "clsprc",
    "raw_vwap",
    "vwap_close_factor",
    "score",
    "centered_score",
    "weighted_score",
    "side",
    "dnvaltrd",
    "markettype",
    "limitstatus",
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
    "clsprc",
    "raw_vwap",
    "vwap_close_factor",
    "score",
    "centered_score",
    "abs_centered_score",
    "weighted_score",
    "side",
    "dnshrtrd",
    "dnvaltrd",
    "markettype",
    "limitstatus",
]


def main() -> None:
    args = parse_args()
    daily_path, company_path, source_name = choose_data_paths(args.source)
    target_date = choose_target_date(daily_path, args.date)
    market_types = parse_market_types(args.market_types)

    daily = load_daily_slice(daily_path, target_date)
    ranked = build_vwap_close_ranking(
        daily,
        company_path,
        market_types=market_types,
    )

    print(f"Data source: {source_name}")
    print(f"Trading date: {target_date.date().isoformat()}")
    print(f"Market types: {args.market_types}")
    print(f"Stocks after cleaning: {len(ranked)}")
    print("Factor: vwap_close_factor = raw_vwap / clsprc")
    print("Score: cross-sectional z-score of vwap_close_factor")
    print(
        "Longshort rule: weighted_score = (score - mean(score)) / "
        "sum(abs(score - mean(score)))"
    )
    print("This stops before weighted_score * current_stock_return.")

    if ranked.empty:
        print("No valid stocks. Try another --date or --market-types all.")
        return

    balance = check_longshort_weight_balance(ranked)
    print(
        "Weight check passed: "
        f"long={balance['long_sum']:.6f}, "
        f"short={balance['short_sum']:.6f}, "
        f"net={balance['net_sum']:.6f}, "
        f"gross={balance['gross_sum']:.6f}"
    )

    if args.output:
        output_path = write_full_pre_return_ranking(ranked, Path(args.output))
    else:
        output_path = save_pre_return_ranking_next_to_script(ranked)
    print(f"Full ranking saved to: {output_path}")
    print_weight_summary(ranked)

    top = ranked.head(args.top)
    bottom = ranked.tail(args.top).sort_values("score", ascending=True)
    print_table(f"Top {args.top}: highest VWAP / close z-score", top)
    print_table(f"Bottom {args.top}: lowest VWAP / close z-score", bottom)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank stocks by z-score of raw_vwap / close from raw data."
    )
    parser.add_argument(
        "--source",
        choices=["learning", "raw", "auto"],
        default="learning",
        help="Use learning release, raw new_data, or auto fallback.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Trading date, for example 2022-06-30. Defaults to latest available date.",
    )
    parser.add_argument(
        "--market-types",
        default="1,4",
        help="Comma-separated markettype values. Use 'all' to keep every market.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many stocks to print from each end.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Where to save the full pre-return long-short ranking table. "
            "Defaults to the folder containing this script."
        ),
    )
    return parser.parse_args()


def choose_data_paths(source: str) -> tuple[Path, Path, str]:
    candidates = {
        "learning": (
            LEARNING_DAILY_PATH,
            LEARNING_COMPANY_PATH,
            "data_releases/learning/distribute",
        ),
        "raw": (
            RAW_DAILY_PATH,
            RAW_COMPANY_PATH,
            "new_data/distribute",
        ),
    }
    if source in {"learning", "raw"}:
        daily_path, company_path, source_name = candidates[source]
        if not daily_path.exists():
            raise FileNotFoundError(f"daily_returns.parquet not found: {daily_path}")
        return daily_path, company_path, source_name

    for daily_path, company_path, source_name in candidates.values():
        if daily_path.exists():
            return daily_path, company_path, source_name
    raise FileNotFoundError(
        "daily_returns.parquet not found under learning release or new_data"
    )


def choose_target_date(daily_path: Path, requested_date: str | None) -> pd.Timestamp:
    if requested_date:
        return pd.Timestamp(requested_date).normalize()

    dates = pd.read_parquet(daily_path, columns=["trddt"])
    latest = pd.to_datetime(dates["trddt"], errors="coerce").max()
    if pd.isna(latest):
        raise ValueError(f"cannot find trading dates in {daily_path}")
    return pd.Timestamp(latest).normalize()


def parse_market_types(value: str) -> set[int] | None:
    if value.strip().lower() == "all":
        return None
    result = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            result.add(int(item))
    return result


def load_daily_slice(daily_path: Path, target_date: pd.Timestamp) -> pd.DataFrame:
    return pd.read_parquet(
        daily_path,
        columns=DAILY_COLUMNS,
        filters=[("trddt", "=", pd.Timestamp(target_date).normalize())],
    )


def build_vwap_close_ranking(
    daily: pd.DataFrame,
    company_path: Path,
    *,
    market_types: set[int] | None,
) -> pd.DataFrame:
    rows = clean_daily_rows(daily, market_types=market_types)
    if rows.empty:
        return rows

    rows["raw_vwap"] = rows["dnvaltrd"] / rows["dnshrtrd"]
    rows["vwap_close_factor"] = rows["raw_vwap"] / rows["clsprc"]
    rows["score"] = zscore(rows["vwap_close_factor"])
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

    info = load_company_info([company_path, RAW_COMPANY_PATH])
    ranked = rows.merge(info, on="code", how="left", suffixes=("", "_company"))
    ranked = ranked.dropna(subset=["score"]).sort_values(
        "score",
        ascending=False,
        kind="stable",
    )
    ranked["rank"] = range(1, len(ranked) + 1)

    ordered = [column for column in PRINT_COLUMNS if column in ranked.columns]
    extra = [column for column in ranked.columns if column not in ordered]
    return ranked.loc[:, [*ordered, *extra]].reset_index(drop=True)


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
        & (rows["clsprc"] > 0)
        & (rows["dnshrtrd"] > 0)
        & (rows["dnvaltrd"] > 0)
    )
    return rows.loc[valid].reset_index(drop=True)


def load_company_info(company_paths: list[Path]) -> pd.DataFrame:
    frames = []
    for company_path in company_paths:
        if not company_path.exists():
            continue
        company = pd.read_csv(
            company_path,
            usecols=lambda column: column in COMPANY_COLUMNS,
            dtype={"stkcd": "string"},
        )
        company["code"] = normalize_code(company["stkcd"])
        keep = [
            column
            for column in COMPANY_COLUMNS
            if column in company.columns and column != "stkcd"
        ]
        frames.append(company.loc[:, ["code", *keep]])
    if not frames:
        return pd.DataFrame({"code": pd.Series(dtype="object")})

    # Prefer the first source, but let later sources fill codes missing from it.
    return pd.concat(frames, ignore_index=True).drop_duplicates("code", keep="first")


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


def print_weight_summary(frame: pd.DataFrame) -> None:
    weights = pd.to_numeric(frame["weighted_score"], errors="coerce").fillna(0.0)
    long_sum = float(weights[weights > 0].sum())
    short_sum = float(weights[weights < 0].sum())
    gross = float(weights.abs().sum())
    print(
        "Weight summary: "
        f"long={long_sum:.6f}, short={short_sum:.6f}, gross={gross:.6f}"
    )


def check_longshort_weight_balance(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    weights = pd.to_numeric(frame["weighted_score"], errors="coerce").fillna(0.0)
    summary = {
        "long_sum": round(float(weights[weights > 0].sum()), 12),
        "short_sum": round(float(weights[weights < 0].sum()), 12),
        "net_sum": round(float(weights.sum()), 12),
        "gross_sum": round(float(weights.abs().sum()), 12),
    }
    expected = {
        "long_sum": 0.5,
        "short_sum": -0.5,
        "net_sum": 0.0,
        "gross_sum": 1.0,
    }
    failed = [
        key
        for key, expected_value in expected.items()
        if not np.isclose(summary[key], expected_value, atol=tolerance, rtol=0.0)
    ]
    if failed:
        raise ValueError(
            "Long-short weight check failed: "
            f"long={summary['long_sum']:.6f}, "
            f"short={summary['short_sum']:.6f}, "
            f"net={summary['net_sum']:.6f}, "
            f"gross={summary['gross_sum']:.6f}"
        )
    return summary


def save_pre_return_ranking_next_to_script(
    frame: pd.DataFrame,
    filename: str = DEFAULT_OUTPUT_FILENAME,
) -> Path:
    return write_full_pre_return_ranking(frame, SCRIPT_DIR / filename)


def write_full_pre_return_ranking(frame: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    available = [column for column in FULL_OUTPUT_COLUMNS if column in frame.columns]
    frame.loc[:, available].to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def print_table(title: str, frame: pd.DataFrame) -> None:
    print()
    print(title)
    available = [column for column in PRINT_COLUMNS if column in frame.columns]
    table = frame.loc[:, available].copy()
    formatters = {
        "clsprc": "{:.3f}".format,
        "raw_vwap": "{:.3f}".format,
        "vwap_close_factor": "{:.6f}".format,
        "score": "{:.4f}".format,
        "centered_score": "{:.4f}".format,
        "weighted_score": "{:.6f}".format,
        "dnvaltrd": "{:,.0f}".format,
    }
    print(table.to_string(index=False, formatters=formatters))


if __name__ == "__main__":
    main()
