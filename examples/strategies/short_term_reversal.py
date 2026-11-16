"""短期反转策略。

策略想法：
- 当天涨得多的股票，下一天可能回落，score 降低。
- 当天跌得多的股票，下一天可能反弹，score 提高。
- 成交金额只给很小加分，让策略稍微偏向更容易交易的股票。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """读取当天行情，返回短期反转分数。"""
    # 1. 读数据：当天股票代码、日收益、成交金额。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd"],
        numeric_columns=["dretwd", "dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 算因子：day_return 是当天涨跌幅，liquidity 是成交活跃度。
    day_return = today["dretwd"]
    liquidity = np.log1p(today["dnvaltrd"])

    # 3. 合成 score：反转项前面是负号，所以跌得多的股票分数更高。
    score = -1.00 * _zscore(day_return) + 0.15 * _zscore(liquidity)

    # 4. 返回 Series。平台负责整理股票代码和执行交易限制。
    return pd.Series(score.values, index=today["stkcd"])


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
