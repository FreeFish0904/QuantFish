from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from quantfish.platform_config import (
    BacktestConfig,
    ConfigRepository,
    ConfigService,
    DataReleasesConfig,
    ExecutionConfig,
    PlatformConfig,
    ScoringConfig,
)


def test_platform_config_defaults_match_course_plan() -> None:
    config = PlatformConfig.default()

    assert config.course.name == "QuantFish"
    assert config.data_releases == DataReleasesConfig(
        raw_data_root="new_data",
        learning_output_root="data_releases/learning",
        hidden_output_root="data_releases/hidden_test",
        learning_start=date(2022, 1, 1),
        learning_end=date(2022, 12, 31),
        hidden_start=date(2023, 1, 1),
        hidden_end=date(2025, 12, 31),
    )
    assert config.backtest == BacktestConfig(
        data_start=date(2022, 1, 1),
        scoring_start=date(2023, 1, 1),
        scoring_end=date(2025, 12, 31),
        capital=1_000_000,
        group_count=5,
        industry_neutralization=False,
        price_policy="front_adjusted",
        execution_price="vwap",
        mark_price="close",
        long_only_benchmark="hs300",
        long_only_min_beta_observations=20,
        long_only_risk_free_rate=0.0175,
    )
    assert config.scoring == ScoringConfig()
    assert config.execution == ExecutionConfig()
    assert config.execution.allowed_market_types == (1, 4, 16, 32, 64)
    assert config.execution.long_only is True
    assert config.execution.commission_rate == pytest.approx(0.0003)
    assert config.execution.slippage_rate == pytest.approx(0.0005)
    assert config.execution.sell_stamp_duty_rate == pytest.approx(0.0005)
    assert config.execution.terminal_stale_position_policy == "reject"
    assert config.execution.long_only_weighting == "rank_equal"
    assert config.execution.long_only_target_count == 50
    assert config.execution.max_position_weight == pytest.approx(0.05)
    assert config.execution.max_participation_rate == pytest.approx(0.10)
    assert config.execution.min_listing_days == 60


def test_learning_window_roots_follow_a_custom_learning_release_root(
    tmp_path: Path,
) -> None:
    learning_root = tmp_path / "isolated_releases" / "learning"
    releases = DataReleasesConfig(learning_output_root=learning_root.as_posix())

    assert releases.release_window("learning_1").output_root == (
        learning_root.parent / "learning_1"
    ).as_posix()
    assert releases.release_window("learning_2").output_root == (
        learning_root.parent / "learning_2"
    ).as_posix()
    assert releases.release_window("learning_3").output_root == (
        learning_root.parent / "learning_3"
    ).as_posix()


def test_platform_config_validates_learning_windows_and_release_roots() -> None:
    default = PlatformConfig.default()

    with pytest.raises(ValueError, match="learning_2_start cannot be after"):
        replace(
            default,
            data_releases=replace(
                default.data_releases,
                learning_2_start=date(2020, 1, 2),
                learning_2_end=date(2020, 1, 1),
            ),
        ).validate()

    with pytest.raises(ValueError, match="output roots must be distinct"):
        replace(
            default,
            data_releases=replace(
                default.data_releases,
                learning_1_output_root=default.data_releases.learning_output_root,
            ),
        ).validate()

    with pytest.raises(ValueError, match="output roots cannot contain each other"):
        replace(
            default,
            data_releases=replace(
                default.data_releases,
                learning_1_output_root="data_releases/learning/window_1",
            ),
        ).validate()


def test_config_repository_loads_and_saves_yaml(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    repository = ConfigRepository(path)

    repository.save(PlatformConfig.default())
    loaded = repository.load()

    assert loaded == PlatformConfig.default()
    text = path.read_text(encoding="utf-8")
    assert "learning_end: '2022-12-31'" in text
    assert "learning_start: '2022-01-01'" in text
    assert "raw_data_root: new_data" in text
    assert "price_policy: front_adjusted" in text
    assert "alpha_type" not in text
    assert "long_only_risk_free_rate: 0.0175" in text
    assert "industry_neutralization: false" in text
    assert "sharpe_weight: 45.0" in text
    assert "short_profit_weight: 50.0" in text
    assert "short_profit_target: 0.3" in text
    assert "submissions_enabled: true" in text
    assert "python_enabled" not in text
    assert "allowed_market_types:" in text
    assert "- 1" in text
    assert "- 4" in text
    assert "- 16" in text
    assert "- 32" in text
    assert "- 64" in text
    assert "sell_stamp_duty_rate: 0.0005" in text
    assert "terminal_stale_position_policy: reject" in text


def test_config_repository_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert ConfigRepository(tmp_path / "missing.yaml").load() == PlatformConfig.default()


def test_config_service_validates_updates_before_saving(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(
        backtest={"scoring_end": "2026-12-31", "group_count": 10},
    )

    assert updated.backtest.scoring_end == date(2026, 12, 31)
    assert updated.backtest.group_count == 10
    assert ConfigRepository(path).load() == updated


def test_config_repository_migrates_legacy_scoring_weights_to_short_discouraging_defaults(
    tmp_path: Path,
) -> None:
    path = tmp_path / "platform.yaml"
    path.write_text(
        """
scoring:
  return_weight: 0.35
  sharpe_weight: 0.55
  drawdown_weight: 0.1
  average_year_weight: 0.0
  worst_year_weight: 0.0
  turnover_threshold: 1.0
  turnover_penalty_weight: 0.0
  turnover_penalty_cap: 0.0
  minimum_slice_trading_days: 120
""",
        encoding="utf-8",
    )

    loaded = ConfigRepository(path).load()

    assert loaded.scoring == ScoringConfig(minimum_slice_trading_days=120)


def test_config_service_updates_and_validates_new_scoring_fields(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(
        scoring={
            "short_profit_weight": 35.0,
            "short_profit_target": 0.2,
            "turnover_limit": 2.5,
        },
    )

    assert updated.scoring.short_profit_weight == 35.0
    assert updated.scoring.short_profit_target == 0.2
    assert updated.scoring.turnover_limit == 2.5

    with pytest.raises(ValueError, match="short_profit_weight cannot be negative"):
        service.update(scoring={"short_profit_weight": -1.0})

    with pytest.raises(ValueError, match="short_profit_target must be positive"):
        service.update(scoring={"short_profit_target": 0.0})

    with pytest.raises(ValueError, match="turnover_limit must be positive"):
        service.update(scoring={"turnover_limit": 0.0})


def test_config_service_rejects_invalid_date_windows(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="scoring_start cannot be after scoring_end"):
        service.update(backtest={"scoring_start": "2026-01-01"})

    assert not (tmp_path / "platform.yaml").exists()


def test_config_service_updates_hidden_test_window(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(
        data_releases={
            "learning_end": "2023-12-31",
            "hidden_start": "2024-01-01",
            "hidden_end": "2024-12-31",
        },
        backtest={
            "scoring_start": "2024-01-01",
            "scoring_end": "2024-12-31",
        },
    )

    assert updated.data_releases.hidden_start == date(2024, 1, 1)
    assert updated.data_releases.hidden_end == date(2024, 12, 31)
    assert ConfigRepository(path).load() == updated


def test_config_service_rejects_invalid_backtest_settings(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="group_count must be positive"):
        service.update(backtest={"group_count": 0})

    with pytest.raises(ValueError, match="capital must be positive"):
        service.update(backtest={"capital": 0})


def test_config_service_updates_and_validates_industry_neutralization(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(backtest={"industry_neutralization": True})

    assert updated.backtest.industry_neutralization is True
    assert ConfigRepository(path).load().backtest.industry_neutralization is True

    with pytest.raises(ValueError, match="industry_neutralization must be a boolean"):
        service.update(backtest={"industry_neutralization": "yes"})


def test_config_service_updates_and_validates_allowed_market_types(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(execution={"allowed_market_types": [1, "4", 64]})

    assert updated.execution.allowed_market_types == (1, 4, 64)
    assert ConfigRepository(path).load().execution.allowed_market_types == (1, 4, 64)

    with pytest.raises(ValueError, match="allowed_market_types cannot be empty"):
        service.update(execution={"allowed_market_types": []})

    with pytest.raises(ValueError, match="unsupported market type"):
        service.update(execution={"allowed_market_types": [3]})


def test_config_service_updates_and_validates_long_only_settings(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(
        backtest={
            "long_only_benchmark": "hs300",
            "long_only_min_beta_observations": 30,
            "long_only_risk_free_rate": 0.02,
        },
        execution={
            "long_only_weighting": "score_proportional",
            "long_only_target_count": 80,
            "max_position_weight": 0.04,
            "max_participation_rate": 0.08,
            "min_listing_days": 90,
            "terminal_stale_position_policy": "carry",
        },
    )

    assert updated.backtest.long_only_benchmark == "hs300"
    assert updated.backtest.long_only_min_beta_observations == 30
    assert updated.backtest.long_only_risk_free_rate == pytest.approx(0.02)
    assert updated.execution.long_only_weighting == "score_proportional"
    assert updated.execution.long_only_target_count == 80
    assert updated.execution.max_position_weight == pytest.approx(0.04)
    assert updated.execution.max_participation_rate == pytest.approx(0.08)
    assert updated.execution.min_listing_days == 90
    assert updated.execution.terminal_stale_position_policy == "carry"

    unbenchmarked = service.update(backtest={"long_only_benchmark": "none"})
    assert unbenchmarked.backtest.long_only_benchmark == "none"

    with pytest.raises(ValueError, match="unsupported long_only_benchmark"):
        service.update(backtest={"long_only_benchmark": "csi500"})

    with pytest.raises(ValueError, match="long_only_min_beta_observations must be positive"):
        service.update(backtest={"long_only_min_beta_observations": 0})

    with pytest.raises(ValueError, match="long_only_risk_free_rate must be finite"):
        service.update(backtest={"long_only_risk_free_rate": float("nan")})

    with pytest.raises(ValueError, match="long_only_risk_free_rate must be between -1 and 1"):
        service.update(backtest={"long_only_risk_free_rate": 1.0})

    with pytest.raises(ValueError, match="unsupported long_only_weighting"):
        service.update(execution={"long_only_weighting": "signed"})

    with pytest.raises(ValueError, match="long_only_target_count must be positive"):
        service.update(execution={"long_only_target_count": 0})

    with pytest.raises(ValueError, match="max_position_weight must be between 0 and 1"):
        service.update(execution={"max_position_weight": 1.5})

    with pytest.raises(ValueError, match="max_participation_rate must be between 0 and 1"):
        service.update(execution={"max_participation_rate": 0.0})

    with pytest.raises(ValueError, match="min_listing_days cannot be negative"):
        service.update(execution={"min_listing_days": -1})

    with pytest.raises(ValueError, match="terminal_stale_position_policy"):
        service.update(execution={"terminal_stale_position_policy": "silently_zero"})


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("backtest", "industry_neutralization"),
        ("execution", "submissions_enabled"),
        ("execution", "hidden_test_enabled"),
        ("execution", "submission_timeout_enabled"),
        ("execution", "long_only"),
    ],
)
def test_config_rejects_string_booleans(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match=f"{field} must be a boolean"):
        service.update(**{section: {field: "false"}})


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("backtest", "capital"),
        ("scoring", "sharpe_weight"),
        ("execution", "commission_rate"),
        ("execution", "sell_stamp_duty_rate"),
        ("execution", "max_leverage"),
    ],
)
def test_config_rejects_non_finite_numeric_values(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match=f"{field} must be finite"):
        service.update(**{section: {field: float("nan")}})


def test_config_service_updates_hidden_test_visibility(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(execution={"hidden_test_enabled": False})

    assert updated.execution.hidden_test_enabled is False
    assert ConfigRepository(path).load().execution.hidden_test_enabled is False


def test_config_service_updates_submission_gate(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(execution={"submissions_enabled": False})

    assert updated.execution.submissions_enabled is False
    assert ConfigRepository(path).load().execution.submissions_enabled is False


def test_config_repository_ignores_legacy_python_enabled(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    path.write_text(
        """
execution:
  submissions_enabled: true
  python_enabled: false
""",
        encoding="utf-8",
    )

    loaded = ConfigRepository(path).load()

    assert loaded.execution.submissions_enabled is True
    assert "python_enabled" not in ConfigRepository(path).load().to_dict()["execution"]


def test_config_repository_ignores_legacy_alpha_type(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    path.write_text(
        """
backtest:
  alpha_type: longonly
  group_count: 7
execution:
  long_only: true
""",
        encoding="utf-8",
    )

    repository = ConfigRepository(path)
    loaded = repository.load()
    repository.save(loaded)

    assert loaded.backtest.group_count == 7
    assert loaded.execution.long_only is True
    assert "alpha_type" not in repository.load().to_dict()["backtest"]
    assert "alpha_type" not in path.read_text(encoding="utf-8")


def test_config_service_ignores_legacy_alpha_type_updates(tmp_path: Path) -> None:
    path = tmp_path / "platform.yaml"
    service = ConfigService(ConfigRepository(path))

    updated = service.update(backtest={"alpha_type": "marketneutral", "group_count": 6})

    assert updated.backtest.group_count == 6
    assert "alpha_type" not in ConfigRepository(path).load().to_dict()["backtest"]


def test_config_rejects_unsupported_policy_values(tmp_path: Path) -> None:
    service = ConfigService(ConfigRepository(tmp_path / "platform.yaml"))

    with pytest.raises(ValueError, match="unsupported price_policy"):
        service.update(backtest={"price_policy": "raw"})

    with pytest.raises(ValueError, match="unsupported execution_price"):
        service.update(backtest={"execution_price": "open"})

    with pytest.raises(ValueError, match="unsupported mark_price"):
        service.update(backtest={"mark_price": "vwap"})
