from __future__ import annotations

import argparse
import logging
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from quantfish.data.bundle import _date_series, _read_dataset, _to_timestamp
from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.data.scanner import scan_catalog
from quantfish.data.scoring_datasets import (
    ADJ_FACTOR_DATASET,
    COMPANY_INFO_DATASET,
    HS300_DATASET,
    INDUSTRY_DATASET,
    RETURNS_DATASET,
)
from quantfish.platform_config import (
    ConfigRepository,
    PlatformConfig,
)
from quantfish.stock_codes import normalize_stock_code

HS300_INDEX_CODE = "000300"
CSV_RELEASE_CHUNK_SIZE = 100_000
PARQUET_RELEASE_BATCH_ROWS = 100_000
LOGGER = logging.getLogger(__name__)
CONFIGURED_RELEASE_NAMES = (
    "learning",
    "learning_1",
    "learning_2",
    "learning_3",
    "hidden_test",
)


@dataclass(frozen=True)
class ReleaseBuildProgress:
    phase: str
    percent: float
    completed_datasets: int = 0
    total_datasets: int = 0
    current_dataset: str | None = None


ReleaseProgressCallback = Callable[[ReleaseBuildProgress], None]


@dataclass(frozen=True)
class _ReleaseTarget:
    name: str | None
    output_root: Path
    start_date: pd.Timestamp | None
    end_date: pd.Timestamp | None
    metadata: dict[str, object]


@dataclass
class _PreparedReleaseTarget:
    target: _ReleaseTarget
    temp_output_root: Path
    copied_docs: set[str] = field(default_factory=set)
    released_specs: list[DatasetSpec] = field(default_factory=list)


def build_release(
    source: Path | str,
    output: Path | str,
    start: str | None = None,
    end: str | None = None,
    release_metadata: dict[str, object] | None = None,
) -> DataCatalog:
    source_root = Path(source)
    output_root = Path(output)
    _validate_release_paths(source_root, output_root)
    start_date = _to_timestamp(start) if start is not None else None
    end_date = _to_timestamp(end) if end is not None else None
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("release start cannot be after release end")
    source_catalog = scan_catalog(source_root)
    _validate_source_catalog(source_root, source_catalog)
    catalogs = _build_release_targets(
        source_root,
        source_catalog,
        [
            _ReleaseTarget(
                name=None,
                output_root=output_root,
                start_date=start_date,
                end_date=end_date,
                metadata=release_metadata or {},
            )
        ],
    )
    return catalogs[0]


def build_releases_from_config(
    config: PlatformConfig,
    release_names: Iterable[str] | None = None,
    progress_callback: ReleaseProgressCallback | None = None,
    required_dataset_ids: Iterable[str] | None = None,
) -> dict[str, DataCatalog]:
    config.validate()
    releases = config.data_releases
    windows_by_name = {
        window.name: window for window in releases.release_windows()
    }
    selected_names = _selected_release_names(release_names, windows_by_name)
    selected_windows = [windows_by_name[name] for name in selected_names]
    source_root = Path(releases.raw_data_root)
    _report_progress(progress_callback, phase="scanning", percent=0)
    source_catalog = scan_catalog(source_root)
    _validate_source_catalog(source_root, source_catalog)
    required_datasets = tuple(dict.fromkeys(required_dataset_ids or ()))
    if required_datasets or "hidden_test" in selected_names:
        _report_progress(
            progress_callback,
            phase="validating",
            percent=2,
            total_datasets=len(source_catalog.datasets),
        )
    _validate_required_source_datasets(
        source_root,
        source_catalog,
        required_datasets,
    )
    if "hidden_test" in selected_names:
        _validate_hidden_hs300_source(
            source_root,
            start_date=pd.Timestamp(releases.hidden_start),
            end_date=pd.Timestamp(releases.hidden_end),
            source_catalog=source_catalog,
        )
    base_metadata = {
        "course": config.course.name,
        "configured_learning_start": releases.learning_start.isoformat(),
        "configured_learning_end": releases.learning_end.isoformat(),
        "configured_hidden_start": releases.hidden_start.isoformat(),
        "configured_hidden_end": releases.hidden_end.isoformat(),
        "price_policy": config.backtest.price_policy,
    }
    targets = [
        _ReleaseTarget(
            name=window.name,
            output_root=Path(window.output_root),
            start_date=pd.Timestamp(window.start),
            end_date=pd.Timestamp(window.end),
            metadata={
                "release_name": window.name,
                **base_metadata,
            },
        )
        for window in selected_windows
    ]
    catalogs = _build_release_targets(
        source_root,
        source_catalog,
        targets,
        progress_callback=progress_callback,
        required_dataset_ids=required_datasets,
    )
    _report_progress(
        progress_callback,
        phase="completed",
        percent=100,
        completed_datasets=len(source_catalog.datasets),
        total_datasets=len(source_catalog.datasets),
    )
    return {
        target.name or target.output_root.name: catalog
        for target, catalog in zip(targets, catalogs, strict=True)
    }


def _selected_release_names(
    release_names: Iterable[str] | None,
    windows_by_name: dict[str, object],
) -> tuple[str, ...]:
    if release_names is None:
        return tuple(windows_by_name)
    requested = tuple(dict.fromkeys(release_names))
    if not requested:
        raise ValueError("at least one configured data release must be selected")
    unknown = [name for name in requested if name not in windows_by_name]
    if unknown:
        raise ValueError(f"unsupported configured data release: {unknown[0]}")
    return requested


def _validate_source_catalog(source_root: Path, source_catalog: DataCatalog) -> None:
    if source_catalog.datasets:
        return
    raise ValueError(
        f"no supported datasets found in source data root: {source_root}"
    )


def _validate_required_source_datasets(
    source_root: Path,
    source_catalog: DataCatalog,
    required_dataset_ids: Iterable[str],
) -> None:
    missing: list[str] = []
    for dataset_id in required_dataset_ids:
        try:
            source_catalog.resolve(dataset_id)
        except KeyError:
            missing.append(dataset_id)
    if missing:
        raise ValueError(
            "source data root is missing datasets required for scoring: "
            f"{', '.join(missing)} ({source_root})"
        )


_REQUIRED_RELEASE_COLUMN_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    RETURNS_DATASET: (
        ("date", "TradingDate", "Trddt"),
        ("symbol", "Symbol", "Stkcd"),
        ("front_close", "close", "Clsprc", "clsprc"),
        ("dnshrtrd", "Dnshrtrd", "volume"),
        ("dnvaltrd", "Dnvaltrd", "amount"),
    ),
    ADJ_FACTOR_DATASET: (
        ("date", "TradingDate", "Trddt", "tradingdate"),
        ("symbol", "Symbol", "Stkcd"),
        (
            "cumulatebwardfactor",
            "CumulateBwardFactor",
            "cumulatefwardfactor",
            "CumulateFwardFactor",
        ),
    ),
    INDUSTRY_DATASET: (
        ("ImplementDate", "date", "TradingDate"),
        ("Symbol", "code", "Stkcd", "stkcd"),
        (
            "IndustryName",
            "IndustryClassificationName",
            "industry",
            "indnme",
        ),
    ),
    COMPANY_INFO_DATASET: (
        ("symbol", "Symbol", "stkcd", "Stkcd", "code"),
        ("listdt", "Listdt", "LISTDT", "list_date", "ListDate"),
    ),
    HS300_DATASET: (
        ("indexcd", "Indexcd"),
        ("idxtrd01", "Trddt", "date", "tradingdate"),
        ("idxtrd08", "Retindex", "return", "idxtrd05", "Clsindex", "close"),
    ),
}


def _validate_required_release_datasets(
    target: _PreparedReleaseTarget,
    release_catalog: DataCatalog,
    required_dataset_ids: Iterable[str],
) -> None:
    release_name = target.target.name or target.target.output_root.name
    for dataset_id in required_dataset_ids:
        spec = release_catalog.resolve(dataset_id)
        if not spec.row_count:
            raise ValueError(
                f"{release_name} release has no usable rows for required dataset "
                f"{dataset_id}"
            )
        dataset_path = target.temp_output_root / spec.relative_path
        columns = _release_dataset_columns(dataset_path, spec)
        folded_columns = {column.casefold() for column in columns}
        missing_groups = [
            candidates
            for candidates in _REQUIRED_RELEASE_COLUMN_GROUPS.get(dataset_id, ())
            if not any(candidate.casefold() in folded_columns for candidate in candidates)
        ]
        if missing_groups:
            missing = "; ".join("/".join(group) for group in missing_groups)
            raise ValueError(
                f"{release_name} release dataset {dataset_id} is missing required "
                f"columns: {missing}"
            )
        if dataset_id == HS300_DATASET:
            _validate_release_hs300_rows(release_name, dataset_path, spec)


def _release_dataset_columns(path: Path, spec: DatasetSpec) -> list[str]:
    if spec.format == "csv":
        return [
            str(column)
            for column in pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
        ]
    if spec.format == "parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("pyarrow is required to validate parquet releases") from exc
        return [str(column) for column in pq.read_schema(path).names]
    raise ValueError(f"unsupported dataset format: {spec.format}")


def _validate_release_hs300_rows(
    release_name: str,
    dataset_path: Path,
    spec: DatasetSpec,
) -> None:
    frame = _read_dataset(dataset_path, spec)
    columns = {str(column).casefold(): str(column) for column in frame.columns}
    code_column = columns.get("indexcd")
    if code_column is None:
        return
    codes = (
        frame[code_column]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )
    if not bool((codes == HS300_INDEX_CODE).any()):
        raise ValueError(
            f"{release_name} release has no HS300 rows in {HS300_DATASET}"
        )


def _build_release_targets(
    source_root: Path,
    source_catalog: DataCatalog,
    targets: list[_ReleaseTarget],
    progress_callback: ReleaseProgressCallback | None = None,
    required_dataset_ids: Iterable[str] = (),
) -> list[DataCatalog]:
    _validate_target_output_roots(targets)
    prepared: list[_PreparedReleaseTarget] = []
    total_datasets = len(source_catalog.datasets)
    try:
        _report_progress(
            progress_callback,
            phase="preparing",
            percent=3,
            total_datasets=total_datasets,
        )
        for target in targets:
            prepared.append(_prepare_release_target(source_root, target))
        _report_progress(
            progress_callback,
            phase="building",
            percent=5,
            total_datasets=total_datasets,
        )
        for dataset_index, spec in enumerate(source_catalog.datasets, start=1):
            stats = _write_dataset_to_release_targets(source_root, spec, prepared)
            for target, (source_row_count, row_count) in zip(prepared, stats, strict=True):
                target.released_specs.append(_released_spec(spec, source_row_count, row_count))
                target.copied_docs.update(
                    _copy_dataset_docs(source_root, target.temp_output_root, spec)
                )
            _report_progress(
                progress_callback,
                phase="building",
                percent=5 + 85 * dataset_index / max(1, total_datasets),
                completed_datasets=dataset_index,
                total_datasets=total_datasets,
                current_dataset=spec.dataset_id,
            )

        _report_progress(
            progress_callback,
            phase="cataloging",
            percent=92,
            completed_datasets=total_datasets,
            total_datasets=total_datasets,
        )
        catalogs: list[DataCatalog] = []
        for target in prepared:
            _copy_unclaimed_docs(source_root, target.temp_output_root, target.copied_docs)
            release_catalog = DataCatalog(
                root=target.target.output_root.as_posix(),
                datasets=target.released_specs,
                metadata={
                    "source_root": source_root.as_posix(),
                    "release_generation": uuid.uuid4().hex,
                    "release_start": target.target.start_date.date().isoformat()
                    if target.target.start_date is not None
                    else None,
                    "release_end": target.target.end_date.date().isoformat()
                    if target.target.end_date is not None
                    else None,
                    **target.target.metadata,
                },
            )
            _validate_required_release_datasets(
                target,
                release_catalog,
                required_dataset_ids,
            )
            release_catalog.save(target.temp_output_root / "data_catalog.json")
            catalogs.append(release_catalog)

        _report_progress(
            progress_callback,
            phase="publishing",
            percent=97,
            completed_datasets=total_datasets,
            total_datasets=total_datasets,
        )
        for target in prepared:
            _replace_output(target.temp_output_root, target.target.output_root)
        return catalogs
    except Exception:
        for target in prepared:
            if target.temp_output_root.exists():
                shutil.rmtree(target.temp_output_root)
        raise


def _report_progress(
    callback: ReleaseProgressCallback | None,
    *,
    phase: str,
    percent: float,
    completed_datasets: int = 0,
    total_datasets: int = 0,
    current_dataset: str | None = None,
) -> None:
    if callback is None:
        return
    callback(
        ReleaseBuildProgress(
            phase=phase,
            percent=max(0.0, min(100.0, round(percent, 1))),
            completed_datasets=completed_datasets,
            total_datasets=total_datasets,
            current_dataset=current_dataset,
        )
    )


def _validate_target_output_roots(targets: list[_ReleaseTarget]) -> None:
    resolved_roots: list[tuple[Path, str]] = []
    for target in targets:
        resolved = target.output_root.resolve()
        target_name = target.name or target.output_root.name
        for existing, existing_name in resolved_roots:
            if (
                resolved == existing
                or resolved in existing.parents
                or existing in resolved.parents
            ):
                raise ValueError(
                    "release output roots cannot contain each other: "
                    f"{existing_name} and {target_name}"
                )
        resolved_roots.append((resolved, target_name))


def _prepare_release_target(
    source_root: Path,
    target: _ReleaseTarget,
) -> _PreparedReleaseTarget:
    _validate_release_paths(source_root, target.output_root)
    target.output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_output_root = Path(
        tempfile.mkdtemp(
            prefix=f".{target.output_root.name}.",
            suffix=".tmp",
            dir=target.output_root.parent,
        )
    )
    return _PreparedReleaseTarget(target=target, temp_output_root=temp_output_root)


def _validate_release_paths(source_root: Path, output_root: Path) -> None:
    source_resolved = source_root.resolve()
    output_resolved = output_root.resolve()
    if (
        source_resolved == output_resolved
        or source_resolved in output_resolved.parents
        or output_resolved in source_resolved.parents
    ):
        raise ValueError("release output and source data root cannot contain each other")
    if output_resolved == Path(output_resolved.anchor):
        raise ValueError("release output cannot be a filesystem root")


def _write_dataset_to_release_targets(
    source_root: Path,
    spec: DatasetSpec,
    targets: list[_PreparedReleaseTarget],
) -> list[tuple[int, int]]:
    source_path = source_root / spec.relative_path
    for target in targets:
        (target.temp_output_root / spec.relative_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    if spec.primary_asof_column is None and spec.format != "csv":
        source_row_count = _dataset_row_count(source_path, spec)
        for target in targets:
            shutil.copy2(source_path, target.temp_output_root / spec.relative_path)
        return [(source_row_count, source_row_count) for _target in targets]
    if _streams_release_csv(spec):
        return _write_streamed_csv_release_targets(source_path, spec, targets)
    if spec.format == "parquet" and not _carries_pre_window_baseline(spec):
        return _write_streamed_parquet_release_targets(source_path, spec, targets)

    source_df = _read_dataset(source_path, spec)
    stats: list[tuple[int, int]] = []
    for target in targets:
        release_df = _filter_for_release(
            source_df,
            spec,
            target.target.start_date,
            target.target.end_date,
        )
        _write_dataset(target.temp_output_root / spec.relative_path, spec, release_df)
        stats.append((len(source_df), len(release_df)))
    return stats


def _released_spec(
    spec: DatasetSpec,
    source_row_count: int,
    row_count: int,
) -> DatasetSpec:
    return DatasetSpec(
        dataset_id=spec.dataset_id,
        aliases=spec.aliases,
        csmar_table_code=spec.csmar_table_code,
        relative_path=spec.relative_path,
        format=spec.format,
        is_static=spec.is_static,
        date_columns=spec.date_columns,
        primary_asof_column=spec.primary_asof_column,
        symbol_column=spec.symbol_column,
        column_descriptions=spec.column_descriptions,
        doc_paths=spec.doc_paths,
        row_count=row_count,
        source_row_count=source_row_count,
    )


def _validate_hidden_hs300_source(
    source_root: Path | str,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    source_catalog: DataCatalog | None = None,
) -> None:
    source_path = Path(source_root)
    catalog = source_catalog or scan_catalog(source_path)
    try:
        spec = catalog.resolve(HS300_DATASET)
    except KeyError:
        return

    frame = _read_dataset(source_path / spec.relative_path, spec)
    if frame.empty:
        raise ValueError(_hidden_hs300_error(start_date, end_date))

    columns = {str(column).lower(): str(column) for column in frame.columns}
    code_column = columns.get("indexcd")
    date_column = columns.get("idxtrd01")
    if code_column is None or date_column is None:
        raise ValueError(
            "market.index_daily must include indexcd and idxtrd01 columns for HS300 release validation"
        )

    codes = frame[code_column].astype(str).str.strip().str.zfill(6)
    dates = _date_series(frame[date_column])
    window_mask = (
        (codes == HS300_INDEX_CODE)
        & (dates >= start_date.normalize())
        & (dates <= end_date.normalize())
    )
    if not bool(window_mask.any()):
        raise ValueError(_hidden_hs300_error(start_date, end_date))


def _hidden_hs300_error(start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    return (
        "hidden_test release has no HS300 rows in market.index_daily "
        f"for {start_date.date().isoformat()} through {end_date.date().isoformat()}"
    )


def _filter_for_release(
    df: pd.DataFrame,
    spec: DatasetSpec,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> pd.DataFrame:
    if spec.primary_asof_column is None:
        return df.copy()
    dates = _date_series(df[spec.primary_asof_column])
    mask = pd.Series(True, index=df.index)
    if start_date is not None:
        mask &= dates >= start_date
    if end_date is not None:
        mask &= dates <= end_date
    filtered = df[mask].copy()
    if start_date is None or not _carries_pre_window_baseline(spec):
        return filtered
    baseline = _pre_window_baseline_rows(df, spec, dates, start_date)
    if baseline.empty:
        return filtered
    return pd.concat([baseline, filtered], ignore_index=True)


def _carries_pre_window_baseline(spec: DatasetSpec) -> bool:
    return (
        spec.dataset_id in {ADJ_FACTOR_DATASET, INDUSTRY_DATASET}
        and spec.symbol_column is not None
        and spec.primary_asof_column is not None
    )


def _pre_window_baseline_rows(
    df: pd.DataFrame,
    spec: DatasetSpec,
    dates: pd.Series,
    start_date: pd.Timestamp,
) -> pd.DataFrame:
    before_window = df[dates < start_date]
    if before_window.empty or spec.symbol_column is None:
        return df.iloc[0:0].copy()
    working = pd.DataFrame(
        {
            "date": dates.loc[before_window.index],
            "symbol": before_window[spec.symbol_column].map(normalize_stock_code),
        },
        index=before_window.index,
    )
    latest_indexes = (
        working.sort_values("date", kind="stable")
        .groupby("symbol", sort=False)
        .tail(1)
        .index
    )
    return df.loc[sorted(latest_indexes)].copy()


def _write_dataset(path: Path, spec: DatasetSpec, df: pd.DataFrame) -> None:
    if spec.format == "csv":
        df.to_csv(path, index=False)
        return
    if spec.format == "parquet":
        df.to_parquet(path, index=False)
        return
    raise ValueError(f"unsupported dataset format: {spec.format}")


def _streams_release_csv(spec: DatasetSpec) -> bool:
    return spec.format == "csv" and "/datago/" in f"/{spec.relative_path}"


def _write_streamed_csv_release(
    source_path: Path,
    output_path: Path,
    spec: DatasetSpec,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> tuple[int, int]:
    read_kwargs: dict[str, object] = {
        "encoding": "utf-8-sig",
        "chunksize": _csv_release_chunk_size(),
    }
    if spec.symbol_column:
        read_kwargs["dtype"] = {spec.symbol_column: str}
    source_row_count = 0
    row_count = 0
    wrote_rows = False
    header_columns: list[str] | None = None

    for chunk in pd.read_csv(source_path, **read_kwargs):
        if header_columns is None:
            header_columns = [str(column) for column in chunk.columns]
        source_row_count += len(chunk)
        release_chunk = _filter_for_release(chunk, spec, start_date, end_date)
        if release_chunk.empty:
            continue
        release_chunk.to_csv(
            output_path,
            index=False,
            mode="w" if not wrote_rows else "a",
            header=not wrote_rows,
        )
        wrote_rows = True
        row_count += len(release_chunk)

    if not wrote_rows:
        header = (
            pd.DataFrame(columns=header_columns)
            if header_columns is not None
            else pd.read_csv(source_path, nrows=0, encoding="utf-8-sig")
        )
        header.to_csv(output_path, index=False)
    return source_row_count, row_count


def _write_streamed_csv_release_targets(
    source_path: Path,
    spec: DatasetSpec,
    targets: list[_PreparedReleaseTarget],
) -> list[tuple[int, int]]:
    read_kwargs: dict[str, object] = {
        "encoding": "utf-8-sig",
        "chunksize": _csv_release_chunk_size(),
    }
    if spec.symbol_column:
        read_kwargs["dtype"] = {spec.symbol_column: str}
    source_row_count = 0
    row_counts = [0 for _target in targets]
    wrote_rows = [False for _target in targets]
    header_columns: list[str] | None = None

    for chunk in pd.read_csv(source_path, **read_kwargs):
        if header_columns is None:
            header_columns = [str(column) for column in chunk.columns]
        source_row_count += len(chunk)
        for index, target in enumerate(targets):
            release_chunk = _filter_for_release(
                chunk,
                spec,
                target.target.start_date,
                target.target.end_date,
            )
            if release_chunk.empty:
                continue
            release_chunk.to_csv(
                target.temp_output_root / spec.relative_path,
                index=False,
                mode="w" if not wrote_rows[index] else "a",
                header=not wrote_rows[index],
            )
            wrote_rows[index] = True
            row_counts[index] += len(release_chunk)

    if not all(wrote_rows):
        header = (
            pd.DataFrame(columns=header_columns)
            if header_columns is not None
            else pd.read_csv(source_path, nrows=0, encoding="utf-8-sig")
        )
        for index, target in enumerate(targets):
            if not wrote_rows[index]:
                header.to_csv(target.temp_output_root / spec.relative_path, index=False)
    return [(source_row_count, row_count) for row_count in row_counts]


def _write_streamed_parquet_release_targets(
    source_path: Path,
    spec: DatasetSpec,
    targets: list[_PreparedReleaseTarget],
) -> list[tuple[int, int]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("pyarrow is required to stream parquet releases") from exc

    parquet_file = pq.ParquetFile(source_path)
    schema = parquet_file.schema_arrow
    source_row_count = parquet_file.metadata.num_rows
    writers = [
        _ParquetReleaseWriter(
            target.temp_output_root / spec.relative_path,
            schema,
            pa,
            pq,
        )
        for target in targets
    ]
    try:
        for batch in parquet_file.iter_batches(batch_size=_parquet_release_batch_rows()):
            chunk = batch.to_pandas()
            for target, writer in zip(targets, writers, strict=True):
                release_chunk = _filter_window_rows(
                    chunk,
                    spec,
                    target.target.start_date,
                    target.target.end_date,
                )
                writer.write_frame(release_chunk)
    finally:
        for writer in writers:
            writer.close()
    return [(source_row_count, writer.row_count) for writer in writers]


class _ParquetReleaseWriter:
    def __init__(self, output_path: Path, source_schema: object, pa: object, pq: object):
        self.output_path = output_path
        self.source_schema = source_schema
        self.pa = pa
        self.pq = pq
        self.writer = None
        self.row_count = 0

    def write_frame(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        table = self.pa.Table.from_pandas(
            frame,
            schema=self.source_schema,
            preserve_index=False,
        )
        if self.writer is None:
            self.writer = self.pq.ParquetWriter(self.output_path, table.schema)
        self.writer.write_table(table)
        self.row_count += len(frame)

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            return
        empty_table = self.pa.Table.from_arrays(
            [self.pa.array([], type=field.type) for field in self.source_schema],
            names=self.source_schema.names,
        )
        self.pq.write_table(empty_table, self.output_path)


def _filter_window_rows(
    df: pd.DataFrame,
    spec: DatasetSpec,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> pd.DataFrame:
    if spec.primary_asof_column is None:
        return df.copy()
    dates = _date_series(df[spec.primary_asof_column])
    mask = pd.Series(True, index=df.index)
    if start_date is not None:
        mask &= dates >= start_date
    if end_date is not None:
        mask &= dates <= end_date
    return df[mask].copy()


def _dataset_row_count(source_path: Path, spec: DatasetSpec) -> int:
    if spec.format == "parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("pyarrow is required to count parquet rows") from exc

        return int(pq.ParquetFile(source_path).metadata.num_rows)
    if spec.format == "csv":
        try:
            return sum(
                len(chunk)
                for chunk in pd.read_csv(
                    source_path,
                    encoding="utf-8-sig",
                    chunksize=_csv_release_chunk_size(),
                    dtype={spec.symbol_column: str} if spec.symbol_column else None,
                )
            )
        except Exception:
            return len(_read_dataset(source_path, spec))
    raise ValueError(f"unsupported dataset format: {spec.format}")


def _csv_release_chunk_size() -> int:
    return _positive_int_from_env("QUANTFISH_RELEASE_CSV_CHUNK_SIZE", CSV_RELEASE_CHUNK_SIZE)


def _parquet_release_batch_rows() -> int:
    return _positive_int_from_env(
        "QUANTFISH_RELEASE_PARQUET_BATCH_ROWS",
        PARQUET_RELEASE_BATCH_ROWS,
    )


def _positive_int_from_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _copy_dataset_docs(source_root: Path, output_root: Path, spec: DatasetSpec) -> set[str]:
    copied: set[str] = set()
    dataset_dir = Path(spec.relative_path).parent
    for doc_name in spec.doc_paths:
        source_doc = source_root / dataset_dir / doc_name
        if not source_doc.exists():
            continue
        output_doc = output_root / dataset_dir / doc_name
        output_doc.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_doc, output_doc)
        copied.add(source_doc.relative_to(source_root).as_posix())
    return copied


def _copy_unclaimed_docs(
    source_root: Path, output_root: Path, copied_docs: Iterable[str]
) -> None:
    copied = set(copied_docs)
    for path in source_root.rglob("*"):
        if not path.is_file() or _is_hidden(path.relative_to(source_root)):
            continue
        relative = path.relative_to(source_root)
        if relative.as_posix() in copied:
            continue
        if path.suffix.lower() not in {".pdf", ".txt"}:
            continue
        output_path = output_root / relative
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, output_path)


def _is_hidden(relative_path: Path) -> bool:
    return any(part.startswith(".") for part in relative_path.parts)


def _replace_output(temp_output_root: Path, output_root: Path) -> None:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    backup_output_root = temp_output_root.with_name(
        f"{temp_output_root.name}.previous"
    )
    previous_output_moved = False
    if output_root.exists():
        output_root.rename(backup_output_root)
        previous_output_moved = True
    try:
        temp_output_root.rename(output_root)
    except Exception:
        if previous_output_moved:
            backup_output_root.rename(output_root)
        raise
    if previous_output_moved:
        try:
            if backup_output_root.is_dir():
                shutil.rmtree(backup_output_root)
            else:
                backup_output_root.unlink()
        except OSError:
            LOGGER.warning(
                "release published, but previous output could not be removed: %s",
                backup_output_root,
                exc_info=True,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build QuantFish data releases.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build a dated data release")
    build_parser.add_argument("--source", required=True)
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--start")
    build_parser.add_argument("--end")
    config_parser = subparsers.add_parser(
        "build-from-config", help="Build one or more configured data releases"
    )
    config_parser.add_argument("--config", default="config/platform.yaml")
    config_parser.add_argument(
        "--release",
        action="append",
        choices=CONFIGURED_RELEASE_NAMES,
        dest="release_names",
        help="Release to build; repeat to build several (default: all)",
    )
    args = parser.parse_args(argv)

    if args.command == "build":
        build_release(args.source, args.output, start=args.start, end=args.end)
        return 0
    if args.command == "build-from-config":
        build_releases_from_config(
            ConfigRepository(args.config).load(),
            release_names=args.release_names,
        )
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
