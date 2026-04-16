from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.services.asset_service import get_asset_content

router = APIRouter()


@router.get(
    "/assets/{assetId}/content",
    response_class=FileResponse,
    summary="Получить бинарное содержимое артефакта",
    responses={
        404: {"model": ErrorResponse, "description": "Артефакт не найден"},
    },
)
async def get_asset_content_endpoint(
    assetId: UUID,
    db: Session = Depends(get_db_session),
) -> FileResponse:
    return get_asset_content(
        db=db,
        asset_id=assetId,
    )