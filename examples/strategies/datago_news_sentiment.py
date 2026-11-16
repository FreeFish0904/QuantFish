"""DataGo 新闻情绪策略。

策略想法：
- 新闻本身有情绪分数。
- 新闻相关上市公司表告诉我们这条新闻影响哪些股票。
- 用 news_id 合并两张表，把新闻情绪分配到股票上。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """用过去 3 天新闻情绪给股票打分。"""
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    news = data.history(
        "新闻情感量化数据表",
        lookback_days=3,
        columns=["news_id", "overall_senti_score"],
        numeric_columns=["overall_senti_score"],
    )
    links = data.history(
        "新闻相关上市公司表",
        lookback_days=3,
        columns=["news_id", "stkcd", "relev_score"],
        numeric_columns=["relev_score"],
    )

    base = pd.DataFrame(
        {
            "code": today["stkcd"].map(_code_for_merge),
            "day_return": today["dretwd"],
        }
    )
    if news.empty or links.empty:
        return pd.Series(_zscore(base["day_return"]).values, index=today["stkcd"])

    joined = links.merge(news, on="news_id", how="inner")
    joined["weighted_sentiment"] = (
        joined["overall_senti_score"] * joined["relev_score"]
    )
    sentiment = pd.DataFrame(
        {
            "code": joined["stkcd"].map(_code_for_merge),
            "sentiment": joined["weighted_sentiment"],
        }
    )
    sentiment = sentiment.groupby("code", as_index=False)["sentiment"].mean()

    merged = base.merge(sentiment, on="code", how="left")
    score = _zscore(merged["sentiment"].fillna(0.0))
    score = score + 0.10 * _zscore(merged["day_return"])

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
