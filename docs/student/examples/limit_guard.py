# limit_guard.py
# 进阶积木：在“信号层”主动把交易受限股票的分数设为 0。
#
# 入门策略不需要复制这个文件。
# QuantFish 回测执行层已经会处理涨跌停、不可交易和流动性限制。
# 这个 helper 只是给想提前把信号变得更保守的同学使用。

import pandas as pd


def drop_blocked_scores(scores, daily_df, limit_col="limitstatus"):
    """把交易受限股票的 score 设为 0。

    scores:
        DataFrame，至少包含 score 列，并且行顺序要和 daily_df 对齐。
    daily_df:
        当天日行情，通常来自 data.current(..., numeric_columns=["limitstatus"])。
    limit_col:
        交易限制列名。默认使用学习数据里的 limitstatus。
    """
    if limit_col not in daily_df.columns:
        # 如果数据里没有限制列，就原样返回，避免 helper 影响主策略运行。
        return scores.copy()

    result = scores.copy()
    blocked = daily_df[limit_col].ne(0)
    result.loc[blocked.to_numpy(), "score"] = 0.0
    return result


if __name__ == "__main__":
    # 下面只是本地演示数据，不是正式策略。
    scores = pd.DataFrame({"score": [1.5, -0.5, 2.0]})
    daily = pd.DataFrame({"limitstatus": [0, 1, 0]})

    print("过滤前：")
    print(scores)
    print("\n过滤后（limitstatus != 0 的分数变 0）：")
    print(drop_blocked_scores(scores, daily))
