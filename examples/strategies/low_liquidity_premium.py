"""低流动性溢价策略。

策略想法：
- 成交金额越低，股票越“不活跃”。
- 这个样例假设低流动性股票未来可能有补偿收益，所以成交金额越低 score 越高。
- 这里只演示因子写法；真实交易限制由平台回测执行层处理。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """读取当天成交金额，返回低流动性分数。"""
    # 1. 读数据：只需要股票代码和成交金额。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dnvaltrd"],
        numeric_columns=["dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 算因子：成交金额取 log，降低极端大成交额的影响。
    liquidity = np.log1p(today["dnvaltrd"])

    # 3. 合成 score：前面加负号，成交越低，分数越高。
    score = -1.00 * _zscore(liquidity)

    # 4. 返回 Series，平台会自动整理股票代码。
    return pd.Series(score.values, index=today["stkcd"])


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
