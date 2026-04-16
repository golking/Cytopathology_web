from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.result import (
    AnalysisImageResultRead,
    AnalysisSessionResultsResponse,
    TimeClassificationResult,
    TimeClassificationTopPrediction,
)
from app.services.asset_url_service import build_asset_content_url
from app.services.session_service import get_analysis_session, get_session_record


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _build_time_classification_block(result_record) -> TimeClassificationResult | None:
    if result_record is None:
        return None

    predicted_class = result_record.predicted_time_class
    confidence = _to_float(result_record.predicted_time_confidence)

    if predicted_class is None or confidence is None:
        return None

    top2_raw = result_record.top2_predictions or []
    top2 = [
        TimeClassificationTopPrediction(
            predicted_class=str(item["predicted_class"]),
            confidence=float(item["confidence"]),
        )
        for item in top2_raw
        if item.get("predicted_class") is not None
        and item.get("confidence") is not None
    ]

    confidence_flag = result_record.confidence_flag

    return TimeClassificationResult(
        predicted_class=str(predicted_class),
        confidence=confidence,
        top2=top2,
        confidence_flag=str(confidence_flag) if confidence_flag is not None else None,
    )


def _build_image_result(image_record) -> AnalysisImageResultRead:
    result_record = image_record.result

    return AnalysisImageResultRead(
        image_id=image_record.public_id,
        image_index=image_record.image_index,
        original_filename=image_record.original_filename,
        status=image_record.status,
        original_url=build_asset_content_url(
            image_record.original_asset.public_id
            if image_record.original_asset is not None
            else None
        ),
        preview_url=build_asset_content_url(
            image_record.preprocessed_asset.public_id
            if image_record.preprocessed_asset is not None
            else None
        ),
        time_classification=_build_time_classification_block(result_record),
        warnings=[
            str(item)
            for item in (result_record.warnings or [])
        ] if result_record is not None else [],
        error_message=image_record.error_message,
        inference_time_ms=(
            result_record.inference_time_ms
            if result_record is not None
            else None
        ),
    )


def get_analysis_session_results(
    db: Session,
    session_id: UUID,
) -> AnalysisSessionResultsResponse:
    session_summary = get_analysis_session(db, session_id)
    session_record = get_session_record(
        db,
        session_id,
        load_images=True,
        load_results=True,
        load_job=True,
    )

    image_records = sorted(
        session_record.images,
        key=lambda item: item.image_index,
    )

    results = [
        _build_image_result(image_record)
        for image_record in image_records
    ]

    return AnalysisSessionResultsResponse(
        session=session_summary,
        results=results,
    )