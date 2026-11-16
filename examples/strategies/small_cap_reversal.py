"""小市值 + 短期反转 + 低流动性策略。

策略想法：
- 市值越小，score 越高。
- 当天跌得越多，score 越高，表达短期反转。
- 成交金额越低，score 略高，表达低流动性溢价。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """读取当天行情，合成三个简单因子。"""
    # 1. 读数据：这里比入门策略多读市值和成交金额。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd", "dsmvosd", "dsmvtll"],
        numeric_columns=["dretwd", "dnvaltrd", "dsmvosd", "dsmvtll"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 算因子。
    #    dsmvosd 是流通市值；缺失时用 dsmvtll 总市值补一下。
    market_cap = today["dsmvosd"].fillna(today["dsmvtll"])
    market_cap = np.log1p(market_cap)
    day_return = today["dretwd"]
    liquidity = np.log1p(today["dnvaltrd"])

    # 3. 合成 score。
    #    三个负号分别表示：市值越小越好、当天收益越低越好、成交金额越低越好。
    score = (
        -0.65 * _zscore(market_cap)
        - 0.25 * _zscore(day_return)
        - 0.10 * _zscore(liquidity)
    )

    # 4. 返回 Series。平台负责股票代码规范化和交易执行限制。
    return pd.Series(score.values, index=today["stkcd"])


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
