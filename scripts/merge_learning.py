#!/usr/bin/env python3
"""Merge learning_1/2/3 daily_returns.parquet into a single learning release."""

import json
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
from pathlib import Path

BASE = Path("data_releases")
OUTPUT = BASE / "learning" / "stock"

SOURCES = [
    BASE / "learning_1" / "stock" / "daily_returns.parquet",
    BASE / "learning_2" / "stock" / "daily_returns.parquet",
    BASE / "learning_3" / "stock" / "daily_returns.parquet",
]

print("Reading source files...")
frames = []
for p in SOURCES:
    print(f"  Reading {p} ({p.stat().st_size / 1024 / 1024:.0f} MB)...")
    df = pd.read_parquet(p)
    print(f"    {len(df)} rows, dates: {df['trddt'].min()} to {df['trddt'].max()}")
    frames.append(df)

print("\nConcatenating...")
merged = pd.concat(frames, ignore_index=True)
print(f"  Before dedup: {len(merged)} rows")

print("Deduplicating on (stkcd, trddt)...")
merged = merged.drop_duplicates(subset=["stkcd", "trddt"], keep="first")
print(f"  After dedup: {len(merged)} rows")

print("Sorting by trddt, stkcd...")
merged = merged.sort_values(["trddt", "stkcd"], ignore_index=True)

# Convert trddt to datetime64[us] to match existing schema
merged["trddt"] = pd.to_datetime(merged["trddt"])

print(f"\nFinal data: {len(merged)} rows")
print(f"  Date range: {merged['trddt'].min()} to {merged['trddt'].max()}")
print(f"  Unique stocks: {merged['stkcd'].nunique()}")
print(f"  Unique dates: {merged['trddt'].nunique()}")

OUTPUT.mkdir(parents=True, exist_ok=True)
output_path = OUTPUT / "daily_returns.parquet"
print(f"\nWriting to {output_path}...")
merged.to_parquet(output_path, index=False)
print(f"  Written: {output_path.stat().st_size / 1024 / 1024:.0f} MB")

# Update the data_catalog.json with correct row count
catalog_path = BASE / "learning" / "data_catalog.json"
print(f"\nUpdating catalog: {catalog_path}")
with open(catalog_path) as f:
    catalog = json.load(f)

for ds in catalog["datasets"]:
    if ds["dataset_id"] == "stock.daily_returns":
        ds["row_count"] = len(merged)
        ds["source_row_count"] = sum(
            int(pq.ParquetFile(str(p)).metadata.num_rows) for p in SOURCES
        )
        print(f"  Updated stock.daily_returns row_count: {ds['row_count']}")
        print(f"  Updated stock.daily_returns source_row_count: {ds['source_row_count']}")

with open(catalog_path, "w") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("\nDone!")