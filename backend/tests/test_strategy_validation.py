from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings

ADMIN_PASSWORD = "quantfish-admin"


def _write_release(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"TradingDate": "2023-01-03", "Symbol": "1", "Ret": 0.10, "Markettype": 1},
            {"TradingDate": "2023-01-03", "Symbol": "000002", "Ret": -0.05, "Markettype": 4},
            {"TradingDate": "2023-01-04", "Symbol": "1", "Ret": 0.03, "Markettype": 1},
            {"TradingDate": "2023-01-04", "Symbol": "000002", "Ret": 0.04, "Markettype": 4},
        ]
    ).to_parquet(stock_dir / "daily_returns.parquet", index=False)
    DataCatalog(
        root=root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="stock.daily_returns",
                aliases=[],
                csmar_table_code=None,
                relative_path="distribute/stock/daily_returns.parquet",
                format="parquet",
                is_static=False,
                date_columns=["TradingDate"],
                primary_asof_column="TradingDate",
                symbol_column="Symbol",
            )
        ],
    ).save(root / "data_catalog.json")


def _config_path(tmp_path: Path) -> Path:
    release_root = tmp_path / "release"
    _write_release(release_root)
    config = PlatformConfig.default()
    config = replace(
        config,
        data_releases=replace(
            config.data_releases,
            hidden_output_root=release_root.as_posix(),
        ),
    )
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(config)
    return config_path


def _app(tmp_path: Path) -> TestClient:
    settings = WebSettings(
        runtime_root=tmp_path / "runtime",
        config_path=_config_path(tmp_path),
        frontend_dist=tmp_path / "missing-frontend-dist",
        admin_password=ADMIN_PASSWORD,
        admin_session_secret="test-session-secret",
        participant_session_secret="test-participant-session-secret",
        student_exports_enabled=False,
    )
    return TestClient(create_app(settings))


GOOD_STRATEGY = """
import pandas as pd


def generate_signals(data):
    current = data.current("stock.daily_returns")
    return pd.DataFrame({"code": current["Symbol"], "score": range(len(current))})
"""


def _post(client: TestClient, content: str, **form: str):
    return client.post(
        "/api/submissions/validate",
        files={"file": ("generate_signals.py", content.encode("utf-8"), "text/x-python")},
        data={"team_name": "Team Alpha", "password": "secret", **form},
    )


def _create_team(client: TestClient) -> None:
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    response = client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    )
    assert response.status_code == 200


def test_validate_reports_a_working_strategy(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        response = _post(client, GOOD_STRATEGY)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True, payload
    assert payload["code"] == "ok"
    assert payload["data_track"] == "hidden_test"
    assert payload["trading_dates_checked"] == 2
    assert payload["signal_dates"] == 2
    assert payload["signal_rows"] == 4
    assert payload["first_signal_date"] == "2023-01-03"
    assert payload["last_signal_date"] == "2023-01-04"
    assert payload["sample_codes"] == ["000001", "000002"]
    assert payload["warnings"] == []
    assert payload["elapsed_ms"] >= 0


def test_validate_does_not_create_a_submission(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        _post(client, GOOD_STRATEGY)
        queued = client.get("/api/submissions").json()

    assert queued["total_count"] == 0


def test_validate_flags_a_strategy_that_raises(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        response = _post(
            client,
            """
def generate_signals(data):
    raise RuntimeError("boom")
""",
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["code"] == "strategy_error"
    assert "boom" in payload["message"]


def test_validate_flags_a_strategy_without_generate_signals(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        response = _post(client, "value = 1\n")

    payload = response.json()
    assert payload["ok"] is False
    assert payload["code"] == "invalid_signals"
    assert "generate_signals" in payload["message"]


def test_validate_rejects_a_syntax_error_before_running(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        response = _post(client, "def generate_signals(data)\n    return None\n")

    assert response.status_code == 400
    assert "invalid Python strategy" in response.json()["detail"]


def test_validate_requires_team_credentials(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        response = client.post(
            "/api/submissions/validate",
            files={"file": ("generate_signals.py", GOOD_STRATEGY.encode(), "text/x-python")},
            data={"team_name": "Team Alpha", "password": "wrong"},
        )

    assert response.status_code == 401


def test_validate_is_rate_limited_per_team(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        _create_team(client)
        statuses = [_post(client, GOOD_STRATEGY).status_code for _ in range(6)]
        blocked = _post(client, GOOD_STRATEGY)

    assert statuses == [200] * 6
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "Too many pre-checks" in blocked.json()["detail"]
