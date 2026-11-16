from __future__ import annotations

import pandas as pd


def arithmetic_equity(returns: pd.Series) -> pd.Series:
    return 1.0 + pd.to_numeric(returns, errors="coerce").fillna(0.0).cumsum()


def relative_drawdown_from_equity(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)
    running_peak = equity.cummax()
    running_peak = running_peak.where(running_peak >= 1.0, 1.0)
    return equity / running_peak - 1.0
