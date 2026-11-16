from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str
    status: str
    engine_version: str
