import pandas as pd

def generate_signals(data, date):
    daily = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd", "dnvaltrd", "limitstatus"],
        numeric_columns=["dretwd", "dnvaltrd", "limitstatus"],
    )

    industry = data.latest(
        "basic.STK_INDUSTRYCLASS",
        by="Symbol",
        columns=["Symbol", "IndustryName"],
    )

    rows = daily.merge(
        industry,
        left_on="stkcd",
        right_on="Symbol",
        how="left",
    )

    rows = rows[rows["limitstatus"].fillna(0).eq(0)].copy()
    rows["code"] = rows["stkcd"].astype(str).str.zfill(6).str[-6:]

    # Example long idea: short-term reversal + liquidity.
    rows["long_quality"] = -rows["dretwd"] + 0.05 * rows["dnvaltrd"].rank(pct=True)

    signals = []

    for _, group in rows.dropna(subset=["IndustryName"]).groupby("IndustryName"):
        if len(group) < 4:
            continue

        long_names = group.nlargest(1, "long_quality")
        anchors = (
            group.drop(long_names.index)
            .nlargest(3, "dnvaltrd")   # liquid anchors, not necessarily "bad" stocks
        )

        signals.append(pd.DataFrame({
            "code": long_names["code"],
            "score": 1.0,
        }))
        signals.append(pd.DataFrame({
            "code": anchors["code"],
            "score": 0.0,
        }))

    if not signals:
        return pd.DataFrame(columns=["code", "score"])

    return pd.concat(signals, ignore_index=True)