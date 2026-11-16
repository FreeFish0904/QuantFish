from __future__ import annotations

from collections import deque
from math import isfinite, sqrt

import numpy as np
import pandas as pd


WEIGHTS = {
    "close_weak": 0.2,
    "lowvol63": 0.2,
    "size_small": 0.2,
    "liq_low": 0.2,
    "intraday_rev": 0.2,
}

LONGS_PER_INDUSTRY = 1
ANCHORS_PER_LONG = 4
LONG_SCORE = 1.0
ANCHOR_SCORE = 0.0

_RETURN_WINDOWS: dict[str, deque[float]] = {}
_RETURN_SUMS: dict[str, float] = {}
_RETURN_SUMSQS: dict[str, float] = {}
_LAST_DATE = None
_RETURN_WINDOW_SIZE = 63
_LOWVOL_MIN_PERIODS = 30


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=[
            "stkcd",
            "opnprc",
            "hiprc",
            "loprc",
            "clsprc",
            "dnvaltrd",
            "dsmvosd",
            "dretwd",
            "limitstatus",
        ],
        numeric_columns=[
            "opnprc",
            "hiprc",
            "loprc",
            "clsprc",
            "dnvaltrd",
            "dsmvosd",
            "dretwd",
            "limitstatus",
        ],
    )
    if today.empty:
        return pd.Series(dtype=float)

    current = pd.DataFrame({"code": today["stkcd"].map(_code)})
    current["limitstatus"] = today["limitstatus"].fillna(0)

    _update_return_cache(current["code"], today["dretwd"], date)

    price_range = (today["hiprc"] - today["loprc"]).replace(0, np.nan)
    current["close_weak"] = (today["hiprc"] - today["clsprc"]) / price_range
    current["intraday_rev"] = -(today["clsprc"] / today["opnprc"].replace(0, np.nan) - 1.0)
    current["liq_low"] = -np.log1p(today["dnvaltrd"].where(today["dnvaltrd"] > 0))
    current["size_small"] = -np.log(today["dsmvosd"].where(today["dsmvosd"] > 0))
    current["lowvol63"] = _cached_lowvol63(current["code"]).to_numpy()

    base_score = pd.Series(0.0, index=current.index)
    for factor, weight in WEIGHTS.items():
        base_score = base_score + weight * _zscore(current[factor])
    current["base_score"] = base_score

    current = _attach_industry(data, current)
    shaped = _select_long_and_anchor_scores(current)
    if shaped.empty:
        return pd.Series(dtype=float)

    return pd.Series(shaped["score"].values, index=shaped["code"])


def _attach_industry(data, current):
    industry = _load_industry(data)
    if industry.empty:
        result = current.copy()
        result["industry"] = pd.NA
        return result

    symbol_column = _first_present(industry, ["Symbol", "code", "Stkcd", "stkcd"])
    industry_column = _first_present(
        industry,
        ["IndustryName", "IndustryClassificationName", "industry", "indnme"],
    )
    industry = industry.rename(
        columns={symbol_column: "raw_code", industry_column: "industry"}
    )
    industry["code"] = industry["raw_code"].map(_code)
    industry = industry.dropna(subset=["industry"])
    return current.merge(industry[["code", "industry"]], on="code", how="left")


def _load_industry(data):
    for dataset in ("basic.STK_INDUSTRYCLASS", "STK_INDUSTRYCLASS"):
        try:
            return data.latest(
                dataset,
                by="Symbol",
                columns=["Symbol", "IndustryName"],
            )
        except Exception:
            continue
    return pd.DataFrame()


def _select_long_and_anchor_scores(current):
    rows = current.copy()
    rows["base_score"] = pd.to_numeric(rows["base_score"], errors="coerce")
    rows["limitstatus"] = pd.to_numeric(rows["limitstatus"], errors="coerce").fillna(0)

    liquidity = _rank_pct(rows["liq_low"], ascending=False)
    stability = _rank_pct(rows["lowvol63"], ascending=True)
    neutral_alpha = _rank_pct(rows["base_score"].abs(), ascending=False)
    rows["anchor_quality"] = 0.50 * liquidity + 0.30 * stability + 0.20 * neutral_alpha

    rows = rows[
        rows["industry"].notna()
        & rows["base_score"].map(np.isfinite)
        & rows["limitstatus"].eq(0)
    ].copy()
    if rows.empty:
        return pd.DataFrame(columns=["code", "score"])

    selected = []
    for _, group in rows.groupby("industry", sort=False):
        if len(group) < 2:
            continue

        long_count = min(LONGS_PER_INDUSTRY, len(group) - 1)
        longs = group.nlargest(long_count, "base_score")
        remaining = group.drop(longs.index)
        if longs.empty or remaining.empty:
            continue

        anchor_count = min(len(remaining), max(1, ANCHORS_PER_LONG * len(longs)))
        anchors = remaining.nlargest(anchor_count, "anchor_quality")

        selected.append(pd.DataFrame({"code": longs["code"], "score": LONG_SCORE}))
        selected.append(pd.DataFrame({"code": anchors["code"], "score": ANCHOR_SCORE}))

    if not selected:
        return pd.DataFrame(columns=["code", "score"])

    shaped = pd.concat(selected, ignore_index=True)
    return shaped.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)


def _rank_pct(values, ascending=True):
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranked = numeric.rank(pct=True, ascending=ascending)
    return ranked.fillna(0.5)


def _first_present(frame, candidates):
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    folded = {str(column).lower(): column for column in frame.columns}
    for candidate in candidates:
        found = folded.get(candidate.lower())
        if found is not None:
            return found
    raise KeyError("missing required column")


def _update_return_cache(codes, returns, date):
    global _LAST_DATE
    current_date = pd.Timestamp(date).normalize()
    if _LAST_DATE is not None and current_date <= _LAST_DATE:
        _RETURN_WINDOWS.clear()
        _RETURN_SUMS.clear()
        _RETURN_SUMSQS.clear()
    _LAST_DATE = current_date

    cleaned = pd.to_numeric(returns, errors="coerce").to_numpy(dtype=float, copy=False)
    for code, value in zip(codes, cleaned):
        if not isfinite(value):
            continue

        raw_window = _RETURN_WINDOWS.get(code)
        if raw_window is None:
            raw_window = deque(maxlen=_RETURN_WINDOW_SIZE)
            _RETURN_WINDOWS[code] = raw_window
            _RETURN_SUMS[code] = 0.0
            _RETURN_SUMSQS[code] = 0.0

        if len(raw_window) == _RETURN_WINDOW_SIZE:
            dropped = raw_window.popleft()
            _RETURN_SUMS[code] -= dropped
            _RETURN_SUMSQS[code] -= dropped * dropped

        raw_window.append(float(value))
        _RETURN_SUMS[code] += float(value)
        _RETURN_SUMSQS[code] += float(value) * float(value)


def _cached_lowvol63(codes):
    values = []
    for code in codes:
        history = _RETURN_WINDOWS.get(code)
        if history is None or len(history) < _LOWVOL_MIN_PERIODS:
            values.append(np.nan)
            continue

        count = len(history)
        sum_raw = _RETURN_SUMS.get(code, 0.0)
        sumsq_raw = _RETURN_SUMSQS.get(code, 0.0)
        variance = (sumsq_raw - sum_raw * sum_raw / count) / (count - 1)
        if not isfinite(variance) or variance <= 0:
            values.append(0.0)
            continue
        values.append(-sqrt(variance))

    return pd.Series(values, index=codes.index)


def _zscore(values):
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).to_numpy(
        dtype=float,
        copy=False,
    )
    mask = np.isfinite(numeric)
    if not mask.any():
        return pd.Series(0.0, index=values.index)

    focused = numeric[mask]
    spread = focused.std(ddof=1)
    if not isfinite(spread) or spread == 0:
        return pd.Series(0.0, index=values.index)

    centered = np.zeros_like(numeric, dtype=float)
    centered[mask] = (focused - focused.mean()) / spread
    centered[~mask] = 0.0
    return pd.Series(np.clip(centered, -3.0, 3.0), index=values.index)


def _code(value):
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]