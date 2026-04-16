from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import AnalysisImageStatus
from app.schemas.session import AnalysisSessionDetailRead


class TimeClassificationTopPrediction(BaseModel):
    predicted_class: str
    confidence: float = Field(..., ge=0, le=1)


class TimeClassificationResult(BaseModel):
    predicted_class: str
    confidence: float = Field(..., ge=0, le=1)
    top2: list[TimeClassificationTopPrediction] = Field(default_factory=list)
    confidence_flag: str | None = None


class AnalysisImageResultRead(BaseModel):
    image_id: UUID
    image_index: int = Field(..., ge=1)
    original_filename: str
    status: AnalysisImageStatus
    original_url: str | None = None
    preview_url: str | None = None
    time_classification: TimeClassificationResult | None = None
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    inference_time_ms: int | None = Field(default=None, ge=0)


class AnalysisSessionResultsResponse(BaseModel):
    session: AnalysisSessionDetailRead
    results: list[AnalysisImageResultRead]