from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import AnalysisSessionStatus
from app.schemas.catalog import CellLineRef, VirusRef


class AnalysisSessionCreateRequest(BaseModel):
    virus_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_]+$",
    )
    cell_line_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9_\-]+$",
    )
    notes: str | None = Field(
        default=None,
        max_length=4000,
    )


class AnalysisSessionRead(BaseModel):
    id: UUID
    status: AnalysisSessionStatus
    virus: VirusRef
    cell_line: CellLineRef
    images_count: int = Field(..., ge=0)
    completed_images_count: int = Field(..., ge=0)
    failed_images_count: int = Field(..., ge=0)
    notes: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisSessionProgress(BaseModel):
    total_images: int = Field(..., ge=0)
    completed_images: int = Field(..., ge=0)
    failed_images: int = Field(..., ge=0)
    percent: int = Field(..., ge=0, le=100)


class AnalysisSessionDetailRead(BaseModel):
    id: UUID
    status: AnalysisSessionStatus
    virus: VirusRef
    cell_line: CellLineRef
    progress: AnalysisSessionProgress
    notes: str | None = None
    error_message: str | None = None
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisSessionStartResponse(BaseModel):
    id: UUID
    status: AnalysisSessionStatus
    queued_at: datetime
    
class AnalysisSessionListItem(BaseModel):
    id: UUID
    status: AnalysisSessionStatus
    virus: VirusRef
    cell_line: CellLineRef
    images_count: int = Field(..., ge=0)
    completed_images_count: int = Field(..., ge=0)
    failed_images_count: int = Field(..., ge=0)
    notes: str | None = None
    error_message: str | None = None
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisSessionsListResponse(BaseModel):
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    items: list[AnalysisSessionListItem]