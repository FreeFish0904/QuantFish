# `data/` — generated datasets

Nothing in this folder is tracked by git. It exists so that the demo and local
experiments share one predictable location.

```text
data/
  sample/
    raw/        CSMAR-style source tables written by scripts/gen_sample_dataset.py
    releases/   learning / learning_1..3 / hidden_test releases built from raw/
```

Generate it with:

```bash
python scripts/gen_sample_dataset.py --config config/platform.demo.yaml
```

Output layout (about 11 MB):

```text
data/sample/raw/
  distribute/stock/daily_returns.parquet     stkcd, trddt, dretwd, opnprc, hiprc, loprc, clsprc, dnshrtrd, dnvaltrd, markettype
  teacher/factor_benchmark/adj_factor.parquet tradingdate, stkcd, cumulatefwardfactor
  distribute/market/index_daily.csv           indexcd, idxtrd01, idxtrd05, idxtrd08, idxtrd09
  distribute/basic/STK_INDUSTRYCLASS.csv      ImplementDate, stkcd, IndustryName
  distribute/basic/company_info.csv           stkcd, listdt, statdt
```

The real classroom deployment points `data_releases.raw_data_root` at a licensed
CSMAR-style export instead; `scan_catalog` detects the layout automatically.
