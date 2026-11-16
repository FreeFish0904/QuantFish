"""DataGo 新闻提及动量策略。

策略想法：
- 过去一周被新闻频繁且高相关地提到，score 越高。
- 加一点成交金额确认，避免只追踪非常冷门的新闻噪声。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """统计过去 7 天报刊新闻对每只股票的提及强度。"""
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dnvaltrd"],
        numeric_columns=["dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    mentions = data.history(
        "新闻相关上市公司表",
        lookback_days=7,
        columns=["stkcd", "ment_times", "relev_score"],
        numeric_columns=["ment_times", "relev_score"],
    )

    base = pd.DataFrame(
        {
            "code": today["stkcd"].map(_code_for_merge),
            "liquidity": np.log1p(today["dnvaltrd"]),
        }
    )
    if mentions.empty:
        return pd.Series(_zscore(base["liquidity"]).values, index=today["stkcd"])

    mention_score = pd.DataFrame(
        {
            "code": mentions["stkcd"].map(_code_for_merge),
            "mention_strength": mentions["ment_times"] * mentions["relev_score"],
        }
    )
    mention_score = mention_score.groupby("code", as_index=False)[
        "mention_strength"
    ].sum()

    merged = base.merge(mention_score, on="code", how="left")
    score = _zscore(merged["mention_strength"].fillna(0.0))
    score = score + 0.10 * _zscore(merged["liquidity"])

    return pd.Series(score.values, index=today["stkcd"])


def _code_for_merge(value):
    """把 1、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
