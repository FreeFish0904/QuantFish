"""因子5：中间价偏离 ((high + low) / 2) / close。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- midprice = (hiprc + loprc) / 2。
- score = midprice / clsprc。

怎么理解这个分数：
- midprice 是当天最高价和最低价的简单平均，也叫日内中间价。
- score 大于 1：中间价高于收盘价，说明收盘价相对日内中间价偏低。
- score 接近 1：中间价和收盘价接近。
- score 小于 1：中间价低于收盘价，说明收盘价相对日内中间价偏高。

这里直接把原始因子作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的中间价偏离分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd  = 股票代码。
    # hiprc  = 当天最高价，用来计算中间价。
    # loprc  = 当天最低价，用来计算中间价。
    # clsprc = 当天收盘价，是 midprice / close 的分母。
    #
    # numeric_columns 会把价格字段转成数字，异常值会变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "hiprc", "loprc", "clsprc"],
        numeric_columns=["hiprc", "loprc", "clsprc"],
    )

    # 2. 计算日内中间价。
    # 这个价格不是实际成交价，只是最高价和最低价的简单平均。
    midprice = (today["hiprc"] + today["loprc"]) / 2.0

    # 3. 计算 midprice / close。
    # 如果收盘价为 0 或缺失，平台会把最终无穷 score 整理成 NaN。
    score = midprice / today["clsprc"]

    # 4. 返回 Series。平台会自动整理股票代码，并把 score 转成回测仓位。
    return pd.Series(score.values, index=today["stkcd"])
