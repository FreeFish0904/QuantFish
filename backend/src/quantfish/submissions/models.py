from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class SubmissionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionDataTrack(StrEnum):
    HIDDEN_TEST = "hidden_test"
    LEARNING = "learning"
    LEARNING_1 = "learning_1"
    LEARNING_2 = "learning_2"
    LEARNING_3 = "learning_3"


@dataclass(frozen=True)
class Team:
    team_id: str
    display_name: str
    password_hash: str
    created_at: str = field(default_factory=_utc_now)
    archived_at: str | None = None

    @classmethod
    def from_plaintext_password(
        cls,
        *,
        team_id: str,
        display_name: str,
        password: str,
        created_at: str | None = None,
        archived_at: str | None = None,
    ) -> Team:
        return cls(
            team_id=team_id,
            display_name=display_name,
            password_hash=hash_team_password(password),
            created_at=created_at or _utc_now(),
            archived_at=archived_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "display_name": self.display_name,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "archived_at": self.archived_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Team:
        password_hash = data.get("password_hash")
        if password_hash is None and data.get("password") is not None:
            password_hash = hash_team_password(str(data["password"]))
        return cls(
            team_id=str(data["team_id"]),
            display_name=str(data["display_name"]),
            password_hash=str(password_hash),
            created_at=str(data.get("created_at") or _utc_now()),
            archived_at=(str(data["archived_at"]) if data.get("archived_at") is not None else None),
        )


@dataclass(frozen=True)
class ScoreFingerprints:
    config_sha256: str
    hidden_catalog_sha256: str
    strategy_sha256: str
    engine_version: str
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST
    release_generation: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "config_sha256": self.config_sha256,
            "hidden_catalog_sha256": self.hidden_catalog_sha256,
            "strategy_sha256": self.strategy_sha256,
            "engine_version": self.engine_version,
            "data_track": self.data_track.value,
        }
        if self.release_generation is not None:
            payload["release_generation"] = self.release_generation
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScoreFingerprints:
        return cls(
            config_sha256=str(data["config_sha256"]),
            hidden_catalog_sha256=str(data["hidden_catalog_sha256"]),
            strategy_sha256=str(data["strategy_sha256"]),
            engine_version=str(data["engine_version"]),
            data_track=_submission_data_track(data.get("data_track")),
            release_generation=(
                str(data["release_generation"])
                if data.get("release_generation") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class SubmissionMetrics:
    total_return: float | None = None
    annual_return: float | None = None
    average_year_return: float | None = None
    worst_year_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    average_turnover: float | None = None
    average_short_exposure: float | None = None
    long_total_return: float | None = None
    short_total_return: float | None = None
    annualized_short_profit: float | None = None
    calmar: float | None = None
    win_rate: float | None = None
    stale_position_days: int | None = None
    max_stale_gross_exposure: float | None = None
    average_stale_gross_exposure: float | None = None
    terminal_stale_position_count: int | None = None
    terminal_stale_gross_exposure: float | None = None
    trading_days: int | None = None
    raw_total_return: float | None = None
    raw_sharpe: float | None = None
    raw_max_drawdown: float | None = None
    raw_calmar: float | None = None
    risk_free_rate: float | None = None
    risk_free_daily_return: float | None = None
    beta: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    active_total_return: float | None = None
    active_annual_return: float | None = None
    active_max_drawdown: float | None = None
    active_calmar: float | None = None
    # Geometric reporting basis (see docs/metrics-definitions.md). Scoring keeps
    # using the arithmetic annual_return above.
    compounded_total_return: float | None = None
    cagr: float | None = None
    compounded_max_drawdown: float | None = None
    compounded_calmar: float | None = None
    volatility: float | None = None
    sortino: float | None = None
    t_stat: float | None = None
    t_stat_p_value: float | None = None
    # Benchmark-relative reporting block (see docs/metrics-definitions.md).
    # strategy_* is the raw portfolio on the days that have a CSI 300 return, so
    # excess_* = strategy_* - benchmark_*; scoring keeps using the rows above.
    strategy_total_return: float | None = None
    strategy_annual_return: float | None = None
    benchmark_total_return: float | None = None
    benchmark_annual_return: float | None = None
    benchmark_cagr: float | None = None
    excess_total_return: float | None = None
    excess_annual_return: float | None = None
    excess_compounded_return: float | None = None
    excess_cagr: float | None = None
    excess_max_drawdown: float | None = None
    excess_win_rate: float | None = None
    excess_volatility: float | None = None
    excess_information_ratio: float | None = None
    excess_beta: float | None = None
    excess_observations: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "average_year_return": self.average_year_return,
            "worst_year_return": self.worst_year_return,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "average_turnover": self.average_turnover,
            "average_short_exposure": self.average_short_exposure,
            "long_total_return": self.long_total_return,
            "short_total_return": self.short_total_return,
            "annualized_short_profit": self.annualized_short_profit,
            "calmar": self.calmar,
            "win_rate": self.win_rate,
            "stale_position_days": self.stale_position_days,
            "max_stale_gross_exposure": self.max_stale_gross_exposure,
            "average_stale_gross_exposure": self.average_stale_gross_exposure,
            "terminal_stale_position_count": self.terminal_stale_position_count,
            "terminal_stale_gross_exposure": self.terminal_stale_gross_exposure,
            "trading_days": self.trading_days,
            "raw_total_return": self.raw_total_return,
            "raw_sharpe": self.raw_sharpe,
            "raw_max_drawdown": self.raw_max_drawdown,
            "raw_calmar": self.raw_calmar,
            "risk_free_rate": self.risk_free_rate,
            "risk_free_daily_return": self.risk_free_daily_return,
            "beta": self.beta,
            "tracking_error": self.tracking_error,
            "information_ratio": self.information_ratio,
            "active_total_return": self.active_total_return,
            "active_annual_return": self.active_annual_return,
            "active_max_drawdown": self.active_max_drawdown,
            "active_calmar": self.active_calmar,
            "compounded_total_return": self.compounded_total_return,
            "cagr": self.cagr,
            "compounded_max_drawdown": self.compounded_max_drawdown,
            "compounded_calmar": self.compounded_calmar,
            "volatility": self.volatility,
            "sortino": self.sortino,
            "t_stat": self.t_stat,
            "t_stat_p_value": self.t_stat_p_value,
            "strategy_total_return": self.strategy_total_return,
            "strategy_annual_return": self.strategy_annual_return,
            "benchmark_total_return": self.benchmark_total_return,
            "benchmark_annual_return": self.benchmark_annual_return,
            "benchmark_cagr": self.benchmark_cagr,
            "excess_total_return": self.excess_total_return,
            "excess_annual_return": self.excess_annual_return,
            "excess_compounded_return": self.excess_compounded_return,
            "excess_cagr": self.excess_cagr,
            "excess_max_drawdown": self.excess_max_drawdown,
            "excess_win_rate": self.excess_win_rate,
            "excess_volatility": self.excess_volatility,
            "excess_information_ratio": self.excess_information_ratio,
            "excess_beta": self.excess_beta,
            "excess_observations": self.excess_observations,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SubmissionMetrics:
        return cls.from_summary(data)

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any]) -> SubmissionMetrics:
        return cls(
            total_return=_optional_float(summary.get("total_return")),
            annual_return=_optional_float(summary.get("annual_return")),
            average_year_return=_optional_float(summary.get("average_year_return")),
            worst_year_return=_optional_float(summary.get("worst_year_return")),
            sharpe=_optional_float(summary.get("sharpe")),
            max_drawdown=_optional_float(summary.get("max_drawdown")),
            average_turnover=_optional_float(summary.get("average_turnover")),
            average_short_exposure=_optional_float(summary.get("average_short_exposure")),
            long_total_return=_optional_float(summary.get("long_total_return")),
            short_total_return=_optional_float(summary.get("short_total_return")),
            annualized_short_profit=_optional_float(summary.get("annualized_short_profit")),
            calmar=_optional_float(summary.get("calmar")),
            win_rate=_optional_float(summary.get("win_rate")),
            stale_position_days=_optional_int(summary.get("stale_position_days")),
            max_stale_gross_exposure=_optional_float(summary.get("max_stale_gross_exposure")),
            average_stale_gross_exposure=_optional_float(
                summary.get("average_stale_gross_exposure")
            ),
            terminal_stale_position_count=_optional_int(
                summary.get("terminal_stale_position_count")
            ),
            terminal_stale_gross_exposure=_optional_float(
                summary.get("terminal_stale_gross_exposure")
            ),
            trading_days=_optional_int(summary.get("trading_days")),
            raw_total_return=_optional_float(summary.get("raw_total_return")),
            raw_sharpe=_optional_float(summary.get("raw_sharpe")),
            raw_max_drawdown=_optional_float(summary.get("raw_max_drawdown")),
            raw_calmar=_optional_float(summary.get("raw_calmar")),
            risk_free_rate=_optional_float(summary.get("risk_free_rate")),
            risk_free_daily_return=_optional_float(summary.get("risk_free_daily_return")),
            beta=_optional_float(summary.get("beta")),
            tracking_error=_optional_float(summary.get("tracking_error")),
            information_ratio=_optional_float(summary.get("information_ratio")),
            active_total_return=_optional_float(summary.get("active_total_return")),
            active_annual_return=_optional_float(summary.get("active_annual_return")),
            active_max_drawdown=_optional_float(summary.get("active_max_drawdown")),
            active_calmar=_optional_float(summary.get("active_calmar")),
            compounded_total_return=_optional_float(summary.get("compounded_total_return")),
            cagr=_optional_float(summary.get("cagr")),
            compounded_max_drawdown=_optional_float(summary.get("compounded_max_drawdown")),
            compounded_calmar=_optional_float(summary.get("compounded_calmar")),
            volatility=_optional_float(summary.get("volatility")),
            sortino=_optional_float(summary.get("sortino")),
            t_stat=_optional_float(summary.get("t_stat")),
            t_stat_p_value=_optional_float(summary.get("t_stat_p_value")),
            strategy_total_return=_optional_float(summary.get("strategy_total_return")),
            strategy_annual_return=_optional_float(summary.get("strategy_annual_return")),
            benchmark_total_return=_optional_float(summary.get("benchmark_total_return")),
            benchmark_annual_return=_optional_float(summary.get("benchmark_annual_return")),
            benchmark_cagr=_optional_float(summary.get("benchmark_cagr")),
            excess_total_return=_optional_float(summary.get("excess_total_return")),
            excess_annual_return=_optional_float(summary.get("excess_annual_return")),
            excess_compounded_return=_optional_float(summary.get("excess_compounded_return")),
            excess_cagr=_optional_float(summary.get("excess_cagr")),
            excess_max_drawdown=_optional_float(summary.get("excess_max_drawdown")),
            excess_win_rate=_optional_float(summary.get("excess_win_rate")),
            excess_volatility=_optional_float(summary.get("excess_volatility")),
            excess_information_ratio=_optional_float(summary.get("excess_information_ratio")),
            excess_beta=_optional_float(summary.get("excess_beta")),
            excess_observations=_optional_int(summary.get("excess_observations")),
        )


@dataclass(frozen=True)
class Submission:
    submission_id: str
    team_id: str
    status: SubmissionStatus
    strategy_path: str
    report_dir: str
    fingerprints: ScoreFingerprints | None
    original_filename: str
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST
    submission_number: int | None = None
    metrics: SubmissionMetrics | None = None
    error_message: str | None = None
    submitted_at: str = field(default_factory=_utc_now)
    scored_at: str | None = None
    config_snapshot: dict[str, Any] | None = None
    report_pdf_status: str | None = None
    report_pdf_path: str | None = None
    report_pdf_created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "team_id": self.team_id,
            "status": self.status.value,
            "strategy_path": self.strategy_path,
            "report_dir": self.report_dir,
            "fingerprints": self.fingerprints.to_dict() if self.fingerprints else None,
            "original_filename": self.original_filename,
            "data_track": self.data_track.value,
            "submission_number": self.submission_number,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "error_message": self.error_message,
            "submitted_at": self.submitted_at,
            "scored_at": self.scored_at,
            "config_snapshot": self.config_snapshot,
            "report_pdf_status": self.report_pdf_status,
            "report_pdf_path": self.report_pdf_path,
            "report_pdf_created_at": self.report_pdf_created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Submission:
        metrics = data.get("metrics")
        return cls(
            submission_id=str(data["submission_id"]),
            team_id=str(data["team_id"]),
            status=_submission_status(str(data["status"])),
            strategy_path=str(data["strategy_path"]),
            report_dir=str(data["report_dir"]),
            fingerprints=(
                ScoreFingerprints.from_dict(data["fingerprints"])
                if data.get("fingerprints") is not None
                else None
            ),
            original_filename=str(data.get("original_filename") or "strategy.py"),
            data_track=_submission_data_track(data.get("data_track")),
            submission_number=_optional_int(data.get("submission_number")),
            metrics=SubmissionMetrics.from_dict(metrics) if metrics else None,
            error_message=(
                str(data["error_message"]) if data.get("error_message") is not None else None
            ),
            submitted_at=str(data.get("submitted_at") or _utc_now()),
            scored_at=str(data["scored_at"]) if data.get("scored_at") is not None else None,
            config_snapshot=(
                dict(data["config_snapshot"])
                if isinstance(data.get("config_snapshot"), Mapping)
                else None
            ),
            report_pdf_status=str(data["report_pdf_status"])
            if data.get("report_pdf_status") is not None
            else None,
            report_pdf_path=str(data["report_pdf_path"])
            if data.get("report_pdf_path") is not None
            else None,
            report_pdf_created_at=str(data["report_pdf_created_at"])
            if data.get("report_pdf_created_at") is not None
            else None,
        )


def team_public_payload(team: Team | None) -> dict[str, str]:
    if team is None:
        raise ValueError("team is required")
    return {
        "team_id": team.team_id,
        "display_name": team.display_name,
    }


def _submission_status(value: str) -> SubmissionStatus:
    legacy_statuses = {
        "uploaded": SubmissionStatus.QUEUED,
        "succeeded": SubmissionStatus.COMPLETED,
    }
    if value in legacy_statuses:
        return legacy_statuses[value]
    return SubmissionStatus(value)


def _submission_data_track(value: Any) -> SubmissionDataTrack:
    if value is None or value == "":
        return SubmissionDataTrack.HIDDEN_TEST
    if isinstance(value, SubmissionDataTrack):
        return value
    return SubmissionDataTrack(str(value))


def hash_team_password(password: str) -> str:
    if not password:
        raise ValueError("team password is required")
    salt = secrets.token_hex(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_team_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return hmac.compare_digest(password, password_hash)
    if algorithm != "pbkdf2_sha256":
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()
    return hmac.compare_digest(actual, expected)


def submission_list_payload(
    submission: Submission,
    team_name: str = "",
    score: float | None = None,
    stale: bool = False,
    raw_error: str | None = None,
) -> dict[str, Any]:
    number = submission.submission_number or 0
    return {
        "submission_id": submission.submission_id,
        "submission_number": number,
        "submission_label": submission_label(number),
        "team_id": submission.team_id,
        "team_name": team_name,
        "status": submission.status.value,
        "data_track": submission.data_track.value,
        "stale": stale,
        "submitted_at": submission.submitted_at,
        "scored_at": submission.scored_at,
        "metrics": submission.metrics.to_dict() if submission.metrics else None,
        "score": score,
        "error_message": submission.error_message,
        "raw_error": raw_error,
        "report_pdf_status": submission.report_pdf_status,
    }


def _snapshot_section(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    section = snapshot.get(key)
    return section if isinstance(section, Mapping) else {}


def _snapshot_value(section: Mapping[str, Any], key: str) -> Any:
    return section.get(key)


def submission_execution_parameters(submission: Submission) -> dict[str, Any] | None:
    snapshot = submission.config_snapshot
    if not isinstance(snapshot, Mapping):
        return None

    backtest = _snapshot_section(snapshot, "backtest")
    execution = _snapshot_section(snapshot, "execution")
    return {
        "data_track": submission.data_track.value,
        "data_start": _snapshot_value(backtest, "data_start"),
        "scoring_start": _snapshot_value(backtest, "scoring_start"),
        "scoring_end": _snapshot_value(backtest, "scoring_end"),
        "capital": _snapshot_value(backtest, "capital"),
        "group_count": _snapshot_value(backtest, "group_count"),
        "industry_neutralization": _snapshot_value(backtest, "industry_neutralization"),
        "price_policy": _snapshot_value(backtest, "price_policy"),
        "execution_price": _snapshot_value(backtest, "execution_price"),
        "mark_price": _snapshot_value(backtest, "mark_price"),
        "long_only_benchmark": _snapshot_value(backtest, "long_only_benchmark"),
        "long_only_risk_free_rate": _snapshot_value(backtest, "long_only_risk_free_rate"),
        "long_only_min_beta_observations": _snapshot_value(
            backtest,
            "long_only_min_beta_observations",
        ),
        "commission_rate": _snapshot_value(execution, "commission_rate"),
        "slippage_rate": _snapshot_value(execution, "slippage_rate"),
        "sell_stamp_duty_rate": _snapshot_value(execution, "sell_stamp_duty_rate"),
        "max_leverage": _snapshot_value(execution, "max_leverage"),
        "top_k": _snapshot_value(execution, "top_k"),
        "allowed_market_types": _snapshot_value(execution, "allowed_market_types"),
        "long_only": _snapshot_value(execution, "long_only"),
        "long_only_weighting": _snapshot_value(execution, "long_only_weighting"),
        "long_only_target_count": _snapshot_value(execution, "long_only_target_count"),
        "max_position_weight": _snapshot_value(execution, "max_position_weight"),
        "max_participation_rate": _snapshot_value(execution, "max_participation_rate"),
        "min_listing_days": _snapshot_value(execution, "min_listing_days"),
        "terminal_stale_position_policy": _snapshot_value(
            execution,
            "terminal_stale_position_policy",
        ),
        "submission_timeout_enabled": _snapshot_value(
            execution,
            "submission_timeout_enabled",
        ),
        "submission_timeout_seconds": _snapshot_value(
            execution,
            "submission_timeout_seconds",
        ),
    }


def submission_detail_payload(
    submission: Submission,
    *,
    team_name: str = "",
    artifacts: Mapping[str, Any] | None = None,
    score: float | None = None,
    stale: bool = False,
    raw_error: str | None = None,
) -> dict[str, Any]:
    payload = submission_list_payload(
        submission,
        team_name=team_name,
        score=score,
        stale=stale,
        raw_error=raw_error,
    )
    payload.update(
        {
            "fingerprints": submission.fingerprints.to_dict() if submission.fingerprints else None,
            "original_filename": submission.original_filename,
            "artifacts": dict(artifacts or {}),
            "execution_parameters": submission_execution_parameters(submission),
            "performance_table": list((artifacts or {}).get("performance_table", [])),
        }
    )
    return payload


def submission_label(submission_number: int) -> str:
    return f"#{submission_number}" if submission_number > 0 else "#?"


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    result = float(value)
    if math.isnan(result):
        return None
    return result


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    result = float(value)
    if math.isnan(result):
        return None
    return int(result)
