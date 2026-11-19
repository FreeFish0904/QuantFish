"""HTTP request logging.

Every `/api/*` request gets one line with method, path, status, duration and a
request id that is echoed back in the `x-request-id` header, so a user report
("it failed around 14:03") can be matched to a backend line and the scoring
job it triggered.

Deliberately not logged: request bodies, uploaded strategies, cookies and
authorization headers.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from quantfish.observability import get_logger, log_event

_LOGGER = get_logger("web.request")
_QUIET_PATHS = frozenset({"/api/health", "/api/ready"})


def install_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=_elapsed_ms(started),
            )
            raise
        duration_ms = _elapsed_ms(started)
        if _should_log(request.url.path, response.status_code):
            level = _level_for(response.status_code)
            log_event(
                _LOGGER,
                level,
                "request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
        response.headers["x-request-id"] = request_id
        return response


def _should_log(path: str, status_code: int) -> bool:
    if not path.startswith("/api/"):
        return False
    if status_code >= 400:
        return True
    return path not in _QUIET_PATHS


def _level_for(status_code: int) -> int:
    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
