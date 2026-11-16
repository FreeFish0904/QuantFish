"""价格动量 + 成交活跃度策略。

策略想法：
- 当天收益越高，说明短期价格越强，score 越高。
- 成交金额越大，说明交易越活跃，给少量加分。
- 平台会用今天收盘后生成的 score，在下一个交易日模拟交易。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """读取当天行情，返回每只股票的动量分数。"""
    # 1. 读数据：只取策略真正需要的列。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd"],
        numeric_columns=["dretwd", "dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 算因子：日收益越高越好；成交金额取 log，避免少数超大值支配分数。
    day_return = today["dretwd"]
    liquidity = np.log1p(today["dnvaltrd"])

    # 3. 合成 score：价格动量为主，成交活跃度为辅。
    score = _zscore(day_return) + 0.20 * _zscore(liquidity)

    # 4. 返回信号：index 是原始股票代码，平台会自动整理成六位 code。
    return pd.Series(score.values, index=today["stkcd"])


def _zscore(values):
    """把一列因子变成当天横截面标准分，方便不同因子相加。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
