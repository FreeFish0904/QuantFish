"""Track which report build produced a cached ``report.pdf``.

Rendering a report is slow (matplotlib plots plus weasyprint layout) and the
result is cached next to the run artifacts. Stamping the build lets the download
route regenerate a report that was written by an older template instead of
serving stale layout forever. This module stays dependency-free so the route can
import it without pulling in the optional ``quantfish[pdf]`` extra.
"""

from __future__ import annotations

from pathlib import Path

PDF_REPORT_VERSION = "2026.11.18"
PDF_REPORT_FILE = "report.pdf"
PDF_REPORT_VERSION_FILE = "report.version"


def pdf_report_path(report_dir: Path | str) -> Path:
    """Path of the cached report inside ``report_dir``."""

    return Path(report_dir) / PDF_REPORT_FILE


def pdf_report_is_current(report_dir: Path | str) -> bool:
    """True when a cached PDF exists and was written by the current build."""

    directory = Path(report_dir)
    if not pdf_report_path(directory).is_file():
        return False
    try:
        stamp = (directory / PDF_REPORT_VERSION_FILE).read_text(encoding="utf-8")
    except OSError:
        return False
    return stamp.strip() == PDF_REPORT_VERSION


def mark_pdf_report_written(report_dir: Path | str) -> None:
    """Record that ``report.pdf`` now matches :data:`PDF_REPORT_VERSION`."""

    (Path(report_dir) / PDF_REPORT_VERSION_FILE).write_text(
        f"{PDF_REPORT_VERSION}\n", encoding="utf-8"
    )
