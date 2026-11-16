"""业绩预告动量策略。

策略想法：
- 已发布的业绩预告越积极，score 越高。
- 净利润增速预告越高，score 越高。
- 再加入一点当天市场表现，避免只看公告文本。
"""

import numpy as np
import pandas as pd


FORECAST_TYPE_SCORE = {
    "大增": 2.0,
    "扭亏": 1.5,
    "略增": 0.8,
    "续盈": 0.4,
    "不确定": 0.0,
    "略降": -0.8,
    "续亏": -1.2,
    "转亏": -1.5,
    "大降": -2.0,
}


def generate_signals(data, date):
    """合并当天行情和截至当天已经公开的最新业绩预告。"""
    # 1. 读当天行情，确定今天要给哪些股票打分。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 读最新预告。latest 会自动过滤 date 之后的公告，防止偷看未来。
    forecast_score = _latest_forecast_score(data, today["stkcd"]).reset_index(drop=True)

    # 3. 算市场确认因子：当天收益越高，给一点加分。
    market_score = _zscore(today["dretwd"]).reset_index(drop=True)

    # 4. 合成 score：业绩预告为主，市场确认很轻。
    score = 0.80 * _zscore(forecast_score) + 0.20 * market_score

    # 5. 返回 Series。index 用原始 stkcd，平台会自动整理股票代码。
    return pd.Series(score.values, index=today["stkcd"])


def _latest_forecast_score(data, stock_codes):
    """给当天股票池匹配最新预告分数。

    这里写 _code_for_merge 只是为了 pandas merge 对齐，不是学生策略的必备格式。
    """
    base = pd.DataFrame({"code": stock_codes.map(_code_for_merge)})
    try:
        latest = data.latest(
            "BF_FORECAST",
            by="Stkcd",
            columns=[
                "Stkcd",
                "ForecFinReportType",
                "RatNetProfPareComp_Hig",
                "RatNetProfPareComp_Low",
            ],
            numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
        )
    except KeyError:
        return pd.Series(0.0, index=base.index)

    if latest.empty:
        return pd.Series(0.0, index=base.index)

    # 预告类型转成分数；净利润增速上下限取平均值。
    type_score = latest["ForecFinReportType"].map(FORECAST_TYPE_SCORE).fillna(0.0)
    high = latest["RatNetProfPareComp_Hig"]
    low = latest["RatNetProfPareComp_Low"]
    growth_score = ((high + low) / 2.0).clip(lower=-100.0, upper=200.0) / 100.0

    scored = pd.DataFrame(
        {
            "code": latest["Stkcd"].map(_code_for_merge),
            "forecast_score": type_score + growth_score.fillna(0.0),
        }
    )
    scored = scored.groupby("code", as_index=False)["forecast_score"].last()

    merged = base.merge(scored, on="code", how="left")
    return merged["forecast_score"].fillna(0.0)


def _code_for_merge(value):
    """只用于本策略内部合并：把 1、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]


def _zscore(values):
    """把一列因子变成当天横截面标准分。"""
    numeric = values.replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)
