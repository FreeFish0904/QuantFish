# load_latest.py
# 演示 data.latest：每只股票取“截至当前日期最新的一条记录”。
#
# 业绩预告、财报、股东数据不一定每天都有。
# 如果你想在某个交易日知道“这只股票目前最新公开的信息”，就用 latest。

from quantfish.data import DataBundle


# 1. 打开学习数据包，并绑定日期。
bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

# 2. 对每只股票，取 2022-06-30 及以前最新发布的一条业绩预告。
#    by="Stkcd" 表示按股票代码分组。
#    numeric_columns 让平台把预告上下限转成数字，异常文本和空值会变成 NaN。
latest = data.latest(
    "BF_FORECAST",
    by="Stkcd",
    columns=[
        "Stkcd",
        "PubliDate",
        "ForecFinReportType",
        "RatNetProfPareComp_Hig",
        "RatNetProfPareComp_Low",
    ],
    numeric_columns=["RatNetProfPareComp_Hig", "RatNetProfPareComp_Low"],
)

# 3. 打印结果。
#    如果某只股票在这个日期之前没有预告，就不会出现在 latest 里。
print("共有", len(latest), "只股票在 2022-06-30 之前有最新预告")
print(latest.head())
