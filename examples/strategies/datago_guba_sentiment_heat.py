"""DataGo 股吧情绪热度策略。

策略想法：
- 股吧情绪越正面，score 越高。
- 阅读和发帖越多，说明讨论更活跃，信号权重更大。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """用当天股吧情绪和讨论热度给股票打分。"""
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    guba = data.current(
        "股吧量化舆情表(交易时段分组)",
        columns=[
            "Stock_Id",
            "Reads_All_AllUser_Sum",
            "Posts_All_AllUser_Sum",
            "Senti_Score_Div",
        ],
        numeric_columns=[
            "Reads_All_AllUser_Sum",
            "Posts_All_AllUser_Sum",
            "Senti_Score_Div",
        ],
    )

    base = pd.DataFrame(
        {
            "code": today["stkcd"].map(_code_for_merge),
            "day_return": today["dretwd"],
        }
    )
    if guba.empty:
        return pd.Series(_zscore(base["day_return"]).values, index=today["stkcd"])

    grouped = guba.groupby(guba["Stock_Id"].map(_code_for_merge)).agg(
        reads=("Reads_All_AllUser_Sum", "sum"),
        posts=("Posts_All_AllUser_Sum", "sum"),
        sentiment=("Senti_Score_Div", "mean"),
    )
    grouped["guba_score"] = grouped["sentiment"] * np.log1p(
        grouped["reads"] + grouped["posts"]
    )

    merged = base.merge(
        grouped[["guba_score"]].reset_index().rename(columns={"Stock_Id": "code"}),
        on="code",
        how="left",
    )
    score = _zscore(merged["guba_score"].fillna(0.0))
    score = score + 0.05 * _zscore(merged["day_return"])

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
