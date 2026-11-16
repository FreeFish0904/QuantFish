"""因子6：日内步长因子。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- path_length = 2 * high - 2 * low + abs(close - open)。
- score = - path_length / (close - open)。

怎么理解这个分数：
- path_length 衡量股票当天在最高价和最低价之间“走了多远”。
- close - open 是当天从开盘到收盘的实际涨跌方向。
- 如果股票当天上涨，close - open 为正，前面的负号会让 score 变成负数。
- 如果股票当天下跌，close - open 为负，前面的负号会让 score 变成正数。
- 日内上下波动越大，score 的绝对值通常越大，表示当天走势更不稳定。

这里直接把原始因子作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的日内步长因子分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd  = 股票代码。
    # opnprc = 当天开盘价。
    # hiprc  = 当天最高价。
    # loprc  = 当天最低价。
    # clsprc = 当天收盘价。
    #
    # numeric_columns 会把价格字段转成数字，异常值会变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "opnprc", "hiprc", "loprc", "clsprc"],
        numeric_columns=["opnprc", "hiprc", "loprc", "clsprc"],
    )

    # 2. 计算日内步长。
    # abs(close - open) 表示不管涨跌，只看开盘到收盘的绝对距离。
    intraday_move = today["clsprc"] - today["opnprc"]
    path_length = (
        2.0 * today["hiprc"] - 2.0 * today["loprc"] + intraday_move.abs()
    )

    # 3. 计算最终 score。
    # 分母 close - open 保留涨跌方向；前面的负号让上涨日偏负、下跌日偏正。
    # 如果开盘价等于收盘价，平台会把最终无穷 score 整理成 NaN。
    score = -path_length / intraday_move

    # 4. 返回 Series。平台会自动整理股票代码，并把 score 转成回测仓位。
    return pd.Series(score.values, index=today["stkcd"])
