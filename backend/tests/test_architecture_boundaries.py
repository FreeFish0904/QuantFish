import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "backend" / "src" / "quantfish"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_public_runner_does_not_import_legacy_backtest_modules() -> None:
    imports = _imports(PACKAGE_ROOT / "backtest" / "runner.py")

    assert "wsc_backtest" not in imports
    assert "utils" not in imports


def test_pure_factor_execution_modules_do_not_import_report_writer() -> None:
    factor_execution_dir = PACKAGE_ROOT / "factor_execution"
    imports = {
        imported
        for path in factor_execution_dir.glob("*.py")
        if "report" not in path.stem
        for imported in _imports(path)
    }

    assert "quantfish.backtest.report_writer" not in imports
