from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from quantfish.submissions.participant_session import (
    authenticate_participant,
    clear_participant_session_cookie,
    current_participant_session,
    set_participant_session_cookie,
)
from quantfish.web_app.response_models import ParticipantSessionResponse

router = APIRouter(prefix="/api/session", tags=["session"])


class ParticipantLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    team_name: str
    password: str


@router.post("/login", response_model=ParticipantSessionResponse)
def participant_login(
    request: Request,
    response: Response,
    payload: ParticipantLoginRequest,
) -> dict[str, str | bool]:
    team = authenticate_participant(request, payload.team_name, payload.password)
    set_participant_session_cookie(request, response, team.team_id)
    return {
        "authenticated": True,
        "team_id": team.team_id,
        "team_name": team.display_name,
    }


@router.get("", response_model=ParticipantSessionResponse)
def participant_session(request: Request) -> dict[str, str | bool | None]:
    session = current_participant_session(request)
    if session is None:
        return {"authenticated": False, "team_id": None, "team_name": None}
    return {
        "authenticated": True,
        "team_id": session.team_id,
        "team_name": session.team_name,
    }


@router.post("/logout", response_model=ParticipantSessionResponse)
def participant_logout(response: Response) -> dict[str, bool | None]:
    clear_participant_session_cookie(response)
    return {"authenticated": False, "team_id": None, "team_name": None}
