from pathlib import Path

import pytest

from quantfish.backtest import pdf_report
from quantfish.backtest.pdf_report_version import (
    PDF_REPORT_VERSION,
    mark_pdf_report_written,
    pdf_report_is_current,
    pdf_report_path,
)

SUMMARY = {
    "sharpe": 1.5,
    "sortino": 2.0,
    "cagr": 0.12,
    "annual_return": 0.15,
    "total_return": 0.3,
    "max_drawdown": 0.08,
    "calmar": 1.9,
    "t_stat": 2.4,
    "average_turnover": 0.35,
    "win_rate": 0.55,
    "information_ratio": 0.8,
    "trading_days": 242,
}

EXCESS_SUMMARY = {
    **SUMMARY,
    "strategy_total_return": 0.32,
    "strategy_annual_return": 0.16,
    "benchmark_total_return": 0.20,
    "benchmark_annual_return": 0.10,
    "benchmark_cagr": 0.095,
    "excess_total_return": 0.12,
    "excess_annual_return": 0.06,
    "excess_compounded_return": 0.10,
    "excess_cagr": 0.055,
    "excess_max_drawdown": 0.04,
    "excess_win_rate": 0.53,
    "excess_volatility": 0.07,
    "excess_information_ratio": 0.86,
    "excess_beta": 0.92,
    "excess_observations": 242,
}

def test_cover_cards_label_scoring_basis_and_add_excess_cards() -> None:
    labels = [card["label"] for card in pdf_report._cover_cards({}, SUMMARY)]
    assert "Annual Return (scoring)" in labels
    assert "Total Return (scoring)" in labels
    assert "Excess Return (ann.)" not in labels

    cards = {card["label"]: card["value"] for card in pdf_report._cover_cards({}, EXCESS_SUMMARY)}
    assert cards["Excess Return (ann.)"] == "+6.0%"
    assert cards["Excess Return (total)"] == "+12.0%"
    assert cards["Info Ratio (excess)"] == "0.860"
    assert cards["Tracking Error"] == "7.0%"
    assert cards["Beta (vs CSI 300)"] == "0.920"
    assert cards["Days vs Index"] == "242"


def test_card_groups_split_strategy_and_benchmark_blocks() -> None:
    groups = pdf_report._card_groups({}, EXCESS_SUMMARY)

    assert [group["title"] for group in groups] == ["Strategy performance", "Versus CSI 300"]
    assert {card["group"] for card in groups[0]["cards"]} == {"strategy"}
    assert {card["group"] for card in groups[1]["cards"]} == {"benchmark"}


def test_card_groups_skip_the_benchmark_block_without_index_data() -> None:
    groups = pdf_report._card_groups({}, SUMMARY)

    assert [group["title"] for group in groups] == ["Strategy performance"]

def test_verdict_reports_a_win_with_information_ratio() -> None:
    verdict = pdf_report._verdict({}, EXCESS_SUMMARY)

    assert verdict["tone"] == "positive"
    assert verdict["label"] == "Beat the CSI 300"
    assert "+6.0% per year" in verdict["detail"]
    assert "242 aligned days" in verdict["detail"]
    assert "information ratio 0.86" in verdict["detail"]


def test_verdict_flags_a_loss() -> None:
    summary = {**EXCESS_SUMMARY, "excess_annual_return": -0.03}

    verdict = pdf_report._verdict({}, summary)

    assert verdict["tone"] == "negative"
    assert verdict["label"] == "Trailed the CSI 300"
    assert "-3.0% per year" in verdict["detail"]


def test_verdict_explains_why_the_benchmark_block_is_missing() -> None:
    diagnostics = {
        "benchmark_relative": {
            "status": "unavailable",
            "reason": "only 3 aligned benchmark observations",
        }
    }

    verdict = pdf_report._verdict({}, SUMMARY, diagnostics)

    assert verdict["tone"] == "muted"
    assert verdict["label"] == "No CSI 300 comparison"
    assert "only 3 aligned benchmark observations" in verdict["detail"]


def test_highlights_cover_window_risk_benchmark_and_extremes() -> None:
    highlights = pdf_report._highlights(
        {},
        EXCESS_SUMMARY,
        period={"start": "2023-01-03", "end": "2024-12-31"},
        yearly_records=[
            {"period": "2023", "total_return": 0.21},
            {"period": "2024", "total_return": -0.04},
        ],
    )

    joined = " ".join(highlights)
    assert "242 trading days, 2023-01-03 to 2024-12-31" in joined
    assert "Compounded 12.0% a year" in joined
    assert "+6.0% a year versus the CSI 300" in joined
    assert "Best year 2023 (+21.0%), worst year 2024 (-4.0%)." in joined
    assert len(highlights) <= 4


def test_highlights_stay_quiet_without_metrics() -> None:
    assert pdf_report._highlights({}, {}, period={}) == []

def test_risk_rows_label_the_scoring_basis_side_of_the_benchmark_block() -> None:
    rows = dict(
        pdf_report._risk_rows(
            {"beta": 0.5, "tracking_error": 0.02, "information_ratio": 0.4},
            SUMMARY,
        )
    )

    assert rows["Beta (scoring basis)"] == "0.500"
    assert rows["Tracking Error (scoring basis)"] == "2.0%"
    assert rows["Information Ratio (scoring basis)"] == "0.400"


def test_benchmark_sections_are_hidden_without_benchmark_data() -> None:
    assert pdf_report._benchmark_sections({}, SUMMARY) == []


def _rows_by_label(section):
    return {row[0]: row[1] for row in section["rows"]}


def test_benchmark_sections_group_strategy_index_and_excess_rows() -> None:
    sections = pdf_report._benchmark_sections({}, EXCESS_SUMMARY)

    assert [section["title"] for section in sections] == [
        "Strategy (raw portfolio, aligned days)",
        "CSI 300 benchmark",
        "Excess return (strategy − CSI 300)",
        "Coverage & scoring reference",
    ]
    strategy, benchmark, excess, coverage = sections
    assert _rows_by_label(strategy)["Total return"] == "32.0%"
    assert _rows_by_label(strategy)["Annual return (arithmetic)"] == "16.0%"
    assert _rows_by_label(benchmark)["CAGR (geometric)"] == "9.5%"
    assert _rows_by_label(excess)["Total return (arithmetic)"] == "+12.0%"
    assert _rows_by_label(excess)["Annual return (arithmetic)"] == "+6.0%"
    assert _rows_by_label(excess)["Compounded relative return (geometric)"] == "10.0%"
    assert _rows_by_label(excess)["CAGR (geometric)"] == "5.5%"
    assert _rows_by_label(excess)["Max drawdown (on the excess equity curve)"] == "4.0%"
    assert _rows_by_label(excess)["Win rate (days ahead of the index)"] == "53.0%"
    assert _rows_by_label(excess)["Tracking error (annualized excess volatility)"] == "7.0%"
    assert _rows_by_label(excess)["Information ratio (excess / tracking error)"] == "0.860"
    assert _rows_by_label(excess)["Beta (strategy vs CSI 300)"] == "0.920"
    assert _rows_by_label(coverage)["Aligned observations (days)"] == "242"
    assert "Beta-adjusted excess, annualized (scoring basis)" not in _rows_by_label(coverage)


def test_benchmark_sections_carry_a_sign_tone_for_excess_values() -> None:
    excess_rows = {
        row[0]: row for row in pdf_report._benchmark_sections({}, EXCESS_SUMMARY)[2]["rows"]
    }
    losing = pdf_report._benchmark_sections(
        {},
        {
            **EXCESS_SUMMARY,
            "excess_total_return": -0.2,
            "excess_annual_return": -0.07,
        },
    )[2]["rows"]
    losing_rows = {row[0]: row for row in losing}

    assert excess_rows["Total return (arithmetic)"][2] == "up"
    assert losing_rows["Total return (arithmetic)"][2] == "down"
    assert losing_rows["Annual return (arithmetic)"][1] == "-7.0%"


def test_benchmark_sections_include_scoring_basis_when_beta_adjusted() -> None:
    sections = pdf_report._benchmark_sections(
        {"active_annual_return": 0.08}, EXCESS_SUMMARY
    )

    coverage = _rows_by_label(sections[-1])
    assert coverage["Beta-adjusted excess, annualized (scoring basis)"] == "8.0%"


def test_benchmark_sections_ignore_not_a_number_values() -> None:
    sections = pdf_report._benchmark_sections(
        {}, {**EXCESS_SUMMARY, "excess_information_ratio": float("nan")}
    )

    assert _rows_by_label(sections[2])["Information ratio (excess / tracking error)"] == "—"


def test_yearly_rows_use_the_period_column_and_signed_returns() -> None:
    rows = pdf_report._yearly_rows(
        {
            "performance_by_year": [
                {
                    "period": "2023",
                    "total_return": 0.21,
                    "annualized_return": 0.25,
                    "sharpe": 1.4,
                    "turnover": 0.32,
                    "drawdown": 0.07,
                }
            ]
        }
    )

    assert rows == [
        {
            "year": "2023",
            "return": "+21.0%",
            "annualized": "25.0%",
            "sharpe": "1.40",
            "turnover": "32.0%",
            "drawdown": "7.0%",
            "tone": "up",
        }
    ]

def _graph_data():
    return {
        "equity_cny": [
            {"date": "2023-01-03", "equity_cny": 1_000_000.0},
            {"date": "2023-01-04", "equity_cny": 1_010_000.0},
        ],
        "benchmark": [
            {"date": "2023-01-03", "benchmark_cny": 1_000_000.0},
            {"date": "2023-01-04", "benchmark_cny": 1_005_000.0},
        ],
        "drawdown": [
            {"date": "2023-01-03", "drawdown": 0.0},
            {"date": "2023-01-04", "drawdown": -0.01},
        ],
    }


def test_render_plots_without_series_returns_no_paths(tmp_path: Path) -> None:
    assert pdf_report._render_plots({}, tmp_path) == {}


def test_render_plots_adds_excess_curve_only_with_excess_series(tmp_path: Path) -> None:
    graph_data = _graph_data()
    assert pdf_report._render_plots(graph_data, tmp_path) == {
        "equity_curve": "plots/equity_curve.png",
        "drawdown": "plots/drawdown.png",
    }

    graph_data["excess"] = [
        {"date": "2023-01-03", "excess_return": 0.001, "excess_cny": 1_000.0},
        {"date": "2023-01-04", "excess_return": 0.004, "excess_cny": 5_000.0},
    ]
    paths = pdf_report._render_plots(graph_data, tmp_path)

    assert paths["excess_curve"] == "plots/excess_curve.png"
    assert (tmp_path / "excess_curve.png").is_file()
    assert "monthly_excess" not in paths


def test_render_plots_adds_the_new_activity_charts(tmp_path: Path) -> None:
    excess = [
        {"date": f"2023-01-{day:02d}", "excess_return": 0.001 * (day % 3 - 1)}
        for day in range(1, 26)
    ]
    graph_data = {
        "excess": excess,
        "turnover": [
            {"date": f"2023-02-{day:02d}", "turnover": 0.1 + 0.01 * day} for day in range(1, 13)
        ],
        "exposure": [
            {
                "date": f"2023-02-{day:02d}",
                "long_exposure": 0.8,
                "short_exposure": 0.2,
            }
            for day in range(1, 13)
        ],
        "group_cumulative": [
            {"date": f"2023-02-{day:02d}", "group": group, "cumulative_return": 0.01 * day}
            for group in (1, 5)
            for day in range(1, 13)
        ],
    }

    paths = pdf_report._render_plots(graph_data, tmp_path)

    assert paths["monthly_excess"] == "plots/monthly_excess.png"
    assert paths["turnover"] == "plots/turnover.png"
    assert paths["exposure"] == "plots/exposure.png"
    assert paths["group_cumulative"] == "plots/group_cumulative.png"

def test_render_plots_skips_malformed_records(tmp_path: Path) -> None:
    graph_data = {
        "equity_cny": [
            {"date": None, "equity_cny": None},
            {"date": "not-a-date", "equity_cny": 1.0},
            {"date": "2023-01-03", "equity_cny": float("nan")},
            "not-a-record",
        ],
        "turnover": [{"date": "2023-01-03", "turnover": 0.2}],
    }

    assert pdf_report._render_plots(graph_data, tmp_path) == {}


def _template_context():
    return {
        "submission_id": "sub-1",
        "submission_label": "#1",
        "team_name": "Team A",
        "generated_at": "2026-01-01 00:00 UTC",
        "data_track": "learning_1",
        "period": {"start": "2023-01-03", "end": "2024-12-31"},
        "verdict": pdf_report._verdict({}, EXCESS_SUMMARY),
        "highlights": pdf_report._highlights({}, EXCESS_SUMMARY, period={}),
        "cover_cards": pdf_report._cover_cards({}, EXCESS_SUMMARY),
        "card_groups": pdf_report._card_groups({}, EXCESS_SUMMARY),
        "risk_table": pdf_report._risk_rows({}, EXCESS_SUMMARY),
        "yearly_table": [],
        "params": [("Data Track", "learning_1")],
        "plots": {},
        "version": "quantfish-0.1.0",
    }


def test_template_renders_the_cover_and_benchmark_section() -> None:
    pytest.importorskip("jinja2")

    with_rows = pdf_report._render_template(
        {
            **_template_context(),
            "benchmark_sections": pdf_report._benchmark_sections({}, EXCESS_SUMMARY),
        }
    )
    without_rows = pdf_report._render_template(
        {**_template_context(), "benchmark_sections": []}
    )

    assert "Benchmark &amp; Excess Return" in with_rows
    assert "Excess return (strategy " in with_rows
    assert "Aligned observations (days)" in with_rows
    assert "Benchmark &amp; Excess Return" not in without_rows
    assert "Strategy performance" in with_rows
    assert "Versus CSI 300" in with_rows
    assert "Beat the CSI 300" in with_rows
    assert "Total Return (scoring)" in with_rows


def test_template_survives_a_run_without_charts() -> None:
    pytest.importorskip("jinja2")

    html = pdf_report._render_template(
        {**_template_context(), "benchmark_sections": [], "card_groups": []}
    )

    assert "Backtest Report" in html
    assert "No chart series were found" in html


def test_pdf_report_is_current_requires_a_stamp(tmp_path: Path) -> None:
    assert pdf_report_is_current(tmp_path) is False

    pdf_report_path(tmp_path).write_bytes(b"%PDF-1.4")
    assert pdf_report_is_current(tmp_path) is False

    mark_pdf_report_written(tmp_path)
    assert pdf_report_is_current(tmp_path) is True

    (tmp_path / "report.version").write_text("1900.01.01\n", encoding="utf-8")
    assert pdf_report_is_current(tmp_path) is False
    assert PDF_REPORT_VERSION != "1900.01.01"
