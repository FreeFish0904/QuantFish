from __future__ import annotations


def starter_strategy_text() -> str:
    return '''"""价格成交额动量 starter strategy。

这个文件是 QuantFish 默认下载的入门策略模板。

核心想法：
- 每个交易日，平台会把当天及以前可见的数据交给 generate_signals。
- 学生主要负责构造 score：score 越高，平台越看好这只股票。
- 这里用价格-成交额动量：当天收益越高、成交越活跃，分数越高。
- 涨跌停或交易受限的股票给 0 分，表示今天先不主动交易它。
- 平台会自动整理股票代码、把分数转换成仓位，并在下一个交易日模拟交易。
"""

import numpy as np
import pandas as pd


def generate_signals(data, date):
    """返回当前交易日的股票信号分数。

    data:
        平台传进来的日期绑定数据视图，只能看到 date 及以前的数据。
    date:
        当前交易日。这个模板里不直接使用它，因为 data.current(...) 已经绑定到当天。
    返回值:
        一个 DataFrame，包含 code 和 score 两列。
        code 是六位股票代码，score 是这只股票今天的信号分数。
    """
    # 1. 读取当天日行情里真正需要的列：
    #    stkcd       = 股票代码
    #    dretwd      = 当天日收益率
    #    dnvaltrd    = 当天成交金额，越大说明成交越活跃
    #    limitstatus = 涨跌停 / 交易受限状态，0 表示正常交易
    #    numeric_columns 告诉平台把这些字段转成数字。
    #    如果某一行是空值或异常文本，平台会自动把它变成 NaN。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "trddt", "clsprc", "dretwd", "dnvaltrd", "limitstatus"],
        numeric_columns=["clsprc", "dretwd", "dnvaltrd", "limitstatus"],
    )
    if today.empty:
        return pd.DataFrame({"code": [], "score": []})

    # 2. 把股票代码统一成六位字符串，方便自己检查和合并表格。
    #    例如 1、1.0、"1" 都会变成 "000001"。
    codes = today["stkcd"].map(_normalize_code)

    # 3. 价格动量：当天收益率越高，day_return 越高。
    #    numeric_columns 已经把 dretwd 转成数字；异常文本或空值现在是 NaN。
    day_return = today["dretwd"]

    # 4. 成交活跃度：成交金额越大，通常代表市场关注度越高。
    #    log1p 会压缩极端大成交额，避免一只特别大的股票把分数拉得过猛。
    liquidity = np.log1p(today["dnvaltrd"].clip(lower=0.0))

    # 5. z-score 会把不同量纲放到同一尺度：
    #    zscore(day_return) 看“收益率相对当天其他股票高不高”；
    #    zscore(liquidity) 看“成交活跃度相对当天其他股票高不高”。
    #    0.20 表示成交活跃度只是辅助，主要信号仍然是当天收益。
    score = _zscore(day_return) + 0.20 * _zscore(liquidity)

    # 6. 涨跌停 / 交易受限股票给 0 分。
    #    0 分不是看空，而是中性：今天不让它影响排序。
    blocked = today["limitstatus"].ne(0)
    score = score.where(~blocked, 0.0)

    # 7. 返回 code 和 score 两列。
    #    平台收到后会继续检查格式，并把 score 转成真实回测仓位。
    return pd.DataFrame({"code": codes, "score": score})


def _zscore(values):
    """把一列数值变成横截面标准分，缺失值给中性分 0。"""
    numeric = pd.Series(values, copy=False).replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return pd.Series(0.0, index=numeric.index)
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


def _normalize_code(value):
    """把股票代码整理成六位字符串，例如 1.0 -> "000001"。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]
'''
