# QuantFish 术语表

| 术语 | 解释 |
|---|---|
| `generate_signals` | 策略函数，平台在每个交易日调用它，用来生成当天每只股票的分数。 |
| `DataBundle` | 数据包对象，指向一个数据发布目录，负责加载各种数据集。 |
| `DatedDataBundle` | 日期绑定视图，只能看到某个交易日及之前的数据，防止策略偷看未来。 |
| `FutureDataAccessError` | 未来数据访问错误，当策略试图读取当前交易日之后的数据时会报这个错。 |
| `front_vwap` | 官方执行价，平台用来模拟下单成交的价格。 |
| `front_close` | 官方收盘价/结算价，平台用来计算当天持仓市值的价格。 |
| stock code | 六位股票代码，例如 `000001`；平台会自动把不同格式的代码统一成六位字符串。 |
| `market type` / `markettype` | 市场类型标签。平台默认使用 `[1, 4, 16, 32, 64]`，覆盖沪深主板、创业板、科创板和北交所 A 股。详见 [数据包接口](./02-data-bundle-api.md)。 |
| score | 信号分数，策略函数返回的数值，越高表示越看好这只股票。 |
| weight | 权重，平台根据分数为每只股票分配的资金比例。 |
| turnover | 换手率，衡量一段时间内组合持仓发生了多大比例的交易。 |
| Sharpe | 夏普比率，衡量每承担一单位风险能获得多少超额收益。 |
| max drawdown | 最大回撤，组合净值从最高点回落到最低点的最大跌幅。 |
| `information ratio` / `information_ratio` | 信息比率，只做多模式下等于 `年化主动收益 / 跟踪误差`，衡量单位主动风险带来的主动收益。 |
| `tracking error` / `tracking_error` | 跟踪误差，只做多模式下主动收益日标准差的年化值。 |
| `risk_free_rate` / `risk_free_return` | 无风险收益。只做多模式默认使用年化 `1.75%`，日度值为 `risk_free_rate / 252`，用于计算超额收益、beta 和原始夏普。 |
| `execution.long_only` | 回测模式开关，`false` 表示多空模式，`true` 表示只做多模式。 |
| `long_only_weighting` | 只做多权重算法。默认 `rank_equal` 会让入选且分数为正的股票等权；`score_proportional` 会按正分比例分配；0 分和负分都不会买。 |
| `long_only_target_count` | 只做多模式最多买入多少只股票，是硬上限；同分时按平台原始顺序先到先得。 |
| `max_position_weight` | 只做多配置项（默认 `0.05`），单只股票在组合中的权重上限。超额会优先分配给其他已入选且仍有容量的股票。详见 [回测与评价指标](./06-backtest-and-metrics.md)。 |
| `min_listing_days` | 只做多配置项（默认 `60`），股票上市天数不足该值时会被排除在可投资范围外。详见 [回测与评价指标](./06-backtest-and-metrics.md)。 |
| `sell_stamp_duty_rate` | A 股卖出印花税假设，只按卖出换手率扣除；当前课堂配置为 `0.0005`。 |
| `terminal_stale_position_policy` | 评分末日仍有无法定价持仓时的处理规则。历史学习轨道使用 `carry`，按最后有效收盘价保留并披露；`hidden_test` 使用 `reject`，末日仍无有效收盘价会拒绝结果。 |
| `top_k` | 多空模式每边最多选多少只股票，是硬上限；`null` 表示不限制。 |
| `max_participation_rate` | 单只股票单日最多参与其成交金额的比例，默认 `0.10`；流动性上限公式是 `max_daily_change = max_participation_rate * dnvaltrd / capital`。 |
| `group_count` | 分组数，平台把股票按分数分成多少组来测试单调性。 |
| `industry_neutralization` / 行业中性化 | 平台级回测开关（默认开启）。开启后，平台会按同一天、同一行业扣掉平均 `score`，让仓位更少依赖行业整体偏高或偏低；缺少行业分类的股票会被设为 0 分。详见 [回测引擎揭秘](./11-backtest-engine-explained.md)。 |
| `trdsta` / `TradingStatus` | 交易状态数据字段，学生可以读取分析；平台执行层不会单独用它禁止交易。 |
| `limitstatus` | 涨跌停状态字段，非 0 通常表示股票当天交易受限。 |
| `limit_status` | `limitstatus` 的同义字段名。正值表示涨停方向受限，负值表示跌停方向受限；只做多执行中分别阻止涨停买入和跌停卖出。 |
| `numeric_columns` | 数据加载参数，用于把指定列自动强制转换为数值类型，避免手动 `pd.to_numeric`。 |
| `data_track` / 数据轨道 | 数据发布与提交的运行轨道，决定运行使用 `hidden_test`、完整 `learning`，还是 `learning_1` / `learning_2` / `learning_3` 历史窗口。 |
| `hidden_test` / hidden_test 轨道 | 正式/排行榜轨道，提交到此轨道的成绩会进入排行榜并参与排名。 |
| `learning` / learning 轨道 | 练习轨道，提交结果可在历史、compare 和该轨道的诊断榜单中查看，但不计入以 `hidden_test` 为准的正式排名。 |
| `learning_1` / `learning_2` / `learning_3` | 历史练习窗口，分别覆盖 2010–2015、2015–2020、2020–2022；用于比较策略跨时期稳定性。 |
| `stale` / 已失效运行 | 当设置、指纹、执行引擎或数据集发生变更后，已完成的运行会被标记为失效；stale 运行不能参与 compare，也不能获得排行榜徽章，需要重新提交恢复有效。 |
| `cumulatefwardfactor` | 前复权累计因子，用来把历史价格调整到可比较的前复权价格。 |
| `CSV` | 逗号分隔值（Comma-Separated Values），一种用逗号分隔的表格文本文件，可用 Excel、WPS 直接打开。 |
| `JSON` | JavaScript Object Notation，一种轻量级文本格式，常用来保存配置和图表数据。 |
| `Parquet` | 一种压缩的列式表格存储格式，适合用 Python pandas 读取，Excel 默认打不开。 |
| `DataFrame` | pandas 里的“表格”，有行有列，类似 Excel 工作表。 |
| `Series` | pandas 里的“一列数据”，可理解成只有一列的表格。 |
| `KPI` | 关键绩效指标（Key Performance Indicator），结果页上用大数字展示的核心指标。 |
| `composite score` | 综合评分，平台把收益、夏普、回撤、换手率和空头收益等指标加权后算出的总得分，用于排行榜排名。详见 [在网页端提交](./08-submitting-on-web.md)。 |
| `annualized_short_profit` | 年化空头收益。综合评分里它是一个惩罚项（默认权重 100），主要用于约束多空策略中的空头获利；只做多策略通常可忽略。详见 [在网页端提交](./08-submitting-on-web.md)。 |
| `raw_total_return` / `raw_*` | 只做多模式下输出的原始组合指标，未扣除 beta 影响。与 `active_*` / `information_ratio` 对比使用。详见 [回测与评价指标](./06-backtest-and-metrics.md)。 |
| `average_year_return` | 各自然年收益的平均值。 |
| `worst_year_return` | 所有自然年收益中最差的那一年。 |
| `calmar` | Calmar 比率，等于 `annual_return / max_drawdown`。没有回撤时该值为空。 |
| `fitness` | 综合 fitness 指标，综合考虑夏普、年化收益和换手率。 |
| `alpha` | 超额收益曲线。多空模式下等于策略累计收益减基准累计收益；只做多模式下基于 beta 调整后的主动收益，衡量剔除大盘 beta 后的超额能力。 |
| `active return` / `active_return` | 主动收益。在只做多（long-only）模式下，平台用 `(portfolio_return - risk_free_return) - beta × (benchmark_return - risk_free_return)` 计算每日主动收益，并据此计算评分期指标。详见 [回测与评价指标](./06-backtest-and-metrics.md) 与 [回测引擎揭秘](./11-backtest-engine-explained.md)。 |
| `benchmark` | 基准，通常指沪深 300 等市场指数，用来和策略对比。 |
| `beta` | 贝塔，策略超额收益相对于基准超额收益（默认沪深 300）的回归系数。只做多模式下用它计算主动收益。 |
| `equity` | 累计收益指数，平台里等于 `1 + daily_return.cumsum()`。 |
| `drawdown` | 回撤，累计收益曲线从最高点下跌的幅度。 |
| `long / short` | 做多/做空。做多是买入期待上涨，做空是看跌并先借券卖出。 |
| `leverage` | 杠杆，借钱投资的比例。杠杆越高，收益和亏损都会被放大。 |
| `slippage` | 滑点，实际成交价比理想价格多付出的成本。 |
| `commission` | 佣金/手续费，交易时支付给券商的费用。 |
| `VWAP` | 成交量加权平均价（Volume Weighted Average Price），平台用 `front_vwap` 作为官方执行价。 |
| `Warmup 期` | 热身期，从 `data_start` 到 `scoring_start` 之前，建仓预热但不算成绩。 |
| `Scoring 期` | 评分期，从 `scoring_start` 到 `scoring_end`，收益和指标才会计入成绩。 |
