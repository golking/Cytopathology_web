from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status as http_status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.domain.enums import AnalysisSessionStatus
from app.schemas.errors import ErrorResponse
from app.schemas.session import (
    AnalysisSessionCreateRequest,
    AnalysisSessionDetailRead,
    AnalysisSessionRead,
    AnalysisSessionsListResponse,
    AnalysisSessionStartResponse,
)
from app.services.session_service import (
    create_analysis_session,
    get_analysis_session,
    list_analysis_sessions,
    start_analysis_session,
)

router = APIRouter()


@router.get(
    "/analysis-sessions",
    response_model=AnalysisSessionsListResponse,
    summary="Получить историю сеансов по client token",
    responses={
        400: {"model": ErrorResponse, "description": "Некорректные параметры запроса"},
    },
)
async def get_sessions(
    x_client_token: Annotated[UUID, Header(alias="X-Client-Token")],
    db: Session = Depends(get_db_session),
    session_status: Annotated[
        AnalysisSessionStatus | None,
        Query(alias="status", description="Опциональный фильтр по статусу"),
    ] = None,
    virus_code: Annotated[
        str | None,
        Query(description="Опциональный фильтр по коду вируса"),
    ] = None,
    cell_line_code: Annotated[
        str | None,
        Query(description="Опциональный фильтр по коду клеточной линии"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Размер страницы"),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Смещение"),
    ] = 0,
) -> AnalysisSessionsListResponse:
    return list_analysis_sessions(
        db=db,
        client_token=x_client_token,
        session_status=session_status,
        virus_code=virus_code,
        cell_line_code=cell_line_code,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/analysis-sessions",
    response_model=AnalysisSessionRead,
    status_code=http_status.HTTP_201_CREATED,
    summary="Создать новый сеанс анализа",
    responses={
        400: {"model": ErrorResponse, "description": "Некорректные поля запроса"},
        422: {"model": ErrorResponse, "description": "Неподдерживаемая конфигурация"},
    },
)
async def create_session(
    payload: AnalysisSessionCreateRequest,
    x_client_token: Annotated[UUID | None, Header(alias="X-Client-Token")] = None,
    db: Session = Depends(get_db_session),
) -> AnalysisSessionRead:
    return create_analysis_session(
        payload=payload,
        db=db,
        client_token=x_client_token,
    )


@router.get(
    "/analysis-sessions/{sessionId}",
    response_model=AnalysisSessionDetailRead,
    summary="Получить один сеанс и его текущий статус",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
    },
)
async def get_session(
    sessionId: UUID,
    db: Session = Depends(get_db_session),
) -> AnalysisSessionDetailRead:
    return get_analysis_session(
        db=db,
        session_id=sessionId,
    )


@router.post(
    "/analysis-sessions/{sessionId}/start",
    response_model=AnalysisSessionStartResponse,
    summary="Поставить сеанс в очередь на обработку",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
        409: {"model": ErrorResponse, "description": "Конфликт статуса сеанса"},
    },
)
async def start_session(
    sessionId: UUID,
    db: Session = Depends(get_db_session),
) -> AnalysisSessionStartResponse:
    return start_analysis_session(
        db=db,
        session_id=sessionId,
    )