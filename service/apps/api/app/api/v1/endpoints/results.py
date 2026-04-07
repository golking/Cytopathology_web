from uuid import UUID

from fastapi import APIRouter

from app.schemas.errors import ErrorResponse
from app.schemas.result import AnalysisSessionResultsResponse
from app.services.result_service import get_analysis_session_results

router = APIRouter()


@router.get(
    "/analysis-sessions/{sessionId}/results",
    response_model=AnalysisSessionResultsResponse,
    summary="Получить результаты анализа по всему сеансу",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
    },
)
async def get_session_results(
    sessionId: UUID,
) -> AnalysisSessionResultsResponse:
    return get_analysis_session_results(session_id=sessionId)