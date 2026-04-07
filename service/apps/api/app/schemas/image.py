from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import AnalysisImageStatus


class AnalysisImageRead(BaseModel):
    id: UUID
    image_index: int = Field(..., ge=1)
    original_filename: str
    status: AnalysisImageStatus
    mime_type: str
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, ge=1, le=4)
    error_message: str | None = None
    created_at: datetime