from uuid import UUID

from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AssetNotFoundError
from app.db.models import FileAsset
from app.services.storage_service import resolve_storage_absolute_path


def get_asset_content(
    db: Session,
    asset_id: UUID,
) -> FileResponse:
    stmt = (
        select(FileAsset)
        .where(FileAsset.public_id == asset_id)
        .limit(1)
    )

    asset = db.scalar(stmt)
    if asset is None:
        raise AssetNotFoundError(asset_id)

    absolute_path = resolve_storage_absolute_path(asset.storage_path).resolve()

    try:
        absolute_path.relative_to(settings.storage_root.resolve())
    except ValueError:
        raise AssetNotFoundError(asset_id)

    if not absolute_path.exists() or not absolute_path.is_file():
        raise AssetNotFoundError(asset_id)

    return FileResponse(
        path=str(absolute_path),
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": "inline",
        },
    )