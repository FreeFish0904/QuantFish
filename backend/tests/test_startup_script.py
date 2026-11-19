import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_startup_script_exposes_expected_modes_and_commands() -> None:
    script = PROJECT_ROOT / "scripts" / "start-quantfish.sh"

    mode = script.stat().st_mode
    text = script.read_text(encoding="utf-8")

    assert mode & stat.S_IXUSR
    assert "--mode setup|dev|prod|verify" in text
    assert "conda run -n" in text
    assert "quantfish-web" in text
    assert "npm --prefix frontend" in text
    assert 'HOST="127.0.0.1"' in text
    assert "Use 0.0.0.0 explicitly for LAN access" in text


def test_startup_script_waits_for_http_readiness_before_printing_urls() -> None:
    script = PROJECT_ROOT / "scripts" / "start-quantfish.sh"
    text = script.read_text(encoding="utf-8")

    assert "wait_for_http" in text
    assert "/api/health" in text
    assert "curl -fsS" in text
    wait_for_http = text[text.index("wait_for_http()") : text.index("wait_for_servers()")]
    assert wait_for_http.index("server_died") < wait_for_http.index("curl -fsS")
    wait_for_servers = text[text.index("wait_for_servers()") :]
    assert wait_for_servers.index('wait_for_http "backend"') < wait_for_servers.index(
        "print_urls"
    )


def test_startup_script_waits_for_backend_before_starting_frontend_dev() -> None:
    script = PROJECT_ROOT / "scripts" / "start-quantfish.sh"
    text = script.read_text(encoding="utf-8")

    dev_block = text[text.index("dev)") : text.index(";;", text.index("dev)"))]
    assert 'wait_for_http "backend"' in dev_block
    assert (
        dev_block.index("start_backend")
        < dev_block.index('wait_for_http "backend"')
        < dev_block.index("start_frontend_dev")
    )


def test_startup_script_secures_admin_password_before_startup() -> None:
    script = PROJECT_ROOT / "scripts" / "start-quantfish.sh"
    text = script.read_text(encoding="utf-8")

    assert "ensure_admin_password" in text
    assert "QUANTFISH_ADMIN_PASSWORD" in text
    assert "QUANTFISH_ADMIN_SESSION_SECRET" in text
    assert "QUANTFISH_PARTICIPANT_SESSION_SECRET" in text
    admin_password_block = text[
        text.index("ensure_admin_password()") : text.index("run_verify()")
    ]
    assert 'QUANTFISH_ADMIN_PASSWORD="quantfish-admin"' not in admin_password_block
    assert "GENERATED_ADMIN_PASSWORD" in admin_password_block
    assert "token_urlsafe" in admin_password_block
    dev_block = text[text.index("dev)") : text.index(";;", text.index("dev)"))]
    prod_block = text[text.index("prod)") : text.index(";;", text.index("prod)"))]
    assert dev_block.index("ensure_admin_password") < dev_block.index("start_backend")
    assert prod_block.index("ensure_admin_password") < prod_block.index("start_backend")


def test_server_startup_script_uses_project_venv_and_generated_credentials() -> None:
    script = PROJECT_ROOT / "scripts" / "start-quantfish-server.sh"

    mode = script.stat().st_mode
    text = script.read_text(encoding="utf-8")

    assert mode & stat.S_IXUSR
    assert 'source "./.venv/bin/activate"' in text
    assert "conda run -n" not in text
    assert "ensure_credentials" in text
    assert "token_urlsafe" in text
    assert "QUANTFISH_ADMIN_SESSION_SECRET" in text
    assert "QUANTFISH_PARTICIPANT_SESSION_SECRET" in text
    assert 'HOST="127.0.0.1"' in text
    assert "quantfish-web" in text
    assert "--runtime-root" in text
    assert "runs/web_platform" in text
    assert 'BACKEND_PORT="7860"' in text
    assert "FastAPI port. Default: 7860" in text
