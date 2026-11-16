"""Long-only 小市值 + 长期反转行业锚点策略。

策略想法：
- 小市值股票在当前 learning track 的 long-only 回测里表现较好。
- 再加入一点长期反转：过去累计收益较低的股票，给更高分。
- 策略只使用 date 以前已经走过的交易日收益；当前交易日收益会在函数末尾
  写入缓存，供下一次调用使用，不会提前使用未来收益。
- 和另一个 long-only 样例一样，本策略会在每个行业里加入 0 分 anchor，
  让平台的行业中性化保留行业内相对分差。

这个文件是教学样例，不是投资建议。
"""

from math import isfinite

import numpy as np
import pandas as pd


SMALL_CAP_WEIGHT = 0.70
LONG_REVERSAL_WEIGHT = 0.30
LONGS_PER_INDUSTRY = 1
ANCHORS_PER_INDUSTRY = 12

_PAST_RETURN_SUM_BY_CODE = {}
_LAST_DATE = None


def generate_signals(data, date):
    """返回 long-only 模式下的小市值 + 长期反转候选股票。"""
    global _LAST_DATE

    current_date = pd.Timestamp(date).normalize()
    if _LAST_DATE is not None and current_date <= _LAST_DATE:
        _PAST_RETURN_SUM_BY_CODE.clear()
    _LAST_DATE = current_date

    # 1. 读取当天股票池、市值和当天收益。
    #    注意：当天收益不直接进入今天的反转分数，而是在函数末尾写入缓存，
    #    从下一次交易日开始才会影响 score。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dsmvosd", "dsmvtll"],
        numeric_columns=["dretwd", "dsmvosd", "dsmvtll"],
    )

    rows = pd.DataFrame({"code": today["stkcd"].map(_code_for_merge)})
    market_cap = today["dsmvosd"].fillna(today["dsmvtll"])

    # 2. 小市值分数：市值越小，分数越高。
    small_score = _zscore(-np.log1p(market_cap.where(market_cap > 0)))

    # 3. 长期反转分数：过去累计收益越低，分数越高。
    #    第一次看到某只股票时，历史累计收益默认为 0。
    past_return_sum = rows["code"].map(_PAST_RETURN_SUM_BY_CODE).fillna(0.0)
    reversal_score = _zscore(-past_return_sum)

    # 4. 合成 long-only 因子。这里小市值是主因子，长期反转是辅助。
    rows["base_score"] = (
        SMALL_CAP_WEIGHT * small_score
        + LONG_REVERSAL_WEIGHT * reversal_score
    )
    rows = _attach_industry(data, rows)

    shaped = _select_with_anchors(
        rows,
        score_column="base_score",
        anchors_per_industry=ANCHORS_PER_INDUSTRY,
    )

    # 5. 更新历史收益缓存，供下一次 generate_signals 调用使用。
    _update_past_returns(rows["code"], today["dretwd"])

    return pd.Series(shaped["score"].values, index=shaped["code"])


def _attach_industry(data, rows):
    industry = data.latest(
        "basic.STK_INDUSTRYCLASS",
        by="Symbol",
        columns=["Symbol", "IndustryName"],
    )
    industry = pd.DataFrame(
        {
            "code": industry["Symbol"].map(_code_for_merge),
            "industry": industry["IndustryName"],
        }
    ).dropna(subset=["industry"])
    return rows.merge(industry, on="code", how="left")


def _select_with_anchors(rows, *, score_column, anchors_per_industry):
    usable = rows.dropna(subset=["industry", score_column]).copy()
    if usable.empty:
        return pd.DataFrame(columns=["code", "score"])

    grouped = usable.groupby("industry", sort=False)[score_column]
    group_size = grouped.transform("size")
    high_rank = grouped.rank(method="first", ascending=False)
    low_rank = grouped.rank(method="first", ascending=True)

    has_anchor_room = group_size > LONGS_PER_INDUSTRY
    is_long = has_anchor_room & (high_rank <= LONGS_PER_INDUSTRY)
    is_anchor = has_anchor_room & ~is_long & (low_rank <= anchors_per_industry)
    selected = usable.loc[is_long | is_anchor, ["code", score_column]].copy()
    if selected.empty:
        return pd.DataFrame(columns=["code", "score"])

    # long 的分数略带 base_score 强弱，方便平台 top-k 在行业之间继续排序。
    selected["score"] = 0.0
    selected_is_long = is_long.loc[selected.index]
    selected.loc[selected_is_long, "score"] = (
        1.0 + selected.loc[selected_is_long, score_column].clip(-3.0, 3.0) / 10.0
    )
    return (
        selected.loc[:, ["code", "score"]]
        .drop_duplicates(subset=["code"], keep="first")
        .reset_index(drop=True)
    )


def _update_past_returns(codes, returns):
    cleaned_returns = pd.to_numeric(returns, errors="coerce")
    for code, value in zip(codes, cleaned_returns):
        if not isfinite(value):
            continue
        _PAST_RETURN_SUM_BY_CODE[code] = (
            _PAST_RETURN_SUM_BY_CODE.get(code, 0.0) + float(value)
        )


def _zscore(values):
    """把当天横截面因子转成标准分，方便不同因子相加。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


def _code_for_merge(value):
    """只用于本策略内部合并：把 1、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]
