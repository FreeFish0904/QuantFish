"""Long-only 小市值行业锚点策略。

策略想法：
- 只做多模式下，平台会先做行业中性化，再从正分股票里选股。
- 如果一个行业里只返回高分股票，行业中性化会把这些分数压到接近 0。
- 所以本策略在每个行业里选 1 只最小市值股票做 long candidate，
  再选若干只大市值股票作为 0 分 anchor，帮助平台保留行业内相对分差。

这个文件是教学样例，不是投资建议。
"""

import numpy as np
import pandas as pd


LONGS_PER_INDUSTRY = 1
ANCHORS_PER_INDUSTRY = 8


def generate_signals(data, date):
    """为 long-only 模式返回行业内小市值候选股票和锚点股票。"""
    # 1. 读取当天股票池和市值字段。
    #    dsmvosd 是流通市值；如果缺失，用 dsmvtll 总市值补一下。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dsmvosd", "dsmvtll"],
        numeric_columns=["dsmvosd", "dsmvtll"],
    )

    rows = pd.DataFrame({"code": today["stkcd"].map(_code_for_merge)})
    market_cap = today["dsmvosd"].fillna(today["dsmvtll"])

    # 2. 小市值因子：市值越小，small_score 越高。
    rows["small_score"] = _zscore(-np.log1p(market_cap.where(market_cap > 0)))

    # 3. 读取截至今天已经生效的行业分类。
    #    latest 会被平台限制在 date 及以前，不会读取未来行业变化。
    rows = _attach_industry(data, rows)

    # 4. 在每个行业里选 1 个 long candidate 和若干 anchor。
    #    返回的 anchor 分数是 0；平台行业中性化后，它们通常会变成负分，
    #    因此只做多模式不会买它们，但它们能帮助 long candidate 保持正分。
    shaped = _select_with_anchors(
        rows,
        score_column="small_score",
        anchors_per_industry=ANCHORS_PER_INDUSTRY,
    )
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


def _zscore(values):
    """把当天横截面因子转成标准分，方便排序和组合。"""
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
