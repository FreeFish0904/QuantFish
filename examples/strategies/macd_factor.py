"""简单 MACD 趋势策略。

策略想法：
- MACD 用短期均线和长期均线的差来观察趋势。
- 短期趋势强于长期趋势，score 越高。
- 这个样例比前几个长一些，因为它需要读取历史价格。
"""

import numpy as np
import pandas as pd


FAST_SPAN = 12
SLOW_SPAN = 26
SIGNAL_SPAN = 9
MIN_PRICE_DAYS = SLOW_SPAN + SIGNAL_SPAN - 1
LOOKBACK_DAYS = 90


def generate_signals(data, date):
    """用过去一段时间的收盘价计算 MACD 分数。"""
    # 1. 读当天股票池。最终只给今天有行情的股票输出信号。
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "clsprc", "dnvaltrd"],
        numeric_columns=["clsprc", "dnvaltrd"],
    )
    if today.empty:
        return pd.Series(dtype=float)

    # 2. 读历史行情。history 自动限制到当前 date，不会读到未来。
    history = data.history(
        "stock.daily_returns",
        lookback_days=LOOKBACK_DAYS,
        columns=["stkcd", "trddt", "clsprc", "dnvaltrd"],
        numeric_columns=["clsprc", "dnvaltrd"],
    )
    if history.empty:
        return pd.Series(0.0, index=today["stkcd"])

    # 3. 整理历史数据。这里的 code 只用于按股票分组和 merge。
    rows = pd.DataFrame(
        {
            "code": history["stkcd"].map(_code_for_merge),
            "date": pd.to_datetime(history["trddt"], errors="coerce"),
            "close": history["clsprc"],
            "amount": history["dnvaltrd"],
        }
    )
    rows = rows.dropna(subset=["date", "close"]).sort_values(["code", "date"])

    # 4. 每只股票单独计算 MACD，再合并回今天股票池。
    macd = _macd_by_stock(rows)
    base = pd.DataFrame(
        {
            "code": today["stkcd"].map(_code_for_merge),
            "raw_code": today["stkcd"],
        }
    )
    factors = base.merge(macd, on="code", how="left").fillna(0.0)

    # 5. 合成 score：
    #    macd_level 表示趋势强弱；macd_slope 表示趋势是否继续改善；
    #    liquidity 只给一点点加分，偏向更容易成交的股票。
    score = (
        0.70 * _zscore(factors["macd_level"])
        + 0.20 * _zscore(factors["macd_slope"])
        + 0.10 * _zscore(factors["liquidity"])
    )

    # 6. 返回 Series。index 使用原始股票代码，让平台统一做最终规范化。
    return pd.Series(score.values, index=factors["raw_code"])


def _macd_by_stock(rows):
    """按股票计算 MACD 相关因子。"""
    scored = []
    for code, stock in rows.groupby("code", sort=False):
        close = stock["close"].astype(float)
        if close.notna().sum() < MIN_PRICE_DAYS:
            scored.append(_neutral_row(code))
            continue

        # EMA 是指数移动平均：越新的价格权重越高。
        ema_fast = close.ewm(span=FAST_SPAN, adjust=False, min_periods=FAST_SPAN).mean()
        ema_slow = close.ewm(span=SLOW_SPAN, adjust=False, min_periods=SLOW_SPAN).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=SIGNAL_SPAN, adjust=False, min_periods=SIGNAL_SPAN).mean()
        macd_hist = dif - dea

        # 用最后收盘价缩放，避免高价股和低价股因价格单位不同而不可比。
        last_close = close.iloc[-1]
        scale = abs(last_close) if np.isfinite(last_close) and last_close != 0 else 1.0
        macd_level = _last_number(macd_hist) / scale
        macd_slope = (dif.iloc[-1] - dif.iloc[-4]) / scale if len(dif) >= 4 else 0.0
        liquidity = np.log1p(stock["amount"].tail(5).mean(skipna=True))

        scored.append(
            {
                "code": code,
                "macd_level": macd_level,
                "macd_slope": macd_slope,
                "liquidity": liquidity,
            }
        )

    return pd.DataFrame(scored, columns=["code", "macd_level", "macd_slope", "liquidity"])


def _neutral_row(code):
    """历史价格不足时，给这只股票中性分。"""
    return {"code": code, "macd_level": 0.0, "macd_slope": 0.0, "liquidity": 0.0}


def _last_number(values):
    """取最后一个有效数字；如果没有有效数字，就返回 0。"""
    cleaned = values.replace([np.inf, -np.inf], np.nan)
    cleaned = cleaned.dropna()
    if cleaned.empty:
        return 0.0
    return float(cleaned.iloc[-1])


def _code_for_merge(value):
    """只用于本策略内部 merge：把 1、1.0、000001 对齐成 000001。"""
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
