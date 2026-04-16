from uuid import UUID

from app.core.config import settings


def build_asset_content_url(asset_public_id: UUID | None) -> str | None:
    if asset_public_id is None:
        return None

    return f"{settings.api_v1_prefix}/assets/{asset_public_id}/content"