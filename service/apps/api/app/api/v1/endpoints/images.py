from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Response, UploadFile, status

from app.schemas.errors import ErrorResponse
from app.schemas.image import AnalysisImageRead
from app.services.image_service import (
    delete_analysis_session_image,
    get_analysis_session_image,
    list_analysis_session_images,
    upload_images_to_session,
)

router = APIRouter()


@router.get(
    "/analysis-sessions/{sessionId}/images",
    response_model=list[AnalysisImageRead],
    summary="Получить список изображений сеанса",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
    },
)
async def get_session_images(sessionId: UUID) -> list[AnalysisImageRead]:
    return list_analysis_session_images(session_id=sessionId)


@router.get(
    "/analysis-sessions/{sessionId}/images/{imageId}",
    response_model=AnalysisImageRead,
    summary="Получить одно изображение сеанса",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс или изображение не найдено"},
    },
)
async def get_session_image(
    sessionId: UUID,
    imageId: UUID,
) -> AnalysisImageRead:
    return get_analysis_session_image(
        session_id=sessionId,
        image_id=imageId,
    )


@router.delete(
    "/analysis-sessions/{sessionId}/images/{imageId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить изображение из сеанса",
    responses={
        404: {"model": ErrorResponse, "description": "Сеанс или изображение не найдено"},
        409: {"model": ErrorResponse, "description": "Сеанс уже запущен"},
    },
)
async def delete_session_image(
    sessionId: UUID,
    imageId: UUID,
) -> Response:
    delete_analysis_session_image(
        session_id=sessionId,
        image_id=imageId,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/analysis-sessions/{sessionId}/images",
    response_model=list[AnalysisImageRead],
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить одно или несколько изображений в сеанс",
    responses={
        400: {"model": ErrorResponse, "description": "Некорректный payload или файл"},
        404: {"model": ErrorResponse, "description": "Сеанс не найден"},
        409: {"model": ErrorResponse, "description": "Сеанс уже запущен"},
    },
)
async def upload_session_images(
    sessionId: UUID,
    files: Annotated[
        list[UploadFile],
        File(
            alias="files[]",
            description="Один или несколько файлов изображений",
        ),
    ],
) -> list[AnalysisImageRead]:
    return await upload_images_to_session(session_id=sessionId, files=files)