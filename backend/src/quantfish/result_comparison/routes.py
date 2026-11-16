from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from quantfish.web_app.response_models import CompareResponse


router = APIRouter(prefix="/api/compare", tags=["comparison"])


@router.get("", response_model=CompareResponse, response_model_exclude_unset=True)
def compare_submissions(
    request: Request,
    submission_id: Annotated[list[str], Query(default_factory=list)],
    include_graph_data: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    services = request.app.state.services
    return services.comparison_service.compare(
        submission_id,
        include_graph_data=include_graph_data,
    )
