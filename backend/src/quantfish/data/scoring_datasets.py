from __future__ import annotations

from typing import Any

RETURNS_DATASET = "stock.daily_returns"
ADJ_FACTOR_DATASET = "factor_benchmark.adj_factor"
INDUSTRY_DATASET = "basic.STK_INDUSTRYCLASS"
COMPANY_INFO_DATASET = "basic.company_info"
HS300_DATASET = "market.index_daily"


def scoring_required_dataset_ids(config: Any) -> tuple[str, ...]:
    required = [RETURNS_DATASET, ADJ_FACTOR_DATASET]
    if bool(config.backtest.industry_neutralization):
        required.append(INDUSTRY_DATASET)
    if bool(config.execution.long_only):
        if int(config.execution.min_listing_days) > 0:
            required.append(COMPANY_INFO_DATASET)
        if str(getattr(config.backtest, "long_only_benchmark", "hs300")) == "hs300":
            required.append(HS300_DATASET)
    return tuple(required)
