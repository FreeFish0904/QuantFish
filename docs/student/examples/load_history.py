# load_history.py
# 演示 data.history：读取当前日期之前的一段历史数据。
#
# 当策略需要“过去 N 天”的价格或收益时，会用到这个接口。

from quantfish.data import DataBundle


# 1. 打开学习数据包。
bundle = DataBundle("data_releases/learning")

# 2. 绑定到一个具体日期。
#    后面的 history 只能读到这个日期为止。
data = bundle.at("2022-06-30")

# 3. 读取过去 60 个自然日的日行情。
#    注意：60 个自然日包含周末和节假日，所以实际交易日数量会少一些。
#    numeric_columns 让平台把价格和收益转成数字，脏值会自动变成 NaN。
history = data.history(
    "stock.daily_returns",
    lookback_days=60,
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)

# 4. 看看这段历史实际覆盖了哪些交易日。
print("历史数据从", history["trddt"].min(), "到", history["trddt"].max())
print("总行数:", len(history))
print(history.head())
