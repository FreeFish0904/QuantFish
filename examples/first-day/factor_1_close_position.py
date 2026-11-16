"""因子1：收盘位置 (close - low) / (high - low)。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- score = (clsprc - loprc) / (hiprc - loprc)。

怎么理解这个分数：
- 分母 hiprc - loprc 是当天最高价和最低价之间的价格区间。
- 分子 clsprc - loprc 是收盘价比当天最低价高多少。
- score 接近 1：收盘价靠近日内最高价。
- score 接近 0：收盘价靠近日内最低价。

如果最高价等于最低价，说明当天没有有效的日内价格区间，score 会记为 NaN。
这里直接把原始因子值作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的收盘位置分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd  = 股票代码，用来作为返回 Series 的 index。
    # hiprc  = 当天最高价，是日内价格区间的上边界。
    # loprc  = 当天最低价，是日内价格区间的下边界。
    # clsprc = 当天收盘价，是我们要判断位置的价格。
    #
    # numeric_columns 会把价格字段转成数字，异常值会变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "hiprc", "loprc", "clsprc"],
        numeric_columns=["hiprc", "loprc", "clsprc"],
    )

    # 2. 计算日内完整价格区间。
    # 如果 hiprc == loprc，daily_range 为 0，说明当天没有可用的价格范围。
    daily_range = today["hiprc"] - today["loprc"]

    # 3. 计算收盘价距离最低价的距离。
    # 这个值越大，说明收盘价越靠近高位。
    close_above_low = today["clsprc"] - today["loprc"]

    # 4. 计算收盘位置 score。
    # 如果 daily_range 为 0，平台会把最终无穷 score 整理成 NaN。
    score = close_above_low / daily_range

    # 5. 返回 Series。平台会继续整理股票代码并验证分数格式。
    return pd.Series(score.values, index=today["stkcd"])
