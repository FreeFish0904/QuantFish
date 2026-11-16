"""PDF report generator for backtest results using matplotlib + weasyprint + jinja2."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

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
    "figure.dpi": 120,
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


def _fmt_int(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def generate_pdf_report(submission, report_dir, team_name=""):
    """Generate a PDF report for a completed submission.

    Args:
        submission: Submission dataclass with report_pdf_status/path/created_at fields.
        report_dir: Path to the report directory.
        team_name: Display name of the team.

    Returns:
        Path to the generated PDF file.
    """
    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)

    pdf_path = report_dir_path / "report.pdf"
    plots_dir = report_dir_path / "plots"
    plots_dir.mkdir(exist_ok=True)

    artifacts = _load_artifacts(report_dir_path)
    graph_data = _load_json(report_dir_path / "graph_data.json")
    summary = artifacts.get("summary", {})
    metrics = submission.metrics.to_dict() if submission.metrics else {}
    report_number = submission.submission_number or 0
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    plot_paths = _render_plots(graph_data, plots_dir)

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    context = {
        "submission_id": submission.submission_id,
        "submission_label": f"#{report_number}" if report_number else "—",
        "team_name": team_name or submission.team_id,
        "generated_at": generated_at,
        "data_track": submission.data_track.value,
        "cover_cards": _cover_cards(metrics, summary),
        "risk_table": _risk_rows(metrics, summary),
        "yearly_table": _yearly_rows(artifacts),
        "params": _submission_params(submission),
        "plots": plot_paths,
        "version": "quantfish-0.1.0",
    }

    html = template.render(**context)
    _html_to_pdf(html, pdf_path, base_path=report_dir_path)
    return pdf_path


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
    m = {**summary, **metrics}
    return [
        {"label": "Sharpe", "value": _fmt(m.get("sharpe"), 3)},
        {"label": "Annual Return", "value": _fmt_pct(m.get("annual_return"))},
        {"label": "Total Return", "value": _fmt_pct(m.get("total_return"))},
        {"label": "Max Drawdown", "value": _fmt_pct(m.get("max_drawdown"))},
        {"label": "Calmar", "value": _fmt(m.get("calmar"), 3)},
        {"label": "Avg Turnover", "value": _fmt_pct(m.get("average_turnover"))},
        {"label": "Win Rate", "value": _fmt_pct(m.get("win_rate"))},
        {"label": "Trading Days", "value": _fmt_int(m.get("trading_days"))},
        {"label": "Beta", "value": _fmt(m.get("beta"), 3)},
        {"label": "Info Ratio", "value": _fmt(m.get("information_ratio"), 3)},
    ]


def _risk_rows(metrics, summary):
    m = {**summary, **metrics}
    return [
        ("Annual Return", _fmt_pct(m.get("annual_return"))),
        ("Annual Volatility", _fmt_pct(m.get("annual_volatility", m.get("volatility")))),
        ("Max Drawdown", _fmt_pct(m.get("max_drawdown"))),
        ("Sharpe Ratio", _fmt(m.get("sharpe"), 3)),
        ("Calmar Ratio", _fmt(m.get("calmar"), 3)),
        ("Information Ratio", _fmt(m.get("information_ratio"), 3)),
        ("Win Rate", _fmt_pct(m.get("win_rate"))),
        ("Beta", _fmt(m.get("beta"), 3)),
        ("Tracking Error", _fmt_pct(m.get("tracking_error"))),
        ("Average Turnover", _fmt_pct(m.get("average_turnover"))),
    ]


def _yearly_rows(artifacts):
    rows = artifacts.get("performance_by_year", [])
    result = []
    for r in rows:
        result.append({
            "year": str(r.get("year", r.get("date", "—"))),
            "return": _fmt_pct(r.get("return", r.get("total_return"))),
            "sharpe": _fmt(r.get("sharpe"), 2),
            "drawdown": _fmt_pct(r.get("drawdown", r.get("max_drawdown"))),
        })
    return result


def _render_plots(graph_data, plots_dir):
    paths = {}
    equity = graph_data.get("equity_cny", graph_data.get("equity", []))
    drawdown = graph_data.get("drawdown", [])
    benchmark = graph_data.get("benchmark", [])
    daily_returns = graph_data.get("daily_returns", [])

    if equity:
        paths["equity_curve"] = _plot_equity_curve(equity, benchmark, plots_dir)
    if drawdown:
        paths["drawdown"] = _plot_drawdown(drawdown, plots_dir)
    if daily_returns:
        paths["monthly_heatmap"] = _plot_monthly_heatmap(daily_returns, plots_dir)
        paths["yearly_bar"] = _plot_yearly_bar(daily_returns, plots_dir)
        paths["rolling_sharpe"] = _plot_rolling_sharpe(daily_returns, plots_dir)
    return paths


def _plot_equity_curve(equity, benchmark, plots_dir):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    dates = [pd.Timestamp(r["date"]) for r in equity]
    values = [r.get("equity_cny", r.get("equity", 0)) for r in equity]
    ax.plot(dates, values, color="#4fc3f7", linewidth=1.5, label="Strategy")
    if benchmark:
        bm_dates = [pd.Timestamp(r["date"]) for r in benchmark]
        bm_vals = [r.get("benchmark_cny", r.get("benchmark_equity", 0)) for r in benchmark]
        ax.plot(bm_dates, bm_vals, color="#888", linewidth=1, alpha=0.7, label="Benchmark")
    ax.set_title("Equity Curve", color="#eee", fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", facecolor="#1a1a2e", edgecolor="#333", labelcolor="#ccc")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"¥{v:,.0f}"))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = plots_dir / "equity_curve.png"
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "plots/equity_curve.png"


def _plot_drawdown(drawdown, plots_dir):
    fig, ax = plt.subplots(figsize=(10, 3))
    dates = [pd.Timestamp(r["date"]) for r in drawdown]
    values = [r.get("drawdown", 0) for r in drawdown]
    ax.fill_between(dates, 0, values, color="#ef5350", alpha=0.3)
    ax.plot(dates, values, color="#ef5350", linewidth=1)
    ax.set_title("Drawdown", color="#eee", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = plots_dir / "drawdown.png"
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "plots/drawdown.png"


def _plot_monthly_heatmap(daily_returns, plots_dir):
    df = pd.DataFrame(daily_returns)
    if df.empty or "date" not in df.columns:
        return ""
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return_col = next((c for c in ["daily_return", "return"] if c in df.columns), df.columns[-1])
    monthly = df.groupby(["year", "month"])[return_col].apply(
        lambda x: (1 + x).prod() - 1
    ).unstack(level=0)

    fig, ax = plt.subplots(figsize=(10, max(4, len(monthly) * 0.4)))
    im = ax.imshow(monthly.values, cmap="RdYlGn", aspect="auto", vmin=-0.15, vmax=0.15)
    ax.set_xticks(range(len(monthly.columns)))
    ax.set_xticklabels(monthly.columns, rotation=0, fontsize=8)
    ax.set_yticks(range(len(monthly.index)))
    ax.set_yticklabels(monthly.index, fontsize=8)
    ax.set_title("Monthly Returns Heatmap", color="#eee", fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
    cbar.ax.tick_params(colors="#ccc")
    fig.tight_layout()
    path = plots_dir / "monthly_heatmap.png"
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "plots/monthly_heatmap.png"


def _plot_yearly_bar(daily_returns, plots_dir):
    df = pd.DataFrame(daily_returns)
    if df.empty:
        return ""
    df["date"] = pd.to_datetime(df["date"])
    return_col = next((c for c in ["daily_return", "return"] if c in df.columns), df.columns[-1])
    yearly = df.groupby(df["date"].dt.year)[return_col].apply(
        lambda x: (1 + x).prod() - 1
    )
    colors = ["#4fc3f7" if v >= 0 else "#ef5350" for v in yearly.values]
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(yearly.index.astype(str), yearly.values, color=colors, edgecolor="#333")
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title("Yearly Returns", color="#eee", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
    for bar, val in zip(bars, yearly.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{val:.1%}", ha="center", va="bottom" if val >= 0 else "top",
                fontsize=8, color="#ccc")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = plots_dir / "yearly_bar.png"
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "plots/yearly_bar.png"


def _plot_rolling_sharpe(daily_returns, plots_dir, window=60):
    df = pd.DataFrame(daily_returns)
    if df.empty:
        return ""
    return_col = next((c for c in ["daily_return", "return"] if c in df.columns), df.columns[-1])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    returns = pd.to_numeric(df[return_col], errors="coerce").fillna(0)
    rolling = returns.rolling(window).apply(
        lambda x: np.mean(x) / (np.std(x) + 1e-10) * np.sqrt(252), raw=True
    )
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(df["date"], rolling, color="#4fc3f7", linewidth=1)
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title(f"Rolling Sharpe ({window}-day)", color="#eee", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = plots_dir / "rolling_sharpe.png"
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "plots/rolling_sharpe.png"


def _html_to_pdf(html, output_path, base_path=None):
    from weasyprint import HTML
    doc = HTML(string=html, base_url=str(base_path) if base_path else None)
    doc.write_pdf(str(output_path))
