from pathlib import Path

import pytest

from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.submissions import staleness as staleness_module
from quantfish.submissions.models import ScoreFingerprints, SubmissionDataTrack
from quantfish.submissions.staleness import (
    ScoreFingerprintContext,
    current_fingerprint_context,
    current_fingerprints,
    is_stale,
    is_stale_against_context,
    sha256_file,
    sha256_text,
)


def test_sha256_helpers_hash_text_and_file_contents(tmp_path: Path) -> None:
    path = tmp_path / "strategy.py"
    path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    assert sha256_file(path) == sha256_text(path.read_text(encoding="utf-8"))
    assert sha256_text("alpha") != sha256_text("beta")


def test_current_fingerprints_include_config_catalog_strategy_and_engine(
    tmp_path: Path,
) -> None:
    hidden_catalog_path = tmp_path / "hidden" / "data_catalog.json"
    hidden_catalog_path.parent.mkdir()
    hidden_catalog_path.write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    stored = current_fingerprints(
        {"backtest": {"group_count": 5}, "execution": {"long_only": False}},
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )

    assert isinstance(stored, ScoreFingerprints)
    assert not is_stale(stored, stored)
    assert is_stale(None, stored)
    assert not is_stale(
        stored,
        current_fingerprints(
            {
                "backtest": {"group_count": 5},
                "execution": {"long_only": False},
                "scoring": {"short_profit_weight": 99.0},
            },
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )
    assert is_stale(
        stored,
        current_fingerprints(
            {"backtest": {"group_count": 5}, "execution": {"long_only": True}},
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )
    assert is_stale(
        stored,
        current_fingerprints(
            {
                "backtest": {"group_count": 5, "industry_neutralization": True},
                "execution": {"long_only": False},
            },
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )

    hidden_catalog_path.write_text(
        '{"datasets": [{"dataset_id": "x", "relative_path": "x.csv", '
        '"format": "csv", "is_static": true}]}\n',
        encoding="utf-8",
    )
    (hidden_catalog_path.parent / "x.csv").write_text("x\n1\n", encoding="utf-8")
    assert is_stale(
        stored,
        current_fingerprints(
            {"backtest": {"group_count": 5}, "execution": {"long_only": False}},
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )

    hidden_catalog_path.write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path.write_text("def generate_signals(data):\n    return None\n", encoding="utf-8")
    assert is_stale(
        stored,
        current_fingerprints(
            {"backtest": {"group_count": 5}, "execution": {"long_only": False}},
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )

    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    assert is_stale(
        stored,
        current_fingerprints(
            {"backtest": {"group_count": 5}, "execution": {"long_only": False}},
            hidden_catalog_path,
            strategy_path,
            "engine-2",
        ),
    )


def test_industry_neutralization_changes_config_fingerprint(tmp_path: Path) -> None:
    hidden_catalog_path = tmp_path / "hidden" / "data_catalog.json"
    hidden_catalog_path.parent.mkdir()
    hidden_catalog_path.write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    stored = current_fingerprints(
        {
            "backtest": {"group_count": 5, "industry_neutralization": False},
            "execution": {"long_only": False},
        },
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )

    assert is_stale(
        stored,
        current_fingerprints(
            {
                "backtest": {"group_count": 5, "industry_neutralization": True},
                "execution": {"long_only": False},
            },
            hidden_catalog_path,
            strategy_path,
            "engine-1",
        ),
    )


def test_operational_execution_toggles_do_not_change_config_fingerprint(
    tmp_path: Path,
) -> None:
    hidden_catalog_path = tmp_path / "hidden" / "data_catalog.json"
    hidden_catalog_path.parent.mkdir()
    hidden_catalog_path.write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    stored = current_fingerprints(
        {
            "backtest": {"alpha_type": "longshort", "group_count": 5, "capital": 1_000_000},
            "execution": {
                "long_only": False,
                "max_leverage": 1.0,
                "max_concurrent_scoring": 1,
                "python_enabled": True,
                "hidden_test_enabled": True,
                "submission_timeout_seconds": 120,
                "submission_timeout_enabled": True,
            },
        },
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )

    enabled_current = current_fingerprints(
        {
            "backtest": {"group_count": 5, "capital": 1_000_000},
            "execution": {
                "long_only": False,
                "max_leverage": 1.0,
                "max_concurrent_scoring": 4,
                "submissions_enabled": True,
                "hidden_test_enabled": True,
                "submission_timeout_seconds": 600,
                "submission_timeout_enabled": True,
            },
        },
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )
    disabled_current = current_fingerprints(
        {
            "backtest": {"group_count": 5, "capital": 1_000_000},
            "execution": {
                "long_only": False,
                "max_leverage": 1.0,
                "max_concurrent_scoring": 8,
                "submissions_enabled": False,
                "hidden_test_enabled": False,
                "submission_timeout_seconds": 900,
                "submission_timeout_enabled": False,
            },
        },
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )

    assert stored.config_sha256 == enabled_current.config_sha256
    assert stored.config_sha256 == disabled_current.config_sha256
    assert not is_stale(stored, enabled_current)
    assert not is_stale(stored, disabled_current)


def test_capital_changes_config_fingerprint(tmp_path: Path) -> None:
    hidden_catalog_path = tmp_path / "hidden" / "data_catalog.json"
    hidden_catalog_path.parent.mkdir()
    hidden_catalog_path.write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    stored = current_fingerprints(
        {"backtest": {"capital": 1_000_000}},
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )
    current = current_fingerprints(
        {"backtest": {"capital": 2_000_000}},
        hidden_catalog_path,
        strategy_path,
        "engine-1",
    )

    assert stored.config_sha256 != current.config_sha256
    assert is_stale(stored, current)


def test_current_fingerprints_include_hidden_dataset_contents(tmp_path: Path) -> None:
    hidden_root = tmp_path / "hidden"
    data_path = hidden_root / "distribute" / "stock" / "daily_returns.csv"
    data_path.parent.mkdir(parents=True)
    data_path.write_text("TradingDate,Symbol,Ret\n2023-01-03,000001,0.01\n", encoding="utf-8")
    DataCatalog(
        root=hidden_root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="stock.daily_returns",
                aliases=[],
                csmar_table_code=None,
                relative_path="distribute/stock/daily_returns.csv",
                format="csv",
                is_static=False,
            )
        ],
    ).save(hidden_root / "data_catalog.json")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    stored = current_fingerprints(
        {"execution": {"long_only": False}},
        hidden_root / "data_catalog.json",
        strategy_path,
        "engine-1",
    )

    data_path.write_text("TradingDate,Symbol,Ret\n2023-01-03,000001,0.99\n", encoding="utf-8")
    current = current_fingerprints(
        {"execution": {"long_only": False}},
        hidden_root / "data_catalog.json",
        strategy_path,
        "engine-1",
    )

    assert is_stale(stored, current)


def test_context_based_staleness_matches_full_fingerprints(tmp_path: Path) -> None:
    hidden_root = tmp_path / "hidden"
    hidden_root.mkdir()
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    context = current_fingerprint_context(
        {"execution": {"long_only": False}},
        hidden_root / "data_catalog.json",
        "engine-1",
    )
    stored = current_fingerprints(
        {"execution": {"long_only": False}},
        hidden_root / "data_catalog.json",
        strategy_path,
        "engine-1",
    )

    assert isinstance(context, ScoreFingerprintContext)
    assert stored.config_sha256 == context.config_sha256
    assert stored.hidden_catalog_sha256 == context.hidden_catalog_sha256
    assert stored.engine_version == context.engine_version
    assert not is_stale_against_context(stored, context, strategy_path)

    strategy_path.write_text("def generate_signals(data):\n    return None\n", encoding="utf-8")
    assert is_stale_against_context(stored, context, strategy_path)

    changed_context = ScoreFingerprintContext(
        config_sha256="changed",
        hidden_catalog_sha256=context.hidden_catalog_sha256,
        engine_version=context.engine_version,
        data_track=SubmissionDataTrack.HIDDEN_TEST,
    )
    assert is_stale_against_context(stored, changed_context, strategy_path)
    assert is_stale_against_context(None, context, strategy_path)

    learning_context = ScoreFingerprintContext(
        config_sha256=context.config_sha256,
        hidden_catalog_sha256=context.hidden_catalog_sha256,
        engine_version=context.engine_version,
        data_track=SubmissionDataTrack.LEARNING,
    )
    assert is_stale_against_context(stored, learning_context, strategy_path)


def test_context_staleness_short_circuits_strategy_hash_on_global_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy_path = tmp_path / "missing.py"
    stored = ScoreFingerprints(
        config_sha256="stored-config",
        hidden_catalog_sha256="stored-catalog",
        strategy_sha256="stored-strategy",
        engine_version="engine",
        data_track=SubmissionDataTrack.HIDDEN_TEST,
    )
    context = ScoreFingerprintContext(
        config_sha256="changed-config",
        hidden_catalog_sha256="stored-catalog",
        engine_version="engine",
        data_track=SubmissionDataTrack.HIDDEN_TEST,
    )
    calls: list[Path] = []

    def fail_if_called(path: Path | str) -> str:
        calls.append(Path(path))
        raise AssertionError("strategy hash should not be read after global mismatch")

    monkeypatch.setattr(staleness_module, "sha256_file", fail_if_called)

    assert is_stale_against_context(stored, context, strategy_path)
    assert calls == []
