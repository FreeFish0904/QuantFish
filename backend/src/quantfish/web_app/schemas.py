from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str
    status: str
    engine_version: str


class ReadinessCheckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    critical: bool
    ok: bool
    detail: str | None = None


class ReadyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str
    status: str
    engine_version: str
    checks: list[ReadinessCheckResponse]
