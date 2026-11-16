import numpy as np
import pandas as pd

PATH = "new_data/distribute/stock/daily_returns.parquet"
STOCKS = ["000001", "000002", "600000"]

df = pd.read_parquet(
    PATH,
    columns=["stkcd", "trddt", "dretwd"],
    filters=[("stkcd", "in", STOCKS)],
)

df["stkcd"] = df["stkcd"].astype(str).str.zfill(6)
df["trddt"] = pd.to_datetime(df["trddt"])
df["dretwd"] = pd.to_numeric(df["dretwd"], errors="coerce")

df = df.dropna(subset=["dretwd"]).sort_values(["stkcd", "trddt"])

def calc_metrics(returns: pd.Series) -> pd.Series:
    returns = returns.dropna()

    # Sharpe: annualized daily-return Sharpe, 252 trading days.
    sharpe = np.sqrt(252) * returns.mean() / returns.std(ddof=1)

    # Stock price/equity path from daily returns, compounded.
    equity = (1 + returns).cumprod()

    drawdown = equity / equity.cummax() - 1
    max_drawdown = abs(drawdown.min())

    total_return = equity.iloc[-1] - 1
    annual_return = (1 + total_return) ** (252 / len(returns)) - 1

    return pd.Series({
        "days": len(returns),
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    })

metrics_by_stock = df.groupby("stkcd")["dretwd"].apply(calc_metrics).unstack()
print(metrics_by_stock)