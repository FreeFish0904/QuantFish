# First Day Sample Strategies

这个文件夹里的每一个 `.py` 文件，都是可以直接上传到 QuantFish 平台的独立策略文件。

每个策略都定义了 `generate_signals(data, date)`，只读取当天的 `stock.daily_returns`，然后把一个简单因子直接作为 `score` 返回。平台会自动把股票代码整理成六位字符串，并根据 `score` 做排序和回测。

注意：这些是第一天入门样例，目标是帮助你看懂“从字段到因子到 score”的过程，不是投资建议。

## 策略列表

- `factor_0_vwap_close.py`：VWAP / 收盘价。成交均价相对收盘价越高，分数越高。
- `factor_1_close_position.py`：收盘位置 `(close - low) / (high - low)`。收盘越靠近日内最高价，分数越高。
- `factor_2_intraday_return.py`：日内涨幅 `close / open - 1`。从开盘到收盘涨得越多，分数越高。
- `factor_3_close_strength.py`：收盘强度 `close / high`。收盘越接近日内最高价，分数越高。
- `factor_4_overnight_gap.py`：隔夜跳空 `open / precloseprice - 1`。今天开盘相对昨日收盘跳得越高，分数越高。
- `factor_5_midprice_deviation.py`：中间价偏离 `((high + low) / 2) / close`。日内中间价相对收盘价越高，分数越高。
- `factor_6_intraday_path_length.py`：日内步长因子 `-(2 * high - 2 * low + abs(close - open)) / (close - open)`。上涨日分数偏负，下跌日分数偏正。

## 分数含义

在 QuantFish 里，`score` 越高，平台越倾向于把这只股票排在前面；`score` 越低，排名越靠后。这里没有做 z-score、行业中性化或方向反转，策略直接使用原始因子值作为分数，方便第一天学习和调试。

这些样例直接写原始公式，不需要自己写安全除法函数。如果分母是 0，最终 `score` 可能变成正负无穷；平台会在后台把无穷值整理成 `NaN`。在平台里，`NaN` 表示这只股票当天没有有效信号。
