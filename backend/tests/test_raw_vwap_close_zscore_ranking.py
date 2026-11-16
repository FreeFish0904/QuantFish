from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


SCRIPT_PATH = Path("docs/student/examples/raw_vwap_close_zscore_ranking.py")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "raw_vwap_close_zscore_ranking",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def test_save_pre_return_ranking_next_to_script_writes_clean_csv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_example_module()
    monkeypatch.setattr(module, "SCRIPT_DIR", tmp_path)
    frame = pd.DataFrame(
        [
            {
                "rank": 1,
                "code": "000001",
                "score": 1.0,
                "centered_score": 1.0,
                "abs_centered_score": 1.0,
                "weighted_score": 0.5,
                "side": "long",
                "dretwd": 0.01,
            }
        ]
    )

    output_path = module.save_pre_return_ranking_next_to_script(frame)

    assert output_path == tmp_path / module.DEFAULT_OUTPUT_FILENAME
    written = pd.read_csv(output_path, dtype={"code": "string"})
    assert written["code"].tolist() == ["000001"]
    assert "weighted_score" in written.columns
    assert "dretwd" not in written.columns


def test_raw_fallback_paths_point_to_full_new_data() -> None:
    module = _load_example_module()

    assert module.RAW_DAILY_PATH.as_posix().endswith(
        "new_data/distribute/stock/daily_returns.parquet"
    )
    assert module.RAW_COMPANY_PATH.as_posix().endswith(
        "data_releases/learning/distribute/basic/company_info.csv"
    )


def test_check_longshort_weight_balance_accepts_dollar_neutral_weights() -> None:
    module = _load_example_module()
    frame = pd.DataFrame({"weighted_score": [0.30, 0.20, -0.10, -0.40]})

    summary = module.check_longshort_weight_balance(frame)

    assert summary == {
        "long_sum": 0.5,
        "short_sum": -0.5,
        "net_sum": 0.0,
        "gross_sum": 1.0,
    }


def test_check_longshort_weight_balance_rejects_unbalanced_weights() -> None:
    module = _load_example_module()
    frame = pd.DataFrame({"weighted_score": [0.60, 0.10, -0.20]})

    try:
        module.check_longshort_weight_balance(frame)
    except ValueError as exc:
        assert "long=0.700000" in str(exc)
        assert "short=-0.200000" in str(exc)
        assert "gross=0.900000" in str(exc)
    else:
        raise AssertionError("expected unbalanced weights to raise ValueError")
