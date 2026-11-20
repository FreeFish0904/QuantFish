from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from quantfish.market_types import (
    DEFAULT_ALLOWED_MARKET_TYPES,
    VALID_MARKET_TYPES,
    normalize_allowed_market_types,
)


@dataclass(frozen=True)
class CourseConfig:
    name: str = "QuantFish"


@dataclass(frozen=True)
class DataReleaseWindow:
    name: str
    output_root: str
    start: date
    end: date


@dataclass(frozen=True)
class DataReleasesConfig:
    raw_data_root: str = "new_data"
    learning_output_root: str = "data_releases/learning"
    hidden_output_root: str = "data_releases/hidden_test"
    learning_start: date = date(2022, 1, 1)
    learning_end: date = date(2022, 12, 31)
    hidden_start: date = date(2023, 1, 1)
    hidden_end: date = date(2025, 12, 31)
    learning_1_output_root: str | None = None
    learning_1_start: date = date(2010, 1, 2)
    learning_1_end: date = date(2015, 12, 31)
    learning_2_output_root: str | None = None
    learning_2_start: date = date(2015, 1, 1)
    learning_2_end: date = date(2020, 12, 31)
    learning_3_output_root: str | None = None
    learning_3_start: date = date(2020, 1, 1)
    learning_3_end: date = date(2022, 12, 31)

    def release_window(self, name: str) -> DataReleaseWindow:
        if name == "learning":
            return DataReleaseWindow(
                name=name,
                output_root=self.learning_output_root,
                start=self.learning_start,
                end=self.learning_end,
            )
        if name == "hidden_test":
            return DataReleaseWindow(
                name=name,
                output_root=self.hidden_output_root,
                start=self.hidden_start,
                end=self.hidden_end,
            )
        if name not in {"learning_1", "learning_2", "learning_3"}:
            raise ValueError(f"unsupported data release: {name}")
        configured_root = getattr(self, f"{name}_output_root")
        output_root = (
            configured_root
            if configured_root is not None
            else self._derived_learning_output_root(name)
        )
        return DataReleaseWindow(
            name=name,
            output_root=output_root,
            start=getattr(self, f"{name}_start"),
            end=getattr(self, f"{name}_end"),
        )

    def release_windows(self) -> tuple[DataReleaseWindow, ...]:
        return tuple(
            self.release_window(name)
            for name in (
                "learning",
                "learning_1",
                "learning_2",
                "learning_3",
                "hidden_test",
            )
        )

    def _derived_learning_output_root(self, name: str) -> str:
        learning_root = Path(self.learning_output_root)
        return learning_root.with_name(name).as_posix()


@dataclass(frozen=True)
class BacktestConfig:
    data_start: date = date(2022, 1, 1)
    scoring_start: date = date(2023, 1, 1)
    scoring_end: date = date(2025, 12, 31)
    capital: int = 1_000_000
    group_count: int = 5
    industry_neutralization: bool = False
    price_policy: str = "front_adjusted"
    execution_price: str = "vwap"
    mark_price: str = "close"
    long_only_benchmark: str = "hs300"
    long_only_min_beta_observations: int = 20
    long_only_risk_free_rate: float = 0.0175


@dataclass(frozen=True)
class ScoringConfig:
    sharpe_weight: float = 45.0
    sharpe_target: float = 2.0
    annual_return_weight: float = 35.0
    annual_return_target: float = 0.30
    drawdown_weight: float = 15.0
    drawdown_limit: float = 0.30
    turnover_weight: float = 5.0
    turnover_limit: float = 3.0
    short_profit_weight: float = 50.0
    short_profit_target: float = 0.30
    minimum_slice_trading_days: int = 1


@dataclass(frozen=True)
class ExecutionConfig:
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0005
    sell_stamp_duty_rate: float = 0.0005
    max_leverage: float = 1.0
    top_k: int | None = None
    allowed_market_types: tuple[int, ...] = DEFAULT_ALLOWED_MARKET_TYPES
    submissions_enabled: bool = True
    hidden_test_enabled: bool = True
    max_concurrent_scoring: int = 1
    submission_timeout_seconds: int = 120
    submission_timeout_enabled: bool = True
    long_only: bool = True
    long_only_weighting: str = "rank_equal"
    long_only_target_count: int = 50
    max_position_weight: float = 0.05
    max_participation_rate: float = 0.10
    min_listing_days: int = 60
    terminal_stale_position_policy: str = "reject"


@dataclass(frozen=True)
class PlatformConfig:
    course: CourseConfig
    data_releases: DataReleasesConfig
    backtest: BacktestConfig
    scoring: ScoringConfig = ScoringConfig()
    execution: ExecutionConfig = ExecutionConfig()

    @classmethod
    def default(cls) -> PlatformConfig:
        return cls(
            course=CourseConfig(),
            data_releases=DataReleasesConfig(),
            backtest=BacktestConfig(),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlatformConfig:
        defaults = cls.default()
        return cls(
            course=CourseConfig(**_merge_section(defaults.course, data.get("course", {}))),
            data_releases=DataReleasesConfig(
                **_merge_section(
                    defaults.data_releases,
                    data.get("data_releases", {}),
                )
            ),
            backtest=BacktestConfig(
                **_merge_section(
                    defaults.backtest,
                    _coerce_backtest(data.get("backtest", {})),
                )
            ),
            scoring=ScoringConfig(
                **_merge_section(
                    defaults.scoring,
                    _coerce_scoring(_section_dict(data.get("scoring", {}))),
                )
            ),
            execution=ExecutionConfig(
                **_coerce_execution(_merge_section(defaults.execution, data.get("execution", {})))
            ),
        ).validate()

    def to_dict(self) -> dict[str, Any]:
        return _stringify_dates(asdict(self))

    def validate(self) -> PlatformConfig:
        if not self.course.name:
            raise ValueError("course name is required")
        if not self.data_releases.raw_data_root:
            raise ValueError("raw_data_root is required")
        if not self.data_releases.learning_output_root:
            raise ValueError("learning_output_root is required")
        if not self.data_releases.hidden_output_root:
            raise ValueError("hidden_output_root is required")
        hidden_start = _to_date(self.data_releases.hidden_start)
        hidden_end = _to_date(self.data_releases.hidden_end)
        learning_start = _to_date(self.data_releases.learning_start)
        learning_end = _to_date(self.data_releases.learning_end)
        if hidden_start > hidden_end:
            raise ValueError("hidden_start cannot be after hidden_end")
        if learning_start > learning_end:
            raise ValueError("learning_start cannot be after learning_end")
        if learning_end >= hidden_start:
            raise ValueError("learning_end must be before hidden_start")
        release_windows = self.data_releases.release_windows()
        output_roots: dict[Path, str] = {}
        for window in release_windows:
            if not window.output_root:
                raise ValueError(f"{window.name}_output_root is required")
            window_start = _to_date(window.start)
            window_end = _to_date(window.end)
            if window_start > window_end:
                raise ValueError(f"{window.name}_start cannot be after {window.name}_end")
            resolved_root = Path(window.output_root).resolve()
            for existing_root, existing_name in output_roots.items():
                if resolved_root == existing_root:
                    raise ValueError(
                        "data release output roots must be distinct: "
                        f"{existing_name} and {window.name}"
                    )
                if resolved_root in existing_root.parents or existing_root in resolved_root.parents:
                    raise ValueError(
                        "data release output roots cannot contain each other: "
                        f"{existing_name} and {window.name}"
                    )
            output_roots[resolved_root] = window.name
        if self.backtest.data_start > self.backtest.scoring_start:
            raise ValueError("data_start cannot be after scoring_start")
        if self.backtest.scoring_start > self.backtest.scoring_end:
            raise ValueError("scoring_start cannot be after scoring_end")
        _require_finite_number("capital", self.backtest.capital)
        if self.backtest.capital <= 0:
            raise ValueError("capital must be positive")
        _require_integer("group_count", self.backtest.group_count)
        if self.backtest.group_count <= 0:
            raise ValueError("group_count must be positive")
        _require_boolean("industry_neutralization", self.backtest.industry_neutralization)
        if self.backtest.price_policy != "front_adjusted":
            raise ValueError(f"unsupported price_policy: {self.backtest.price_policy}")
        if self.backtest.execution_price != "vwap":
            raise ValueError(f"unsupported execution_price: {self.backtest.execution_price}")
        if self.backtest.mark_price != "close":
            raise ValueError(f"unsupported mark_price: {self.backtest.mark_price}")
        if self.backtest.long_only_benchmark not in {"hs300", "none"}:
            raise ValueError(
                f"unsupported long_only_benchmark: {self.backtest.long_only_benchmark}"
            )
        _require_integer(
            "long_only_min_beta_observations",
            self.backtest.long_only_min_beta_observations,
        )
        if self.backtest.long_only_min_beta_observations < 1:
            raise ValueError("long_only_min_beta_observations must be positive")
        _require_finite_number(
            "long_only_risk_free_rate",
            self.backtest.long_only_risk_free_rate,
        )
        if not math.isfinite(float(self.backtest.long_only_risk_free_rate)):
            raise ValueError("long_only_risk_free_rate must be finite")
        if not (-1.0 < float(self.backtest.long_only_risk_free_rate) < 1.0):
            raise ValueError("long_only_risk_free_rate must be between -1 and 1")
        for name in (
            "sharpe_weight",
            "sharpe_target",
            "annual_return_weight",
            "annual_return_target",
            "drawdown_weight",
            "drawdown_limit",
            "turnover_weight",
            "turnover_limit",
            "short_profit_weight",
            "short_profit_target",
        ):
            _require_finite_number(name, getattr(self.scoring, name))
        if self.scoring.sharpe_weight < 0:
            raise ValueError("sharpe_weight cannot be negative")
        if self.scoring.sharpe_target <= 0:
            raise ValueError("sharpe_target must be positive")
        if self.scoring.annual_return_weight < 0:
            raise ValueError("annual_return_weight cannot be negative")
        if self.scoring.annual_return_target <= 0:
            raise ValueError("annual_return_target must be positive")
        if self.scoring.drawdown_weight < 0:
            raise ValueError("drawdown_weight cannot be negative")
        if self.scoring.drawdown_limit <= 0:
            raise ValueError("drawdown_limit must be positive")
        if self.scoring.turnover_weight < 0:
            raise ValueError("turnover_weight cannot be negative")
        if self.scoring.turnover_limit <= 0:
            raise ValueError("turnover_limit must be positive")
        if self.scoring.short_profit_weight < 0:
            raise ValueError("short_profit_weight cannot be negative")
        if self.scoring.short_profit_target <= 0:
            raise ValueError("short_profit_target must be positive")
        _require_integer(
            "minimum_slice_trading_days",
            self.scoring.minimum_slice_trading_days,
        )
        if self.scoring.minimum_slice_trading_days < 1:
            raise ValueError("minimum_slice_trading_days must be positive")
        for name in (
            "commission_rate",
            "slippage_rate",
            "sell_stamp_duty_rate",
            "max_leverage",
            "max_position_weight",
            "max_participation_rate",
        ):
            _require_finite_number(name, getattr(self.execution, name))
        if self.execution.commission_rate < 0:
            raise ValueError("commission_rate cannot be negative")
        if self.execution.slippage_rate < 0:
            raise ValueError("slippage_rate cannot be negative")
        if self.execution.sell_stamp_duty_rate < 0:
            raise ValueError("sell_stamp_duty_rate cannot be negative")
        if self.execution.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")
        if self.execution.top_k is not None:
            _require_integer("top_k", self.execution.top_k)
            if self.execution.top_k <= 0:
                raise ValueError("top_k must be positive")
        if self.execution.long_only_weighting not in {
            "rank_equal",
            "score_proportional",
        }:
            raise ValueError(
                f"unsupported long_only_weighting: {self.execution.long_only_weighting}"
            )
        _require_integer("long_only_target_count", self.execution.long_only_target_count)
        if self.execution.long_only_target_count <= 0:
            raise ValueError("long_only_target_count must be positive")
        if not (0 < self.execution.max_position_weight <= 1):
            raise ValueError("max_position_weight must be between 0 and 1")
        if not (0 < self.execution.max_participation_rate <= 1):
            raise ValueError("max_participation_rate must be between 0 and 1")
        _require_integer("min_listing_days", self.execution.min_listing_days)
        if self.execution.min_listing_days < 0:
            raise ValueError("min_listing_days cannot be negative")
        if not self.execution.allowed_market_types:
            raise ValueError("allowed_market_types cannot be empty")
        unsupported = sorted(set(self.execution.allowed_market_types) - VALID_MARKET_TYPES)
        if unsupported:
            raise ValueError(f"unsupported market type: {unsupported[0]}")
        for name in (
            "submissions_enabled",
            "hidden_test_enabled",
            "submission_timeout_enabled",
            "long_only",
        ):
            _require_boolean(name, getattr(self.execution, name))
        _require_integer("max_concurrent_scoring", self.execution.max_concurrent_scoring)
        if self.execution.max_concurrent_scoring < 1:
            raise ValueError("max_concurrent_scoring must be positive")
        _require_integer(
            "submission_timeout_seconds",
            self.execution.submission_timeout_seconds,
        )
        if self.execution.submission_timeout_seconds < 1:
            raise ValueError("submission_timeout_seconds must be positive")
        if self.execution.terminal_stale_position_policy not in {"carry", "reject"}:
            raise ValueError("terminal_stale_position_policy must be 'carry' or 'reject'")
        return self


class ConfigRepository:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> PlatformConfig:
        if not self.path.exists():
            return PlatformConfig.default()
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, Mapping):
            raise ValueError(f"platform config must be a mapping: {self.path}")
        return PlatformConfig.from_dict(data)

    def save(self, config: PlatformConfig) -> None:
        config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                config.to_dict(),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )


class ConfigService:
    def __init__(self, repository: ConfigRepository):
        self.repository = repository

    def update(
        self,
        *,
        course: Mapping[str, Any] | None = None,
        data_releases: Mapping[str, Any] | None = None,
        backtest: Mapping[str, Any] | None = None,
        scoring: Mapping[str, Any] | None = None,
        execution: Mapping[str, Any] | None = None,
    ) -> PlatformConfig:
        updated = self.build_updated(
            course=course,
            data_releases=data_releases,
            backtest=backtest,
            scoring=scoring,
            execution=execution,
        )
        self.repository.save(updated)
        return updated

    def build_updated(
        self,
        *,
        course: Mapping[str, Any] | None = None,
        data_releases: Mapping[str, Any] | None = None,
        backtest: Mapping[str, Any] | None = None,
        scoring: Mapping[str, Any] | None = None,
        execution: Mapping[str, Any] | None = None,
    ) -> PlatformConfig:
        current = self.repository.load()
        return PlatformConfig(
            course=replace(current.course, **dict(course or {})),
            data_releases=replace(
                current.data_releases, **_coerce_dates(dict(data_releases or {}))
            ),
            backtest=replace(current.backtest, **_coerce_backtest(backtest or {})),
            scoring=replace(current.scoring, **_coerce_scoring(dict(scoring or {}))),
            execution=replace(
                current.execution,
                **_coerce_execution(dict(execution or {})),
            ),
        ).validate()


def _merge_section(defaults: Any, raw: Any) -> dict[str, Any]:
    raw = _section_dict(raw)
    merged = asdict(defaults)
    merged.update(_coerce_dates(dict(raw)))
    return merged


def _section_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError("config sections must be mappings")
    return dict(raw)


def _coerce_backtest(values: Any) -> dict[str, Any]:
    backtest = _coerce_dates(_section_dict(values))
    backtest.pop("alpha_type", None)
    return backtest


def _coerce_execution(values: dict[str, Any]) -> dict[str, Any]:
    values.pop("python_enabled", None)
    if "allowed_market_types" in values:
        values["allowed_market_types"] = normalize_allowed_market_types(
            values["allowed_market_types"]
        )
    return values


_LEGACY_SCORING_KEYS = {
    "return_weight",
    "average_year_weight",
    "worst_year_weight",
    "turnover_threshold",
    "turnover_penalty_weight",
    "turnover_penalty_cap",
    "short_exposure_weight",
}

_NEW_SCORING_KEYS = {
    "sharpe_target",
    "annual_return_weight",
    "annual_return_target",
    "drawdown_limit",
    "turnover_weight",
    "turnover_limit",
    "short_profit_weight",
    "short_profit_target",
}


def _coerce_scoring(values: dict[str, Any]) -> dict[str, Any]:
    if not values:
        return values
    has_new_schema = bool(_NEW_SCORING_KEYS.intersection(values))
    minimum_days = values.get("minimum_slice_trading_days")
    if _LEGACY_SCORING_KEYS.intersection(values) and not has_new_schema:
        return {"minimum_slice_trading_days": minimum_days} if minimum_days is not None else {}
    for key in _LEGACY_SCORING_KEYS:
        values.pop(key, None)
    return values


def _coerce_dates(values: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(values.items()):
        if key.endswith(("_start", "_end")) or key in {"data_start", "learning_end"}:
            values[key] = _to_date(value)
    return values


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"expected ISO date string, got {value!r}")


def _require_boolean(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")


def _require_integer(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _require_finite_number(name: str, value: Any) -> None:
    if isinstance(value, (bool, str)):
        raise ValueError(f"{name} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")


def _stringify_dates(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _stringify_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(item) for item in value]
    if isinstance(value, tuple):
        return [_stringify_dates(item) for item in value]
    return value
