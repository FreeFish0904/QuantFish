"""因子2：日内涨幅 close / open - 1。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- score = clsprc / opnprc - 1。

怎么理解这个分数：
- score 为正：收盘价高于开盘价，股票当天日内上涨。
- score 为负：收盘价低于开盘价，股票当天日内下跌。
- score 等于 0：收盘价和开盘价相同。

这里直接把日内涨幅作为 score，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):
    """读取当前交易日的数据，返回每只股票的日内涨幅分数。"""
    # 1. 读取当天日行情里真正需要的字段。
    # stkcd  = 股票代码。
    # opnprc = 当天开盘价，是日内涨幅计算的起点和分母。
    # clsprc = 当天收盘价，是日内涨幅计算的终点和分子。
    #
    # numeric_columns 会把开盘价和收盘价转成数字。
    # 如果原始数据里有空值或异常文本，平台会转成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "opnprc", "clsprc"],
        numeric_columns=["opnprc", "clsprc"],
    )

    # 2. 先计算 close / open。
    # 如果 opnprc 为 0 或缺失，平台会把最终无穷 score 整理成 NaN。
    close_open_ratio = today["clsprc"] / today["opnprc"]

    # 3. 减去 1，得到日内简单收益率。
    # 例子：开盘 10 元，收盘 10.5 元，score = 10.5 / 10 - 1 = 0.05。
    score = close_open_ratio - 1.0

    # 4. 返回 Series。index 是股票代码，value 是 score。
    return pd.Series(score.values, index=today["stkcd"])
