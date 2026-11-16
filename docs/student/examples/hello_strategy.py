# hello_strategy.py
# 这是 QuantFish 最小、最推荐先读的策略文件。
# 你只需要理解一件事：给每只股票算一个 score。

import pandas as pd


def generate_signals(data, date):
    """返回当前交易日的股票信号分数。

    data 是平台给你的“日期绑定数据视图”，只能看到 date 及以前的数据。
    date 是当前交易日；本例不直接使用它，因为 data.current(...) 已经绑定到当天。

    返回值用 pandas Series：
    - index 是股票代码；
    - value 是 score；
    - 平台会自动把股票代码整理成六位字符串，并把 score 转成仓位。
    """
    # 1. 读取当天日行情。第一天只需要两列：
    #    stkcd  = 股票代码；
    #    dretwd = 当天日收益率。
    #    numeric_columns 会让平台把 dretwd 转成数字，异常值自动变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )

    # 2. 直接使用平台已经转好的数字列。
    #    在 QuantFish 里，NaN 表示“这只股票今天没有信号”。
    day_return = today["dretwd"]

    # 3. 构造最简单的短期反转信号：
    #    当天跌得越多，day_return 越负；
    #    前面加一个负号后，score 越高。
    score = -day_return

    # 4. 用 Series 返回最简洁。
    #    你不需要手动把 1.0 改成 "000001"，平台会自动整理股票代码。
    return pd.Series(score.values, index=today["stkcd"])
