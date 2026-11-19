from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from quantfish.data.catalog import DataCatalog
from quantfish.submissions.models import (
    ScoreFingerprints,
    SubmissionDataTrack,
    _submission_data_track,
)


@dataclass(frozen=True)
class ScoreFingerprintContext:
    config_sha256: str
    hidden_catalog_sha256: str
    engine_version: str
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST
    release_generation: str | None = None


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_sha256(config: Any) -> str:
    config_text = json.dumps(
        staleness_config_payload(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(config_text)


def staleness_config_payload(config: Any) -> Any:
    return _staleness_config_ready(config)


def release_file_signatures(catalog_path: Path | str) -> tuple[tuple[str, int, int], ...]:
    path = Path(catalog_path)
    root = path.parent
    catalog = DataCatalog.load(path)
    signatures = [_file_signature(path.relative_to(root).as_posix(), path)]
    for spec in sorted(catalog.datasets, key=lambda item: item.relative_path):
        dataset_path = root / spec.relative_path
        signatures.append(_file_signature(spec.relative_path, dataset_path))
    return tuple(signatures)


def sha256_release(catalog_path: Path | str) -> str:
    path = Path(catalog_path)
    root = path.parent
    digest = hashlib.sha256()
    _update_hash_with_file(digest, path.relative_to(root).as_posix(), path)
    catalog = DataCatalog.load(path)
    for spec in sorted(catalog.datasets, key=lambda item: item.relative_path):
        dataset_path = root / spec.relative_path
        _update_hash_with_file(digest, spec.relative_path, dataset_path)
    return digest.hexdigest()


def current_fingerprints(
    config: Any,
    hidden_catalog_path: Path | str,
    strategy_path: Path | str,
    engine_version: str,
    data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
) -> ScoreFingerprints:
    context = current_fingerprint_context(
        config,
        hidden_catalog_path,
        engine_version,
        data_track,
    )
    return fingerprints_from_context(context, strategy_path)


def current_fingerprint_context(
    config: Any,
    hidden_catalog_path: Path | str,
    engine_version: str,
    data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
) -> ScoreFingerprintContext:
    generation = release_generation(hidden_catalog_path)
    return ScoreFingerprintContext(
        config_sha256=config_sha256(config),
        hidden_catalog_sha256=sha256_release(hidden_catalog_path),
        engine_version=str(engine_version),
        data_track=_submission_data_track(data_track),
        release_generation=generation,
    )


def fingerprints_from_context(
    context: ScoreFingerprintContext,
    strategy_path: Path | str,
) -> ScoreFingerprints:
    return ScoreFingerprints(
        config_sha256=context.config_sha256,
        hidden_catalog_sha256=context.hidden_catalog_sha256,
        strategy_sha256=sha256_file(strategy_path),
        engine_version=context.engine_version,
        data_track=context.data_track,
        release_generation=context.release_generation,
    )


def is_stale(
    stored: ScoreFingerprints | None,
    current: ScoreFingerprints,
) -> bool:
    return stored != current


def is_stale_against_context(
    stored: ScoreFingerprints | None,
    context: ScoreFingerprintContext,
    strategy_path: Path | str,
) -> bool:
    if stored is None:
        return True
    if (
        stored.config_sha256 != context.config_sha256
        or stored.hidden_catalog_sha256 != context.hidden_catalog_sha256
        or stored.engine_version != context.engine_version
        or stored.data_track != context.data_track
        or stored.release_generation != context.release_generation
    ):
        return True
    try:
        return stored.strategy_sha256 != sha256_file(strategy_path)
    except Exception:
        return True


def _json_ready(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _staleness_config_ready(config: Any) -> Any:
    ready = _json_ready(config)
    if isinstance(ready, Mapping):
        ready = dict(ready)
        ready.pop("scoring", None)
        backtest = ready.get("backtest")
        if isinstance(backtest, Mapping):
            backtest = dict(backtest)
            backtest.pop("alpha_type", None)
            ready["backtest"] = backtest
        execution = ready.get("execution")
        if isinstance(execution, Mapping):
            execution = dict(execution)
            execution.pop("submissions_enabled", None)
            execution.pop("hidden_test_enabled", None)
            execution.pop("max_concurrent_scoring", None)
            execution.pop("submission_timeout_seconds", None)
            execution.pop("submission_timeout_enabled", None)
            execution["python_enabled"] = True
            ready["execution"] = execution
    return ready


def release_generation(catalog_path: Path | str) -> str | None:
    catalog = DataCatalog.load(catalog_path)
    value = catalog.metadata.get("release_generation")
    if value is None:
        return None
    generation = str(value).strip()
    return generation or None


def _update_hash_with_file(digest: hashlib._Hash, relative_path: str, path: Path) -> None:
    digest.update(relative_path.encode("utf-8"))
    digest.update(b"\0")
    digest.update(sha256_file(path).encode("ascii"))
    digest.update(b"\0")


def _file_signature(relative_path: str, path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (relative_path, stat.st_size, stat.st_mtime_ns)
