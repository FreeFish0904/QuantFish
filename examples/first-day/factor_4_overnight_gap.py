"""因子4：隔夜跳空 open / precloseprice - 1。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- score = opnprc / precloseprice - 1。

怎么理解这个分数：
- opnprc 是今天开盘价。
- precloseprice 是昨日收盘价。
- score 为正：今天相对昨日收盘高开。
- score 为负：今天相对昨日收盘低开。

这里直接把隔夜跳空幅度作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的隔夜跳空分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd         = 股票代码。
    # opnprc        = 今天开盘价，是分子。
    # precloseprice = 昨日收盘价，是分母。
    #
    # numeric_columns 会把开盘价和昨日收盘价转成数字。
    # 如果原始数据里有空值或异常文本，平台会转成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "opnprc", "precloseprice"],
        numeric_columns=["opnprc", "precloseprice"],
    )

    # 2. 先计算 open / precloseprice。
    # 如果 precloseprice 为 0 或缺失，平台会把最终无穷 score 整理成 NaN。
    open_preclose_ratio = today["opnprc"] / today["precloseprice"]

    # 3. 减去 1，得到隔夜跳空幅度。
    # 例子：昨日收盘 10 元，今天开盘 10.2 元，score = 0.02。
    score = open_preclose_ratio - 1.0

    # 4. 返回 Series。平台会自动整理股票代码并处理 NaN 信号。
    return pd.Series(score.values, index=today["stkcd"])
