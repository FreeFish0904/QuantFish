from __future__ import annotations

from dataclasses import dataclass
import base64
import hmac
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request, Response

from quantfish.submissions.models import Team


PARTICIPANT_SESSION_COOKIE = "quantfish_submission_session"
PARTICIPANT_SESSION_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class ParticipantSession:
    team_id: str
    team_name: str


def authenticate_participant(request: Request, team_name: str, password: str) -> Team:
    team_repository = request.app.state.services.team_repository
    team = team_repository.resolve_login(team_name)
    if (
        team is None
        or team.archived_at is not None
        or not team_repository.verify_password(team.display_name, password)
    ):
        raise HTTPException(status_code=401, detail="invalid team credentials")
    return team


def set_participant_session_cookie(
    request: Request,
    response: Response,
    team_id: str,
) -> None:
    issued_at = str(int(time.time()))
    encoded_team_id = _encode_cookie_part(team_id)
    nonce = secrets.token_hex(12)
    signature = _session_signature(request, issued_at, encoded_team_id, nonce)
    response.set_cookie(
        PARTICIPANT_SESSION_COOKIE,
        f"{issued_at}.{encoded_team_id}.{nonce}.{signature}",
        max_age=PARTICIPANT_SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def clear_participant_session_cookie(response: Response) -> None:
    response.delete_cookie(PARTICIPANT_SESSION_COOKIE, path="/")


def current_participant_session(request: Request) -> ParticipantSession | None:
    cookie = request.cookies.get(PARTICIPANT_SESSION_COOKIE)
    if not cookie:
        return None
    try:
        issued_at_text, encoded_team_id, nonce, signature = cookie.split(".", 3)
        issued_at = int(issued_at_text)
        team_id = _decode_cookie_part(encoded_team_id)
    except (ValueError, UnicodeDecodeError):
        return None
    if issued_at + PARTICIPANT_SESSION_SECONDS < int(time.time()):
        return None
    expected = _session_signature(request, issued_at_text, encoded_team_id, nonce)
    if not hmac.compare_digest(signature, expected):
        return None

    team = request.app.state.services.team_repository.get(team_id)
    if team is None or team.archived_at is not None:
        return None
    return ParticipantSession(team_id=team.team_id, team_name=team.display_name)


def require_participant_session(request: Request) -> ParticipantSession:
    session = current_participant_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="team login required")
    return session


def _session_signature(
    request: Request,
    issued_at: str,
    encoded_team_id: str,
    nonce: str,
) -> str:
    secret = _session_secret(request.app.state.services.settings)
    message = f"{issued_at}.{encoded_team_id}.{nonce}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, "sha256").hexdigest()


def _session_secret(settings: Any) -> str:
    return getattr(settings, "participant_session_secret", settings.admin_session_secret)


def _encode_cookie_part(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _decode_cookie_part(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii")).decode("utf-8")
