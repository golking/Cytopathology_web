from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status

from app.schemas.errors import ErrorResponse
from app.schemas.session import (
    AnalysisSessionCreateRequest,
    AnalysisSessionDetailRead,
    AnalysisSessionRead,
    AnalysisSessionStartResponse,
)
from app.services.session_service import (
    create_analysis_session,
    get_analysis_session,
    start_analysis_session,
)

router = APIRouter()


@router.post(
    "/analysis-sessions",
    response_model=AnalysisSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый сеанс анализа",
    responses={
        400: {"model": ErrorResponse, "description": "Некорректные поля запроса"},
        422: {"model": ErrorResponse, "description": "Неподдерживаемая конфигурация"},
    },
)
async def create_session(
    payload: AnalysisSessionCreateRequest,
    x_client_token: Annotated[UUID | None, Header(alias="X-Client-Token")] = None,
) -> AnalysisSessionRead:
    return create_analysis_session(payload=payload, client_token=x_client_token)


@router.get(
    "/analysis-sessions/{sessionId}",
    response_model=AnalysisSessionDetailRead,
    summary="Получить один сеанс и его текущий статус",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
    },
)
async def get_session(sessionId: UUID) -> AnalysisSessionDetailRead:
    return get_analysis_session(session_id=sessionId)


@router.post(
    "/analysis-sessions/{sessionId}/start",
    response_model=AnalysisSessionStartResponse,
    summary="Поставить сеанс в очередь на обработку",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
        409: {"model": ErrorResponse, "description": "Конфликт статуса сеанса"},
    },
)
async def start_session(sessionId: UUID) -> AnalysisSessionStartResponse:
    return start_analysis_session(session_id=sessionId)