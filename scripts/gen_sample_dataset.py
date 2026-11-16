#!/usr/bin/env python3
"""Generate a deterministic synthetic A-share dataset for the QuantFish demo.

The script writes raw tables that look like CSMAR exports - the layout that
``quantfish.data.releases`` already understands - and then optionally
materialises the learning / hidden-test releases described by a platform
config.

Usage::

    python scripts/gen_sample_dataset.py
    python scripts/gen_sample_dataset.py --output data/sample/raw --skip-releases

The generated dataset is intentionally small (about 40 symbols over seven
years) so the Docker demo can build releases and run a real backtest in a few
seconds. It is *synthetic*: prices, volumes and industries are simulated and
carry no market information.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "sample" / "raw"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "platform.demo.yaml"

INDUSTRIES = ("银行", "医药生物", "电子", "计算机")
MARKET_SEGMENTS = (("600", 1, 18), ("000", 4, 14), ("002", 4, 14), ("300", 16, 14))
INDEX_SERIES = (("000300", "沪深300", 1.0), ("000001", "上证指数", 0.72), ("000905", "中证500", 1.18))


def _business_days(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, end=end)


def _build_universe(count: int, rng: random.Random) -> list[dict[str, object]]:
    """Return stock metadata: code, market type and industry."""

    universe: list[dict[str, object]] = []
    for prefix, market_type, segment_size in MARKET_SEGMENTS:
        for offset in range(segment_size):
            code = f"{prefix}{offset + 1:03d}"
            universe.append(
                {
                    "code": code,
                    "market_type": market_type,
                    "industry": INDUSTRIES[(offset + market_type) % len(INDUSTRIES)],
                    "volatility": rng.uniform(0.013, 0.026),
                    "drift": rng.uniform(-0.00025, 0.00085),
                    "start_price": rng.uniform(8.0, 60.0),
                    "free_float": rng.uniform(2.0e8, 4.0e9),
                    "pays_dividend": rng.random() < 0.55,
                    "suspended": rng.random() < 0.15,
                }
            )
    return universe[:count]


def _listing_dates(
    universe: list[dict[str, object]],
    trading_days: pd.DatetimeIndex,
    rng: random.Random,
) -> dict[str, pd.Timestamp]:
    """Most symbols are listed before the sample, a few list inside it."""

    dates: dict[str, pd.Timestamp] = {}
    late_candidates = set(rng.sample([item["code"] for item in universe], k=3))
    for item in universe:
        code = str(item["code"])
        if code in late_candidates:
            offset = rng.randrange(len(trading_days) // 4, len(trading_days) - 60)
            dates[code] = trading_days[offset]
        else:
            dates[code] = pd.Timestamp("2010-01-04") + pd.Timedelta(days=rng.randrange(0, 2500))
    return dates


def _dividend_schedule(dates: pd.DatetimeIndex, rng: random.Random) -> dict[pd.Timestamp, float]:
    """Pick three ex-dividend days per year with a 1-3% payout."""

    schedule: dict[pd.Timestamp, float] = {}
    for year in sorted({date.year for date in dates}):
        for month, day in ((6, 20), (9, 20), (12, 20)):
            candidate = pd.Timestamp(year=year, month=month, day=day)
            position = int(dates.searchsorted(candidate))
            if position >= len(dates):
                continue
            schedule[dates[position]] = rng.uniform(0.01, 0.03)
    return schedule


def _simulate_stock(
    item: dict[str, object],
    trading_days: pd.DatetimeIndex,
    list_date: pd.Timestamp,
    rng: random.Random,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    code = str(item["code"])
    volatility = float(item["volatility"])
    drift = float(item["drift"])
    dates = trading_days[trading_days >= list_date]
    if len(dates) < 120:
        dates = trading_days[-240:]

    schedule = _dividend_schedule(dates, rng) if item["pays_dividend"] else {}
    factor = 1.0
    forward_factors: list[float] = []
    for date in dates:
        if date in schedule:
            factor *= 1.0 + schedule[date]
        forward_factors.append(factor)
    latest_factor = forward_factors[-1] if forward_factors else 1.0

    suspended: set[pd.Timestamp] = set()
    if item["suspended"]:
        start = rng.randrange(len(dates) // 3, max(len(dates) // 3 + 1, len(dates) - 90))
        suspended.update(dates[start : start + rng.randrange(4, 12)])

    price = float(item["start_price"])
    rows: list[dict[str, object]] = []
    factor_rows: list[dict[str, object]] = []
    # A weakly persistent intraday signal (VWAP / close - 1) predicts returns
    # two days ahead: the engine scores on day t and fills at day t+1 VWAP, so
    # a day-t signal can only pay off from day t+1 to t+2. This is a synthetic,
    # deliberately weak edge - not market data.
    signal = rng.gauss(0.0, 1.0)
    history = [0.0, 0.0]
    persistence = 0.7
    for index, date in enumerate(dates):
        shock = drift + 0.0018 * history[0] + rng.gauss(0.0, volatility)
        shock = max(min(shock, 0.095), -0.095)
        signal = persistence * signal + (1.0 - persistence**2) ** 0.5 * rng.gauss(0.0, 1.0)
        previous_price = price
        price = max(1.0, price * (1.0 + shock))
        cumulative_factor = forward_factors[index] / latest_factor
        raw_close = round(price / cumulative_factor, 2)
        factor_rows.append(
            {
                "tradingdate": date.strftime("%Y-%m-%d"),
                "stkcd": code,
                "cumulatefwardfactor": round(cumulative_factor, 8),
            }
        )
        if date in suspended:
            history = [history[1], signal]
            continue
        turnover = min(0.045, max(0.0015, rng.gauss(0.008, 0.004)))
        volume = int(float(item["free_float"]) * turnover)
        # Intraday shape: an overnight gap, a VWAP tilted by today's signal and
        # a high/low range that always contains open, close and VWAP.
        open_price = previous_price * (1.0 + rng.gauss(0.0, 0.004))
        vwap_price = price * (1.0 + 0.004 * signal)
        high_price = max(open_price, price, vwap_price) * (1.0 + abs(rng.gauss(0.0, 0.003)))
        low_price = min(open_price, price, vwap_price) * (1.0 - abs(rng.gauss(0.0, 0.003)))
        raw_open = round(open_price / cumulative_factor, 2)
        raw_high = round(high_price / cumulative_factor, 2)
        raw_low = round(low_price / cumulative_factor, 2)
        raw_vwap = round(vwap_price / cumulative_factor, 2)
        amount = round(raw_vwap * volume, 2)
        rows.append(
            {
                "stkcd": code,
                "trddt": date.strftime("%Y-%m-%d"),
                "dretwd": round(shock, 6),
                "opnprc": raw_open,
                "hiprc": raw_high,
                "loprc": raw_low,
                "clsprc": raw_close,
                "dnshrtrd": volume,
                "dnvaltrd": amount,
                "markettype": int(item["market_type"]),
            }
        )
        history = [history[1], signal]

    return pd.DataFrame(rows), pd.DataFrame(factor_rows), list_date


def _build_index_rows(
    trading_days: pd.DatetimeIndex,
    market_returns: pd.Series,
    rng: random.Random,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    base_levels = {"000300": 4000.0, "000001": 3200.0, "000905": 5800.0}
    for code, name, scale in INDEX_SERIES:
        level = base_levels[code]
        for date, market_return in zip(trading_days, market_returns, strict=True):
            change = float(market_return) * scale + rng.gauss(0.0, 0.0015)
            level = max(100.0, level * (1.0 + change))
            rows.append(
                {
                    "indexcd": code,
                    "idxtrd01": date.strftime("%Y-%m-%d"),
                    "idxtrd05": round(level, 2),
                    "idxtrd08": round(change * 100, 4),
                    "idxtrd09": name,
                }
            )
    return pd.DataFrame(rows)


def generate_dataset(
    output: Path,
    *,
    stocks: int = 60,
    start: str = "2018-01-01",
    end: str = "2024-12-31",
    seed: int = 20240101,
) -> dict[str, Path]:
    """Write the raw synthetic tables under ``output`` and return their paths."""

    rng = random.Random(seed)
    trading_days = _business_days(start, end)
    universe = _build_universe(stocks, rng)
    listing = _listing_dates(universe, trading_days, rng)

    returns_frames: list[pd.DataFrame] = []
    factor_frames: list[pd.DataFrame] = []
    industry_rows: list[dict[str, str]] = []
    company_rows: list[dict[str, str]] = []

    for item in universe:
        code = str(item["code"])
        daily, factors, list_date = _simulate_stock(item, trading_days, listing[code], rng)
        returns_frames.append(daily)
        factor_frames.append(factors)
        # Point-in-time rows: one snapshot per year so every release window
        # carries at least one as-of record for static reference tables.
        for year in range(2010, int(end[:4]) + 1):
            industry_rows.append(
                {
                    "ImplementDate": f"{year}-01-01",
                    "stkcd": code,
                    "IndustryName": str(item["industry"]),
                }
            )
            company_rows.append(
                {
                    "stkcd": code,
                    "listdt": list_date.strftime("%Y-%m-%d"),
                    "statdt": f"{year}-01-01",
                }
            )

    daily_returns = pd.concat(returns_frames, ignore_index=True)
    adj_factor = pd.concat(factor_frames, ignore_index=True)
    market_returns = (
        daily_returns.groupby("trddt")["dretwd"]
        .mean()
        .reindex(trading_days.strftime("%Y-%m-%d"))
        .fillna(0.0)
    )
    index_daily = _build_index_rows(trading_days, market_returns, rng)

    stock_dir = output / "distribute" / "stock"
    market_dir = output / "distribute" / "market"
    basic_dir = output / "distribute" / "basic"
    factor_dir = output / "teacher" / "factor_benchmark"
    for directory in (stock_dir, market_dir, basic_dir, factor_dir):
        directory.mkdir(parents=True, exist_ok=True)

    paths = {
        "daily_returns": stock_dir / "daily_returns.parquet",
        "adj_factor": factor_dir / "adj_factor.parquet",
        "index_daily": market_dir / "index_daily.csv",
        "industry": basic_dir / "STK_INDUSTRYCLASS.csv",
        "company_info": basic_dir / "company_info.csv",
    }
    daily_returns.to_parquet(paths["daily_returns"], index=False)
    adj_factor.to_parquet(paths["adj_factor"], index=False)
    index_daily.to_csv(paths["index_daily"], index=False, encoding="utf-8-sig")
    pd.DataFrame(industry_rows).to_csv(paths["industry"], index=False, encoding="utf-8-sig")
    pd.DataFrame(company_rows).to_csv(
        paths["company_info"], index=False, encoding="utf-8-sig"
    )
    return paths


def _human_size(path: Path) -> str:
    size = float(path.stat().st_size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the QuantFish synthetic dataset.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Raw source data root.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Config used to build releases.")
    parser.add_argument("--stocks", type=int, default=60, help="Number of simulated symbols.")
    parser.add_argument("--start", default="2018-01-01", help="First trading day.")
    parser.add_argument("--end", default="2024-12-31", help="Last trading day.")
    parser.add_argument("--seed", type=int, default=20240101, help="Random seed.")
    parser.add_argument(
        "--skip-releases",
        action="store_true",
        help="Only write the raw tables and skip building data releases.",
    )
    args = parser.parse_args(argv)

    output = Path(args.output).resolve()
    paths = generate_dataset(
        output,
        stocks=args.stocks,
        start=args.start,
        end=args.end,
        seed=args.seed,
    )
    print(f"Raw dataset written to {output}")
    for name, path in paths.items():
        print(f"  {name:14s} {_human_size(path):>10s}  {path}")

    if not args.skip_releases:
        from quantfish.data.releases import build_releases_from_config
        from quantfish.platform_config import ConfigRepository

        config = ConfigRepository(Path(args.config)).load()
        releases = build_releases_from_config(config)
        print("Releases built:")
        for name, catalog in releases.items():
            print(f"  {name:14s} {len(catalog.datasets):2d} datasets  {catalog.root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
