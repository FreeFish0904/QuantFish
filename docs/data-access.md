# Date-Aware CSMAR Data Access

QuantFish keeps the raw CSMAR-style files intact. The release builder copies the original folder structure, filters dated tables into a learning or hidden-test window, repairs known malformed CSMAR CSV text fields, and writes a `data_catalog.json` next to the released files.

Some source tables contain long prose fields with broken quotes or commas, which can make plain `pd.read_csv()` fail on raw source files. Generated releases rewrite those rows as valid CSV while preserving original file names and column names.

Datago sentiment/search tables under `teacher/behavioral_finance/datago` follow the same release shape. The scanner treats `pub_date` / `Pub_Date` as the primary as-of date, `stock_id` / `Stock_Id` as stock-code columns when present, preserves the vendor `.xlsx` field dictionaries, and streams Datago CSV filtering in chunks because the raw files are large.

## Build Releases

```bash
cd "/Users/promcrdog/Documents/Vector lab/Qclass/platform6"
conda activate QuantFish
python -m pip install -e .

python -m quantfish.data.releases build-from-config --config config/platform.yaml
```

The default `config/platform.yaml` reads from `new_data` and writes five independent releases: the complete `learning` range (2010-01-02 through 2022-12-31), `learning_1` (2010-01-02 through 2015-12-31), `learning_2` (2015-01-01 through 2020-12-31), `learning_3` (2020-01-01 through 2022-12-31), and `hidden_test` (2023-01-01 through 2025-12-31). The historical windows are evaluation slices, not a disjoint partition: 2015 and 2020 intentionally occur in adjacent windows.

Use repeatable `--release` arguments when only selected outputs need to be created or refreshed. This leaves every unselected release untouched:

```bash
python -m quantfish.data.releases build-from-config --config config/platform.yaml \
  --release learning_1 --release learning_2 --release learning_3
```

`data_releases/` is ignored by Git. Do not commit generated releases. Hand out `data_releases/learning` to students; do not hand out raw `new_data` unless you intentionally want them to deal with source-vendor CSV defects.

## Student Access Pattern

```python
from quantfish.data import DataBundle

bundle = DataBundle("data_releases/learning")
data = bundle.at("2022-06-30")

forecast = data.load("BF_FORECAST")
latest_forecast = data.latest("BF_FORECAST", by="Stkcd")
```

`data.load()` automatically caps dated tables at the bound date. A request for rows after the bound date raises `FutureDataAccessError`.

Raw pandas access works on generated releases because they preserve the original file names and columns while repairing malformed CSV rows:

```python
import pandas as pd

forecast = pd.read_csv(
    "data_releases/learning/teacher/financial_supplement/forecast_vs_report/BF_FORECAST.csv"
)
```

## Backtest Data Contract

The hidden-test backtest runner expects the release to contain the same CSMAR-shaped datasets and columns as the student learning release. For official pricing it loads `stock.daily_returns` and `factor_benchmark.adj_factor`, computes VWAP from `dnvaltrd / dnshrtrd`, applies `cumulatefwardfactor`, and uses front-adjusted VWAP-to-close returns. Keep original CSMAR names intact; friendly dataset IDs and table-code aliases live in `data_catalog.json`.
