# QuantFish Sample Strategies

这些样例都是可以直接上传到 QuantFish 平台的独立 Python 策略文件。每个文件都定义：

```python
def generate_signals(data, date):
    ...
```

平台会在每个交易日调用一次 `generate_signals(data, date)`。最简策略可以返回一个 `pandas.Series`：

- Series 的 index 是股票代码。
- Series 的值是当天给这只股票的 `score`。

平台会自动把股票代码整理成六位字符串。分数越高，平台越偏向做多；分数越低，平台越偏向做空。

这些策略只使用平台提供的“日期绑定”数据接口：

- `data.current(...)`
- `data.history(...)`
- `data.latest(...)`

这三个接口都会被平台限制在当前 `date` 及以前的数据范围内。回测引擎使用今天的信号，在下一个交易日执行交易，所以样例里把“今天已经收盘的日行情”当成下一次交易前已知的信息，不使用未来收益。

样例里用于计算的价格、收益率、成交额、市值、业绩预告数值都会通过 `numeric_columns=[...]` 交给平台转换。平台会把指定列里的异常文本或空值变成 `NaN`，策略代码里就可以直接用这些列做计算。

## Files

- `low_liquidity_premium.py`：低流动性溢价策略。成交金额越低，分数越高。
- `small_cap_reversal.py`：小市值 + 低流动性 + 短期反转策略。小市值、低成交金额、当天下跌的股票分数更高。
- `macd_factor.py`：简单 MACD 因子策略。用历史收盘价计算 MACD 趋势强弱，并加入少量成交金额确认。
- `price_volume_momentum.py`：价格动量 + 成交活跃度策略。当天收益越高、成交越活跃，分数越高。
- `short_term_reversal.py`：短期反转策略。当天跌得多的股票分数更高，同时稍微偏向成交更活跃的股票。
- `forecast_revision_momentum.py`：业绩预告动量策略。只使用当前日期前已经发布的最新业绩预告，再混合少量当天市场表现。
- `datago_search_attention.py`：DataGo 百度搜索关注度策略。搜索指数越高，分数越高。
- `datago_news_mention_momentum.py`：DataGo 新闻提及动量策略。过去一周被新闻高相关提及越多，分数越高。
- `datago_news_sentiment.py`：DataGo 新闻情绪策略。用 `news_id` 合并新闻情绪和股票关联表。
- `datago_guba_sentiment_heat.py`：DataGo 股吧情绪热度策略。股吧情绪越正面、讨论越活跃，分数越高。
- `longonly_small_cap_anchor.py`：只做多小市值行业锚点策略。每个行业选 1 只小市值候选股，并加入 0 分锚点，适合 `execution.long_only: true`。
- `longonly_small_reversal_anchor.py`：只做多小市值 + 长期反转行业锚点策略。在小市值基础上加入过去累计收益反转，是当前 learning track 上表现更强的 long-only 教学样例。

这些文件是教学样例，不是投资建议。它们的主要作用是展示如何写出能在平台上运行、不会偷看未来数据、结构清楚的策略。
