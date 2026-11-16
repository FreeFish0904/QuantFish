# load_current.py
# 演示 data.current：只读取“绑定日期当天”的数据。
#
# 这个文件是学习数据接口的小练习，不是要提交的策略文件。

from quantfish.data import DataBundle


# 1. 创建数据包对象。它指向本地学习数据目录。
bundle = DataBundle("data_releases/learning")

# 2. 绑定日期。
#    绑定后，data 只能看到 2022-06-30 及以前的数据，不能偷看未来。
data = bundle.at("2022-06-30")

# 3. 读取当天日行情。
#    columns 只列出想看的字段：列越少，读得越快，也更容易理解。
#    numeric_columns 告诉平台把这些字段转成数字，异常文本和空值会变成 NaN。
today = data.current(
    "stock.daily_returns",
    columns=["stkcd", "trddt", "clsprc", "dretwd"],
    numeric_columns=["clsprc", "dretwd"],
)

# 4. 打印结果。
#    每一行是一只股票在 2022-06-30 当天的记录。
print("当天共有", len(today), "行数据")
print(today.head())
