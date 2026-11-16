"""因子0：VWAP / 收盘价。

这个文件是一个可以直接上传到 QuantFish 平台的完整策略文件。

核心公式：
- VWAP = dnvaltrd / dnshrtrd，也就是“成交金额 / 成交股数”。
- score = VWAP / clsprc，也就是“成交均价 / 收盘价”。

怎么理解这个分数：
- score 接近 1：当天成交均价和收盘价差不多。
- score 大于 1：全天平均成交价格高于收盘价，说明收盘相对全天成交均价偏低。
- score 小于 1：全天平均成交价格低于收盘价，说明收盘相对全天成交均价偏高。

这里不做 z-score 标准化，也不反转方向，直接把原始因子值作为 score。
在 QuantFish 里，score 越高，平台越倾向于把股票排在前面。
"""

import pandas as pd


def generate_signals(data, date):

    # 1. 读取当天日行情里真正需要的字段。
    # stkcd    = 股票代码，用来告诉平台“这个分数属于哪只股票”。
    # dnvaltrd = 当天成交金额，是计算 VWAP 的分子。
    # dnshrtrd = 当天成交股数，是计算 VWAP 的分母。
    # clsprc   = 当天收盘价，是计算 VWAP / close 的分母。

    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dnshrtrd", "dnvaltrd", "clsprc"],
        numeric_columns=["dnshrtrd", "dnvaltrd", "clsprc"],
    )

    # 2. 计算 VWAP。

    vwap = today["dnvaltrd"] / today["dnshrtrd"]

    # 3. 计算最终 score。

    score = vwap / today["clsprc"]

    # 4. 返回 Series。

    return pd.Series(score.values, index=today["stkcd"])
