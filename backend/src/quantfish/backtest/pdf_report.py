"""PDF report generator for backtest results using matplotlib + weasyprint + jinja2.

The module imports only the base dependencies (pandas, numpy, matplotlib) at import
time; ``jinja2`` and ``weasyprint`` belong to the optional ``quantfish[pdf]`` extra
and are imported where they are used, so the rest of the backend keeps working
without them.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from quantfish.backtest.pdf_report_version import (
    PDF_REPORT_VERSION,
    mark_pdf_report_written,
    pdf_report_path,
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

PALETTE = (
    "#4fc3f7",
    "#ffd54f",
    "#81c784",
    "#e57373",
    "#ba68c8",
    "#4db6ac",
    "#f06292",
    "#a1887f",
)

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "axes.facecolor": "#1a1a2e",
    "figure.facecolor": "#1a1a2e",
    "axes.edgecolor": "#333",
    "axes.labelcolor": "#ccc",
    "xtick.color": "#999",
    "ytick.color": "#999",
    "text.color": "#ccc",
    "grid.color": "#333",
    "grid.alpha": 0.5,
    "lines.linewidth": 1.2,
    "figure.dpi": 160,
    "savefig.dpi": 160,
})


def _safe_float(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _fmt(value, digits=2):
    f = _safe_float(value)
    if f is None:
        return "—"
    return f"{f:.{digits}f}"


def _fmt_pct(value, digits=1):
    f = _safe_float(value)
    if f is None:
        return "—"
    return f"{f * 100:.{digits}f}%"


def _fmt_signed_pct(value, digits=1):
    """Percent with an explicit ``+``/``-`` sign; ``—`` when the value is unusable."""

    f = _safe_float(value)
    if f is None:
        return "—"
    return f"{f * 100:+.{digits}f}%"


def _fmt_int(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _merged(metrics, summary):
    """``summary.csv`` first, live ``SubmissionMetrics`` on top."""

    return {**summary, **(metrics or {})}


def _tone(value):
    """CSS class for a signed number, used to colour deltas in the tables."""

    f = _safe_float(value)
    if f is None:
        return "flat"
    if f > 0:
        return "up"
    if f < 0:
        return "down"
    return "flat"


def generate_pdf_report(submission, report_dir, team_name=""):
    """Render (or refresh) the PDF report for a completed submission.

    Args:
        submission: Submission dataclass with report_pdf_status/path/created_at fields.
        report_dir: Path to the report directory.
        team_name: Display name of the team.

    Returns:
        Path to the generated PDF file.
    """

    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)

    context = build_report_context(submission, report_dir_path, team_name=team_name)
    html = _render_template(context)
    pdf_path = pdf_report_path(report_dir_path)
    _html_to_pdf(html, pdf_path, base_path=report_dir_path)
    mark_pdf_report_written(report_dir_path)
    return pdf_path


def build_report_context(submission, report_dir, *, team_name=""):
    """Collect every number the template needs; pure apart from reading artifacts."""

    report_dir_path = Path(report_dir)
    artifacts = _load_artifacts(report_dir_path)
    graph_data = _load_json(report_dir_path / "graph_data.json")
    summary = artifacts.get("summary", {})
    metrics = submission.metrics.to_dict() if submission.metrics else {}
    diagnostics = artifacts.get("diagnostics", {})
    report_number = submission.submission_number or 0
    period = _report_period(graph_data)
    yearly_rows = _yearly_rows(artifacts)

    return {
        "submission_id": submission.submission_id,
        "submission_label": f"#{report_number}" if report_number else "—",
        "team_name": team_name or submission.team_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data_track": submission.data_track.value,
        "period": period,
        "verdict": _verdict(metrics, summary, diagnostics),
        "highlights": _highlights(
            metrics,
            summary,
            period=period,
            yearly_records=artifacts.get("performance_by_year", []),
        ),
        "cover_cards": _cover_cards(metrics, summary),
        "card_groups": _card_groups(metrics, summary),
        "risk_table": _risk_rows(metrics, summary),
        "benchmark_sections": _benchmark_sections(metrics, summary),
        "yearly_table": yearly_rows,
        "params": _submission_params(submission),
        "plots": _render_plots(graph_data, report_dir_path / "plots"),
        "version": f"quantfish-0.1.0 · report build {PDF_REPORT_VERSION}",
    }


def _render_template(context):
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True
    )
    return env.get_template("report.html").render(**context)


def _report_period(graph_data):
    """``{start, end}`` dates of the plotted equity curve, if any."""

    for key in ("equity_cny", "equity"):
        records = graph_data.get(key) or []
        dates = []
        for record in records:
            try:
                dates.append(pd.Timestamp(record.get("date")))
            except (TypeError, ValueError):
                continue
        if dates:
            return {
                "start": min(dates).strftime("%Y-%m-%d"),
                "end": max(dates).strftime("%Y-%m-%d"),
            }
    return {"start": "—", "end": "—"}


def _load_artifacts(report_dir):
    artifacts = {}
    summary_path = report_dir / "summary.csv"
    if summary_path.exists():
        try:
            df = pd.read_csv(summary_path)
            if not df.empty:
                artifacts["summary"] = df.iloc[0].to_dict()
        except Exception:
            pass
    perf_path = report_dir / "performance_by_year.csv"
    if perf_path.exists():
        try:
            df = pd.read_csv(perf_path)
            if not df.empty:
                artifacts["performance_by_year"] = df.to_dict(orient="records")
        except Exception:
            pass
    diagnostics = _load_json(report_dir / "diagnostics.json")
    if isinstance(diagnostics, dict) and diagnostics:
        artifacts["diagnostics"] = diagnostics
    return artifacts


def _load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _submission_params(submission):
    cfg = submission.config_snapshot or {}
    bt = cfg.get("backtest", {}) if isinstance(cfg.get("backtest"), dict) else {}
    ex = cfg.get("execution", {}) if isinstance(cfg.get("execution"), dict) else {}
    return [
        ("Data Track", submission.data_track.value),
        ("Scoring Start", str(bt.get("scoring_start", "—"))),
        ("Scoring End", str(bt.get("scoring_end", "—"))),
        ("Capital", _fmt_int(bt.get("capital"))),
        ("Group Count", str(bt.get("group_count", "—"))),
        ("Price Policy", str(bt.get("price_policy", "—"))),
        ("Execution Price", str(bt.get("execution_price", "—"))),
        ("Mark Price", str(bt.get("mark_price", "—"))),
        ("Industry Neutralization", str(bt.get("industry_neutralization", "—"))),
        ("Long Only", str(ex.get("long_only", "—"))),
        ("Commission Rate", _fmt(ex.get("commission_rate"), 4)),
        ("Slippage Rate", _fmt(ex.get("slippage_rate"), 4)),
        ("Max Leverage", str(ex.get("max_leverage", "—"))),
        ("Max Position Weight", _fmt(ex.get("max_position_weight"), 3)),
    ]


def _cover_cards(metrics, summary):
    """Flat KPI card list; ``group`` tells the template which cover block a card is in."""

    m = _merged(metrics, summary)
    strategy = [
        ("Sharpe", _fmt(m.get("sharpe"), 3)),
        ("Sortino", _fmt(m.get("sortino"), 3)),
        ("CAGR", _fmt_pct(m.get("cagr"))),
        ("Annual Return (scoring)", _fmt_pct(m.get("annual_return"))),
        ("Total Return (scoring)", _fmt_pct(m.get("total_return"))),
        ("Max Drawdown", _fmt_pct(m.get("max_drawdown"))),
        ("Calmar", _fmt(m.get("calmar"), 3)),
        ("t-stat", _fmt(m.get("t_stat"), 2)),
        ("Avg Turnover", _fmt_pct(m.get("average_turnover"))),
        ("Win Rate", _fmt_pct(m.get("win_rate"))),
        ("Info Ratio (scoring)", _fmt(m.get("information_ratio"), 3)),
        ("Trading Days", _fmt_int(m.get("trading_days"))),
    ]
    benchmark = []
    if _safe_float(m.get("excess_annual_return")) is not None:
        benchmark = [
            ("Excess Return (ann.)", _fmt_signed_pct(m.get("excess_annual_return"))),
            ("Excess Return (total)", _fmt_signed_pct(m.get("excess_total_return"))),
            ("Info Ratio (excess)", _fmt(m.get("excess_information_ratio"), 3)),
            ("Tracking Error", _fmt_pct(m.get("excess_volatility"))),
            ("Beta (vs CSI 300)", _fmt(m.get("excess_beta"), 3)),
            ("Days vs Index", _fmt_int(m.get("excess_observations"))),
        ]
    return [
        {"label": label, "value": value, "group": group}
        for group, cards in (("strategy", strategy), ("benchmark", benchmark))
        for label, value in cards
    ]


def _card_groups(metrics, summary):
    """The same cards split into the two cover blocks; empty groups are dropped."""

    cards = _cover_cards(metrics, summary)
    groups = [
        {
            "title": "Strategy performance",
            "note": "Scoring basis, every day of the run",
            "cards": [card for card in cards if card["group"] == "strategy"],
        },
        {
            "title": "Versus CSI 300",
            "note": "Raw portfolio against the index, aligned days only",
            "cards": [card for card in cards if card["group"] == "benchmark"],
        },
    ]
    return [group for group in groups if group["cards"]]


def _verdict(metrics, summary, diagnostics=None):
    """Headline above the cards: did this run beat the index?"""

    m = _merged(metrics, summary)
    excess_annual = _safe_float(m.get("excess_annual_return"))
    if excess_annual is None:
        return {
            "tone": "muted",
            "label": "No CSI 300 comparison",
            "detail": _benchmark_unavailable_reason(diagnostics),
        }

    detail = f"{_fmt_signed_pct(excess_annual)} per year against the CSI 300"
    observations = _safe_float(m.get("excess_observations"))
    if observations:
        detail += f" over {int(observations):,} aligned days"
    information_ratio = _safe_float(m.get("excess_information_ratio"))
    if information_ratio is not None:
        detail += f" (information ratio {information_ratio:.2f})"
    return {
        "tone": "positive" if excess_annual >= 0 else "negative",
        "label": "Beat the CSI 300" if excess_annual >= 0 else "Trailed the CSI 300",
        "detail": detail,
    }


def _benchmark_unavailable_reason(diagnostics):
    block = diagnostics.get("benchmark_relative") if isinstance(diagnostics, dict) else None
    if isinstance(block, dict):
        reason = block.get("reason")
        if block.get("status") == "unavailable" and reason:
            return f"No usable index overlap: {reason}."
    return "No aligned CSI 300 observations, so the benchmark block is omitted."


def _highlights(metrics, summary, *, period, yearly_records=None):
    """Three or four factual sentences, so the report opens with an answer."""

    m = _merged(metrics, summary)
    lines = []

    days = _fmt_int(m.get("trading_days"))
    start = (period or {}).get("start", "—")
    end = (period or {}).get("end", "—")
    if days != "—" and start != "—":
        lines.append(f"Scored {days} trading days, {start} to {end}.")

    cagr = _fmt_pct(m.get("cagr"))
    sharpe = _fmt(m.get("sharpe"), 2)
    if cagr != "—" and sharpe != "—":
        lines.append(
            f"Compounded {cagr} a year with {_fmt_pct(m.get('volatility'))} "
            f"annualized volatility, a max drawdown of "
            f"{_fmt_pct(m.get('max_drawdown'))} and a Sharpe of {sharpe}."
        )

    if _safe_float(m.get("excess_annual_return")) is not None:
        sentence = (
            "The raw portfolio earned "
            f"{_fmt_signed_pct(m.get('excess_annual_return'))} a year versus the "
            f"CSI 300 ({_fmt_signed_pct(m.get('excess_total_return'))} over the "
            "aligned window"
        )
        win_rate = _safe_float(m.get("excess_win_rate"))
        if win_rate is not None:
            sentence += f", ahead of the index on {win_rate * 100:.1f}% of days"
        lines.append(sentence + ").")

    years = _yearly_values(yearly_records)
    if len(years) >= 2:
        best = max(years, key=lambda item: item[1])
        worst = min(years, key=lambda item: item[1])
        lines.append(
            f"Best year {best[0]} ({_fmt_signed_pct(best[1])}), "
            f"worst year {worst[0]} ({_fmt_signed_pct(worst[1])})."
        )

    turnover = _safe_float(m.get("average_turnover"))
    if turnover is not None:
        lines.append(f"Average daily turnover was {_fmt_pct(turnover)} of capital.")
    return lines[:4]


def _yearly_values(yearly_records):
    """``[(year, total_return)]`` with unparsable rows dropped."""

    values = []
    for record in yearly_records or []:
        label = record.get("period", record.get("year"))
        if label is None:
            continue
        value = _safe_float(record.get("total_return", record.get("return")))
        if value is None:
            continue
        values.append((str(label), value))
    return values


def _risk_rows(metrics, summary):
    m = _merged(metrics, summary)
    return [
        ("CAGR (geometric)", _fmt_pct(m.get("cagr"))),
        ("Annual Return (arithmetic, scored)", _fmt_pct(m.get("annual_return"))),
        ("Annual Volatility", _fmt_pct(m.get("volatility"))),
        ("Max Drawdown (arithmetic)", _fmt_pct(m.get("max_drawdown"))),
        ("Max Drawdown (compounded)", _fmt_pct(m.get("compounded_max_drawdown"))),
        ("Sharpe Ratio", _fmt(m.get("sharpe"), 3)),
        ("Sortino Ratio", _fmt(m.get("sortino"), 3)),
        ("Calmar Ratio (arithmetic)", _fmt(m.get("calmar"), 3)),
        ("Calmar Ratio (compounded)", _fmt(m.get("compounded_calmar"), 3)),
        ("Mean Return t-stat", _fmt(m.get("t_stat"), 3)),
        ("t-stat p-value (normal approx.)", _fmt(m.get("t_stat_p_value"), 4)),
        ("Information Ratio (scoring basis)", _fmt(m.get("information_ratio"), 3)),
        ("Win Rate", _fmt_pct(m.get("win_rate"))),
        ("Beta (scoring basis)", _fmt(m.get("beta"), 3)),
        ("Tracking Error (scoring basis)", _fmt_pct(m.get("tracking_error"))),
        ("Average Turnover", _fmt_pct(m.get("average_turnover"))),
    ]


def _benchmark_sections(metrics, summary):
    """Strategy vs CSI 300 grouped into readable blocks; empty without index overlap."""

    m = _merged(metrics, summary)
    if _safe_float(m.get("excess_total_return")) is None:
        return []
    sections = [
        {
            "title": "Strategy (raw portfolio, aligned days)",
            "rows": [
                ("Total return", _fmt_pct(m.get("strategy_total_return"))),
                ("Annual return (arithmetic)", _fmt_pct(m.get("strategy_annual_return"))),
            ],
        },
        {
            "title": "CSI 300 benchmark",
            "rows": [
                ("Total return", _fmt_pct(m.get("benchmark_total_return"))),
                ("Annual return (arithmetic)", _fmt_pct(m.get("benchmark_annual_return"))),
                ("CAGR (geometric)", _fmt_pct(m.get("benchmark_cagr"))),
            ],
        },
        {
            "title": "Excess return (strategy − CSI 300)",
            "rows": [
                (
                    "Total return (arithmetic)",
                    _fmt_signed_pct(m.get("excess_total_return")),
                    _tone(m.get("excess_total_return")),
                ),
                (
                    "Annual return (arithmetic)",
                    _fmt_signed_pct(m.get("excess_annual_return")),
                    _tone(m.get("excess_annual_return")),
                ),
                (
                    "Compounded relative return (geometric)",
                    _fmt_pct(m.get("excess_compounded_return")),
                ),
                ("CAGR (geometric)", _fmt_pct(m.get("excess_cagr"))),
                (
                    "Max drawdown (on the excess equity curve)",
                    _fmt_pct(m.get("excess_max_drawdown")),
                ),
                ("Win rate (days ahead of the index)", _fmt_pct(m.get("excess_win_rate"))),
                (
                    "Tracking error (annualized excess volatility)",
                    _fmt_pct(m.get("excess_volatility")),
                ),
                (
                    "Information ratio (excess / tracking error)",
                    _fmt(m.get("excess_information_ratio"), 3),
                ),
                ("Beta (strategy vs CSI 300)", _fmt(m.get("excess_beta"), 3)),
            ],
        },
    ]
    coverage = [("Aligned observations (days)", _fmt_int(m.get("excess_observations")))]
    if _safe_float(m.get("active_annual_return")) is not None:
        coverage.append(
            (
                "Beta-adjusted excess, annualized (scoring basis)",
                _fmt_pct(m.get("active_annual_return")),
            )
        )
    sections.append({"title": "Coverage & scoring reference", "rows": coverage})
    return sections


def _yearly_rows(artifacts):
    result = []
    for record in artifacts.get("performance_by_year", []):
        year = record.get("period", record.get("year"))
        result.append(
            {
                "year": str(year) if year is not None else "—",
                "return": _fmt_signed_pct(
                    record.get("total_return", record.get("return"))
                ),
                "annualized": _fmt_pct(record.get("annualized_return")),
                "sharpe": _fmt(record.get("sharpe"), 2),
                "turnover": _fmt_pct(record.get("turnover")),
                "drawdown": _fmt_pct(record.get("drawdown", record.get("max_drawdown"))),
                "tone": _tone(record.get("total_return", record.get("return"))),
            }
        )
    return result


def _render_plots(graph_data, plots_dir):
    """Render every chart the data supports; missing series simply drop their page."""

    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    equity = graph_data.get("equity_cny") or graph_data.get("equity") or []
    benchmark = graph_data.get("benchmark") or []
    excess = graph_data.get("excess") or []
    drawdown = graph_data.get("drawdown") or []
    daily_returns = graph_data.get("daily_returns") or []
    turnover = graph_data.get("turnover") or []
    exposure = graph_data.get("exposure") or []
    groups = graph_data.get("group_cumulative") or []

    for key, plot in (
        ("equity_curve", lambda: _plot_equity_curve(equity, benchmark, plots_dir)),
        ("excess_curve", lambda: _plot_excess_curve(excess, plots_dir)),
        ("drawdown", lambda: _plot_drawdown(drawdown, plots_dir)),
        ("monthly_excess", lambda: _plot_monthly_excess(excess, plots_dir)),
        ("monthly_heatmap", lambda: _plot_monthly_heatmap(daily_returns, plots_dir)),
        ("yearly_bar", lambda: _plot_yearly_bar(daily_returns, plots_dir)),
        ("rolling_sharpe", lambda: _plot_rolling_sharpe(daily_returns, plots_dir)),
        ("turnover", lambda: _plot_turnover(turnover, plots_dir)),
        ("exposure", lambda: _plot_exposure(exposure, plots_dir)),
        ("group_cumulative", lambda: _plot_group_cumulative(groups, plots_dir)),
    ):
        rendered = plot()
        if rendered:
            paths[key] = rendered
    return paths


def _plot_points(records, value_keys, *, scale=1.0):
    """``[(Timestamp, value)]`` sorted by date, skipping rows without a usable date/value."""

    points = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        try:
            date = pd.Timestamp(record.get("date"))
        except (TypeError, ValueError):
            continue
        if pd.isna(date):
            continue
        value = None
        for key in value_keys:
            value = _safe_float(record.get(key))
            if value is not None:
                break
        if value is None:
            continue
        points.append((date, value * scale))
    points.sort(key=lambda point: point[0])
    return points


def _save_figure(fig, plots_dir, name):
    path = Path(plots_dir) / name
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return f"plots/{name}"


def _title(ax, text):
    ax.set_title(text, color="#eee", fontsize=12, fontweight="bold", loc="left")


def _money_axis(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"¥{v:,.0f}"))


def _percent_axis(ax, digits=0):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.{digits}%}"))


def _plot_equity_curve(equity, benchmark, plots_dir):
    points = _plot_points(equity, ("equity_cny", "equity"))
    if not points:
        return ""
    dates = [point[0] for point in points]
    values = [point[1] for point in points]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(dates, values, color=PALETTE[0], linewidth=1.5, label="Strategy (raw portfolio)")

    benchmark_points = _plot_points(benchmark, ("benchmark_cny", "benchmark_equity"))
    if benchmark_points:
        ax.plot(
            [point[0] for point in benchmark_points],
            [point[1] for point in benchmark_points],
            color="#9aa5b1",
            linewidth=1.1,
            alpha=0.85,
            label="CSI 300",
        )
    _title(ax, "Equity Curve")
    ax.legend(
        loc="upper left",
        facecolor="#1a1a2e",
        edgecolor="#333",
        labelcolor="#ccc",
        framealpha=0.9,
    )
    _money_axis(ax)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "equity_curve.png")


def _plot_excess_curve(excess, plots_dir):
    points = _plot_points(excess, ("excess_cny", "excess_equity"))
    if not points:
        return ""
    dates = [point[0] for point in points]
    values = [point[1] for point in points]
    fig, ax = plt.subplots(figsize=(10, 2.9))
    ax.fill_between(dates, 0, values, color=PALETTE[1], alpha=0.15)
    ax.plot(dates, values, color=PALETTE[1], linewidth=1.4)
    ax.axhline(0, color="#555", linewidth=0.8)
    _title(ax, "Cumulative Excess Return — strategy minus CSI 300")
    _money_axis(ax)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "excess_curve.png")


def _plot_monthly_excess(excess, plots_dir):
    points = _plot_points(excess, ("excess_return",))
    if len(points) < 20:
        return ""
    frame = pd.DataFrame(points, columns=["date", "excess_return"])
    monthly = frame.groupby([frame["date"].dt.year, frame["date"].dt.month])[
        "excess_return"
    ].apply(lambda values: (1.0 + values).prod() - 1.0)
    if monthly.empty:
        return ""
    labels = [f"{year}-{month:02d}" for year, month in monthly.index]
    colors = [PALETTE[2] if value >= 0 else PALETTE[3] for value in monthly.values]

    fig, ax = plt.subplots(figsize=(10, 2.9))
    ax.bar(range(len(monthly)), monthly.values, color=colors, edgecolor="#333")
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_xticks(range(len(monthly)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6)
    _title(ax, "Monthly Excess Return — compounded inside each month")
    _percent_axis(ax)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "monthly_excess.png")


def _plot_drawdown(drawdown, plots_dir):
    points = _plot_points(drawdown, ("drawdown",))
    if not points:
        return ""
    dates = [point[0] for point in points]
    values = [point[1] for point in points]
    worst = min(values)
    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.fill_between(dates, 0, values, color=PALETTE[3], alpha=0.3)
    ax.plot(dates, values, color=PALETTE[3], linewidth=1)
    ax.annotate(
        f"max {worst:.1%}",
        xy=(dates[values.index(worst)], worst),
        xytext=(6, 6),
        textcoords="offset points",
        color=PALETTE[3],
        fontsize=8,
    )
    _title(ax, "Drawdown — arithmetic equity")
    _percent_axis(ax, digits=1)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "drawdown.png")


def _plot_turnover(turnover, plots_dir):
    points = _plot_points(turnover, ("turnover",))
    if len(points) < 10:
        return ""
    dates = [point[0] for point in points]
    values = [point[1] for point in points]
    rolling = pd.Series(values, index=pd.DatetimeIndex(dates)).rolling(20).mean()
    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.plot(dates, values, color=PALETTE[5], linewidth=0.8, alpha=0.45, label="daily")
    ax.plot(dates, rolling, color=PALETTE[5], linewidth=1.4, label="20-day average")
    _title(ax, "Turnover — share of capital traded per day")
    _percent_axis(ax)
    ax.legend(
        loc="upper left",
        facecolor="#1a1a2e",
        edgecolor="#333",
        labelcolor="#ccc",
        framealpha=0.9,
        fontsize=8,
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "turnover.png")


def _plot_exposure(exposure, plots_dir):
    long_points = _plot_points(exposure, ("long_exposure",))
    short_points = [
        (date, -value) for date, value in _plot_points(exposure, ("short_exposure",))
    ]
    if not long_points and not short_points:
        return ""
    fig, ax = plt.subplots(figsize=(10, 2.6))
    if long_points:
        ax.plot(
            [point[0] for point in long_points],
            [point[1] for point in long_points],
            color=PALETTE[2],
            linewidth=1.2,
            label="long exposure",
        )
    if short_points:
        ax.plot(
            [point[0] for point in short_points],
            [point[1] for point in short_points],
            color=PALETTE[3],
            linewidth=1.2,
            label="short exposure",
        )
    ax.axhline(0, color="#555", linewidth=0.8)
    _title(ax, "Exposure — share of capital held long and short")
    _percent_axis(ax)
    ax.legend(
        loc="upper left",
        facecolor="#1a1a2e",
        edgecolor="#333",
        labelcolor="#ccc",
        framealpha=0.9,
        fontsize=8,
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "exposure.png")


def _plot_group_cumulative(groups, plots_dir):
    records = []
    for record in groups or []:
        if not isinstance(record, dict):
            continue
        try:
            date = pd.Timestamp(record.get("date"))
        except (TypeError, ValueError):
            continue
        value = _safe_float(record.get("cumulative_return"))
        if pd.isna(date) or value is None:
            continue
        records.append(
            {"date": date, "group": str(record.get("group")), "cumulative_return": value}
        )
    frame = pd.DataFrame(records)
    if frame.empty or frame["group"].nunique() < 2:
        return ""
    fig, ax = plt.subplots(figsize=(10, 3))
    for index, (group, rows) in enumerate(frame.sort_values("date").groupby("group")):
        rows = rows.sort_values("date")
        ax.plot(
            rows["date"],
            rows["cumulative_return"],
            color=PALETTE[index % len(PALETTE)],
            linewidth=1.2,
            label=f"Group {group}",
        )
    ax.axhline(0, color="#555", linewidth=0.8)
    _title(ax, "Factor Groups — cumulative return")
    _percent_axis(ax)
    ax.legend(
        loc="upper left",
        ncol=2,
        facecolor="#1a1a2e",
        edgecolor="#333",
        labelcolor="#ccc",
        framealpha=0.9,
        fontsize=7,
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "group_cumulative.png")


def _returns_frame(daily_returns):
    records = []
    for record in daily_returns or []:
        if not isinstance(record, dict):
            continue
        try:
            date = pd.Timestamp(record.get("date"))
        except (TypeError, ValueError):
            continue
        value = _safe_float(record.get("daily_return", record.get("return")))
        if pd.isna(date) or value is None:
            continue
        records.append({"date": date, "daily_return": value})
    frame = pd.DataFrame(records, columns=["date", "daily_return"])
    return frame.sort_values("date").reset_index(drop=True)


def _plot_monthly_heatmap(daily_returns, plots_dir):
    frame = _returns_frame(daily_returns)
    if frame.empty:
        return ""
    frame["year"] = frame["date"].dt.year
    frame["month"] = frame["date"].dt.month
    monthly = (
        frame.groupby(["year", "month"])["daily_return"]
        .apply(lambda values: (1.0 + values).prod() - 1.0)
        .unstack(level=0)
    )
    if monthly.empty:
        return ""

    fig, ax = plt.subplots(figsize=(10, max(3.2, len(monthly) * 0.4)))
    im = ax.imshow(monthly.values, cmap="RdYlGn", aspect="auto", vmin=-0.15, vmax=0.15)
    ax.set_xticks(range(len(monthly.columns)))
    ax.set_xticklabels(monthly.columns, fontsize=8)
    ax.set_yticks(range(len(monthly.index)))
    ax.set_yticklabels(monthly.index, fontsize=8)
    for (row, column), value in np.ndenumerate(monthly.values):
        if pd.isna(value):
            continue
        ax.text(
            column,
            row,
            f"{value:.1%}",
            ha="center",
            va="center",
            fontsize=6,
            color="#101010",
        )
    _title(ax, "Monthly Returns Heatmap")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
    cbar.ax.tick_params(colors="#ccc")
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "monthly_heatmap.png")


def _plot_yearly_bar(daily_returns, plots_dir):
    frame = _returns_frame(daily_returns)
    if frame.empty:
        return ""
    yearly = frame.groupby(frame["date"].dt.year)["daily_return"].apply(
        lambda values: (1.0 + values).prod() - 1.0
    )
    if yearly.empty:
        return ""
    colors = [PALETTE[2] if value >= 0 else PALETTE[3] for value in yearly.values]

    fig, ax = plt.subplots(figsize=(10, 3.2))
    bars = ax.bar(yearly.index.astype(str), yearly.values, color=colors, edgecolor="#333")
    ax.axhline(0, color="#555", linewidth=0.8)
    for bar, value in zip(bars, yearly.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:+.1%}",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8,
            color="#ccc",
        )
    _title(ax, "Calendar Year Returns")
    _percent_axis(ax)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "yearly_bar.png")


def _plot_rolling_sharpe(daily_returns, plots_dir, window=60):
    frame = _returns_frame(daily_returns)
    if len(frame) <= window:
        return ""
    rolling = frame["daily_return"].rolling(window).apply(
        lambda values: np.mean(values) / (np.std(values) + 1e-10) * np.sqrt(252),
        raw=True,
    )

    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.plot(frame["date"], rolling, color=PALETTE[0], linewidth=1)
    ax.axhline(0, color="#555", linewidth=0.8)
    _title(ax, f"Rolling Sharpe — {window}-day window, annualized")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, plots_dir, "rolling_sharpe.png")


def _html_to_pdf(html, output_path, base_path=None):
    from weasyprint import HTML

    document = HTML(string=html, base_url=str(base_path) if base_path else None)
    document.write_pdf(str(output_path))
