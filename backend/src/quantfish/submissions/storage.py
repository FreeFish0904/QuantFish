from __future__ import annotations

from pathlib import Path
import shutil

from quantfish.submissions.starter_strategy import starter_strategy_text as _starter_strategy_text


class SubmissionStorage:
    def __init__(self, runtime_root: Path | str, max_upload_bytes: int = 1_000_000):
        self.runtime_root = Path(runtime_root)
        self.max_upload_bytes = max_upload_bytes

    @property
    def submissions_root(self) -> Path:
        return self.runtime_root / "submissions"

    @property
    def reports_root(self) -> Path:
        return self.runtime_root / "reports"

    def submission_dir(self, submission_id: str) -> Path:
        return self.submissions_root / _safe_id(submission_id)

    def report_dir(self, submission_id: str) -> Path:
        return self.reports_root / _safe_id(submission_id)

    def prepare_report_dir(self, submission_id: str) -> Path:
        path = self.report_dir(submission_id)
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def store_strategy(self, submission_id: str, filename: str, content: bytes) -> Path:
        self.validate_strategy_upload(filename, content)
        path = self.submission_dir(submission_id) / "generate_signals.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read_strategy_text(self, strategy_path: Path | str) -> str:
        upload_root = self.submissions_root.resolve()
        path = Path(strategy_path)
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise FileNotFoundError(path) from exc
        if resolved == upload_root or upload_root not in resolved.parents:
            raise FileNotFoundError(path)
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(path)
        return resolved.read_text(encoding="utf-8")

    def validate_strategy_upload(self, filename: str, content: bytes) -> None:
        if Path(filename).suffix.lower() != ".py":
            raise ValueError("strategy upload must be a Python .py file")
        if len(content) > self.max_upload_bytes:
            raise ValueError(
                f"strategy upload exceeds {self.max_upload_bytes} bytes"
            )
        if not content:
            raise ValueError("strategy upload cannot be empty")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("strategy upload must be UTF-8 text") from exc
        try:
            compile(text, filename, "exec")
        except SyntaxError as exc:
            raise ValueError(f"invalid Python strategy: {exc.msg}") from exc

    def starter_strategy_text(self) -> str:
        return _starter_strategy_text()

    def quickstart_text(self) -> str:
        return (
            "Save your strategy as generate_signals.py, then run:\n\n"
            "conda activate QuantFish\n"
            "python -m pytest tests/test_factor_execution.py -v\n\n"
            "Your file must define generate_signals(data) and return code/score values.\n"
        )

    def delete_upload_files_safely(self, paths: list[str]) -> list[str]:
        deleted: list[str] = []
        upload_root = self.submissions_root.resolve()
        for raw_path in paths:
            path = Path(raw_path)
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved != upload_root and upload_root not in resolved.parents:
                continue
            if not resolved.exists() or not resolved.is_file():
                continue
            resolved.unlink()
            deleted.append(resolved.as_posix())
            _remove_empty_parents(resolved.parent, stop_at=upload_root)
        return deleted


def _safe_id(value: str) -> str:
    if not value or value in {".", ".."}:
        raise ValueError("submission id is required")
    if "/" in value or "\\" in value:
        raise ValueError("submission id cannot contain path separators")
    return value


def _remove_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path
    while current != stop_at and stop_at in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
