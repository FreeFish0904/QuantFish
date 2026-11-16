from __future__ import annotations

import hmac
import secrets
import time

from fastapi import HTTPException, Request, Response


ADMIN_SESSION_COOKIE = "quantfish_admin_session"
ADMIN_SESSION_SECONDS = 12 * 60 * 60


def verify_admin_password(request: Request, supplied: str) -> bool:
    expected = request.app.state.services.settings.admin_password
    return hmac.compare_digest(supplied, expected)


def set_admin_session_cookie(request: Request, response: Response) -> None:
    issued_at = str(int(time.time()))
    nonce = secrets.token_hex(12)
    signature = _session_signature(request, issued_at, nonce)
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        f"{issued_at}.{nonce}.{signature}",
        max_age=ADMIN_SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def clear_admin_session_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")


def has_admin_session(request: Request) -> bool:
    cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not cookie:
        return False
    try:
        issued_at_text, nonce, signature = cookie.split(".", 2)
        issued_at = int(issued_at_text)
    except ValueError:
        return False
    if issued_at + ADMIN_SESSION_SECONDS < int(time.time()):
        return False
    expected = _session_signature(request, issued_at_text, nonce)
    return hmac.compare_digest(signature, expected)


def require_admin_session(request: Request) -> None:
    if has_admin_session(request):
        return
    raise HTTPException(status_code=401, detail="admin login required")


def _session_signature(request: Request, issued_at: str, nonce: str) -> str:
    secret = request.app.state.services.settings.admin_session_secret
    message = f"{issued_at}.{nonce}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, "sha256").hexdigest()
