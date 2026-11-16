from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
THIS_FILE = Path(__file__).name
# The legacy project name is assembled from parts so that this guard file never
# matches itself while scanning the repository.
LEGACY_TOKENS = ("sick" + "fun", "Sick" + "Fun", "SICK" + "FUN")


def test_repository_uses_quantfish_name_consistently() -> None:
    current_files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=PROJECT_ROOT,
        text=True,
    ).splitlines()

    offenders = []
    for relative_path in current_files:
        path = PROJECT_ROOT / relative_path
        if path.name == THIS_FILE:
            continue
        if not path.exists() or path.is_dir():
            continue
        if any(token in relative_path for token in LEGACY_TOKENS):
            offenders.append(relative_path)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(token in text for token in LEGACY_TOKENS):
            offenders.append(relative_path)

    assert offenders == []


def test_backend_package_uses_quantfish_module_name() -> None:
    package_dir = PROJECT_ROOT / "backend" / "src"
    assert (package_dir / "quantfish" / "__init__.py").is_file()
    package_dirs = [
        path.name
        for path in package_dir.iterdir()
        if path.is_dir() and not path.name.endswith(".egg-info")
    ]
    assert package_dirs == ["quantfish"]
