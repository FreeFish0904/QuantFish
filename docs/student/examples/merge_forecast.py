# merge_forecast.py
# 进阶积木：把“最新业绩预告”合并到“当天股票池”上。
#
# 注意：
# - 平台最终会自动整理你返回的股票代码；
# - 这里仍然写 _code_for_merge，是因为 pandas merge 需要两张表的 code 格式一致。

import pandas as pd


def merge_latest_forecast(data, daily_df):
    """返回每只当天股票的业绩预告分数。

    data:
        generate_signals(data, date) 里的日期绑定视图。
    daily_df:
        当天日行情，通常来自 data.current("stock.daily_returns", ...)。
    返回:
        DataFrame，包含 code 和 forecast_score 两列。
        没有预告的股票给 0 分，而不是直接丢掉。
    """
    if daily_df.empty:
        return pd.DataFrame({"code": [], "forecast_score": []})

    # 先用当天日行情确定股票池。策略只给当天有行情的股票打分。
    base = pd.DataFrame({"code": daily_df["stkcd"].map(_code_for_merge)})

    try:
        # latest 会自动过滤当前日期之后的预告，避免偷看未来。
        latest = data.latest(
            "BF_FORECAST",
            by="Stkcd",
            columns=[
                "Stkcd",
                "RatNetProfPareComp_Hig",
                "RatNetProfPareComp_Low",
            ],
            numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
        )
    except KeyError:
        # 有些练习数据没有业绩预告表；这时给所有股票中性分。
        return base.assign(forecast_score=0.0)

    if latest.empty:
        return base.assign(forecast_score=0.0)

    # 业绩预告净利润增速通常给上下限，这里取平均值作为一个简单分数。
    high = latest["RatNetProfPareComp_Hig"]
    low = latest["RatNetProfPareComp_Low"]
    forecast_score = ((high + low) / 2.0).clip(lower=-100.0, upper=200.0) / 100.0

    forecast = pd.DataFrame(
        {
            "code": latest["Stkcd"].map(_code_for_merge),
            "forecast_score": forecast_score.fillna(0.0),
        }
    )

    # 同一股票如果仍有多条记录，就保留最后一条。
    forecast = forecast.groupby("code", as_index=False)["forecast_score"].last()

    merged = base.merge(forecast, on="code", how="left")
    merged["forecast_score"] = merged["forecast_score"].fillna(0.0)
    return merged


def _code_for_merge(value):
    """只用于本文件内部 merge：把 1、1.0、000001 对齐成 000001。"""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code.zfill(6)[-6:]


if __name__ == "__main__":
    # 下面只是本地演示数据，不是正式策略。
    class MockData:
        def latest(self, dataset, by=None, columns=None, numeric_columns=None):
            return pd.DataFrame(
                {
                    "Stkcd": ["000001", "000002"],
                    "RatNetProfPareComp_Hig": [50.0, 10.0],
                    "RatNetProfPareComp_Low": [30.0, 5.0],
                }
            )

    daily = pd.DataFrame({"stkcd": ["000001", "000002", "000003"]})
    print(merge_latest_forecast(MockData(), daily))
