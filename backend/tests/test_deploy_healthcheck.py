from __future__ import annotations

import importlib.util
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEALTHCHECK_PATH = PROJECT_ROOT / "deploy" / "healthcheck.py"


def _load_healthcheck() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_healthcheck", HEALTHCHECK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


healthcheck = _load_healthcheck()


class _ReadinessHandler(BaseHTTPRequestHandler):
    """Answers every GET with a fixed status, like `/api/ready` does."""

    status = 200
    body = b'{"status": "ok"}'
    delay_seconds = 0.0

    def do_GET(self) -> None:
        if self.delay_seconds:
            threading.Event().wait(self.delay_seconds)
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args: object) -> None:
        """Keep the test output clean; the default writes to stderr."""


class _LocalServer(ThreadingHTTPServer):
    """`HTTPServer.server_bind` reverse-resolves the bind address; skip that."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


def _serve(
    status: int,
    *,
    body: bytes = b'{"status": "ok"}',
    delay_seconds: float = 0.0,
) -> tuple[ThreadingHTTPServer, str]:
    handler = type(
        "ReadinessHandler",
        (_ReadinessHandler,),
        {"body": body, "delay_seconds": delay_seconds, "status": status},
    )
    server = _LocalServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/api/ready"


def _stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def test_exits_zero_when_readiness_answers_200() -> None:
    server, url = _serve(200)
    try:
        assert healthcheck.main(["healthcheck.py", url]) == 0
    finally:
        _stop(server)


def test_exits_non_zero_and_reports_the_payload_when_readiness_answers_503(
    capsys: pytest.CaptureFixture[str],
) -> None:
    server, url = _serve(503, body=b'{"status": "unavailable", "checks": []}')
    try:
        assert healthcheck.main(["healthcheck.py", url]) == 1
    finally:
        _stop(server)

    stderr = capsys.readouterr().err
    assert "503" in stderr
    assert "unavailable" in stderr


def test_exits_non_zero_when_the_server_is_stopped() -> None:
    server, url = _serve(200)
    _stop(server)

    assert healthcheck.main(["healthcheck.py", url]) == 1


def test_exits_non_zero_when_the_probe_times_out(capsys: pytest.CaptureFixture[str]) -> None:
    server, url = _serve(200, delay_seconds=1.0)
    try:
        assert healthcheck.main(["healthcheck.py", url], timeout=0.05) == 1
    finally:
        _stop(server)

    assert "unreachable" in capsys.readouterr().err


def test_defaults_match_the_container_port_and_fit_the_compose_timeout() -> None:
    assert healthcheck.DEFAULT_URL == "http://127.0.0.1:8010/api/ready"
    # `deploy/docker-compose.yml` gives the probe 5s; leave headroom for the
    # docker CLI to kill it before that and report a timeout instead.
    assert healthcheck.DEFAULT_TIMEOUT_SECONDS <= 3
