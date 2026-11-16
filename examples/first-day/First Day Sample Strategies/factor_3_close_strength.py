"""因子3：收盘强度 close / high。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- score = clsprc / hiprc。

怎么理解这个分数：
- hiprc 是当天最高价。
- clsprc 是当天收盘价。
- score 接近 1：收盘价仍然接近日内最高价，说明收盘较强。
- score 明显低于 1：股票从日内高点回落较多。

这里直接把 close / high 作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的收盘强度分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd  = 股票代码。
    # hiprc  = 当天最高价，是分母。
    # clsprc = 当天收盘价，是分子。
    #
    # numeric_columns 会让平台把价格字段转成数字，无法转换的值会变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "hiprc", "clsprc"],
        numeric_columns=["hiprc", "clsprc"],
    )

    # 2. 计算 close / high。
    # 如果最高价为 0 或缺失，平台会把最终无穷 score 整理成 NaN。
    score = today["clsprc"] / today["hiprc"]

    # 3. 返回 Series。平台会自动整理股票代码。
    return pd.Series(score.values, index=today["stkcd"])
