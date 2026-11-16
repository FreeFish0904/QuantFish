# full_local_run.py
# 在本地运行一次完整回测并保存结果。
#
# 这个脚本不是策略文件，不需要提交到平台。
# 它的作用是：帮你在自己的电脑上先跑一遍 hello_strategy.py，
# 看看策略能不能正常生成结果。

import sys
from dataclasses import replace as dataclass_replace

from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.platform_config import ConfigRepository


# 1. 加载平台配置。
#    config/platform.yaml 里保存了回测日期、初始资金、执行价格等设置。
config = ConfigRepository("config/platform.yaml").load()

# 2. 本地学习数据覆盖 2015-01-01 至 2022-12-31。
#    为了让刚下载数据的同学立刻看到结果，这里把评分窗口临时调到学习数据内，
#    并把 data_start 也改到评分窗口之前，避免加载 2015 年以来的全部数据。
#    这只影响本地冒烟测试，不会改变平台正式提交时的隐藏测试窗口。
new_backtest = dataclass_replace(
    config.backtest,
    data_start="2022-05-01",   # 避免从 2015-01-01 开始加载全部学习数据
    scoring_start="2022-06-01",
    scoring_end="2022-06-30",
)
config = dataclass_replace(config, backtest=new_backtest)

# 3. 运行回测。
#    第一个参数是策略文件路径。想测试自己的 strategy.py 时，改这里即可。
result = run_student_backtest(
    "docs/student/examples/hello_strategy.py",
    "data_releases/learning",
    config,
)

# 4. 把结果写入 output/student_doc_smoke。
#    里面会有 summary.csv、graph_data.json 等文件。
write_backtest_report(result, "output/student_doc_smoke")  # 这里的路径可以改成你想要的输出目录，例如 "output/my_first_run"

# 5. 在终端打印核心指标，方便快速确认策略是否跑通。
print(result.summary)

# 6. 显式退出，避免某些后台线程让终端看起来像“卡住了”。
sys.exit(0)
