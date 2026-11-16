import pandas as pd


def generate_signals(data, date):
    price_columns = ["opnprc", "hiprc", "loprc", "clsprc"]

    today = data.current("stock.daily_returns", numeric_columns=price_columns)

    intraday_move = today["clsprc"] - today["opnprc"]

    path_length = (
        2.0 * today["hiprc"] - 2.0 * today["loprc"] + intraday_move.abs()
    )
    score = -path_length / intraday_move

    return pd.Series(score.values, index=today["stkcd"])
