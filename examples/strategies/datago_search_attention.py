"""DataGo 百度搜索关注度策略。

策略想法：
- 当天搜索关注度越高，说明市场关注越集中，score 越高。
- 加一点当天收益确认，避免只看舆情热度。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """用 DataGo 搜索指数给当天股票池打分。"""
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    search = data.current(
        "上市公司网络搜索分析数据表",
        columns=["stock_id", "index_all"],
        numeric_columns=["index_all"],
    )

    base = pd.DataFrame(
        {
            "code": today["stkcd"].map(_code_for_merge),
            "day_return": today["dretwd"],
        }
    )
    search_score = pd.DataFrame(
        {
            "code": search["stock_id"].map(_code_for_merge),
            "attention": search["index_all"],
        }
    )
    search_score = search_score.groupby("code", as_index=False)["attention"].mean()

    merged = base.merge(search_score, on="code", how="left")
    attention_score = _zscore(merged["attention"].fillna(0.0))
    market_score = _zscore(merged["day_return"])
    score = -1 * (attention_score + 0.10 * market_score)

    return pd.Series(score.values, index=today["stkcd"])


def _code_for_merge(value):
    """把 000001.SZ、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if "." in code:
        code = code.split(".", 1)[0]
    return code.zfill(6)[-6:]


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
