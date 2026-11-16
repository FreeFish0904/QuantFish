# zscore_helper.py
# 进阶积木：横截面 z-score 标准化。
#
# 当你把“日收益”“成交金额”“市值”这些量纲不同的因子相加时，
# 需要先把它们放到同一尺度上。z-score 就是最常用的做法之一。

import numpy as np
import pandas as pd


def zscore(values):
    """把一列因子值变成“相对当天平均水平的标准分”。

    如果 values 来自平台数据，请优先在 data.current/history/latest/load 里
    使用 numeric_columns=[...]，让平台负责把异常文本和空值转成 NaN。

    返回值含义：
    - 大于 0：高于当天平均水平；
    - 小于 0：低于当天平均水平；
    - 等于 0：接近平均，或原始值缺失时给中性分。
    """
    numeric = pd.Series(values, copy=False).replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


if __name__ == "__main__":
    # 下面只是本地演示数据，不是正式策略。
    sample = pd.Series(
        [1.0, 2.0, 3.0, 4.0, 100.0],
        index=["000001", "000002", "000003", "000004", "000005"],
    )
    print("原始值：")
    print(sample)
    print("\nz-score 结果：")
    print(zscore(sample))
