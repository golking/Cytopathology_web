from uuid import UUID

from app.data.result_store import RESULT_STORE
from app.schemas.result import (
    AnalysisImageResultRead,
    AnalysisSessionResultsResponse,
    TimeClassificationResult,
    TimeClassificationTopPrediction,
)
from app.services.session_service import (
    get_analysis_session,
    get_session_image_records,
    get_session_record,
)


def _build_time_classification_block(
    result_record: dict | None,
) -> TimeClassificationResult | None:
    if result_record is None:
        return None

    predicted_class = result_record.get("predicted_time_class")
    confidence = result_record.get("predicted_time_confidence")

    if predicted_class is None or confidence is None:
        return None

    top2_raw = result_record.get("top2_predictions") or []
    top2 = [
        TimeClassificationTopPrediction(
            predicted_class=item["predicted_class"],
            confidence=item["confidence"],
        )
        for item in top2_raw
        if item.get("predicted_class") is not None
        and item.get("confidence") is not None
    ]

    confidence_flag = result_record.get("confidence_flag")

    return TimeClassificationResult(
        predicted_class=str(predicted_class),
        confidence=float(confidence),
        top2=top2,
        confidence_flag=(
            str(confidence_flag)
            if confidence_flag is not None
            else None
        ),
    )


def _build_image_result(image_record: dict) -> AnalysisImageResultRead:
    result_record = RESULT_STORE.get(image_record["id"])

    return AnalysisImageResultRead(
        image_id=image_record["id"],
        image_index=image_record["image_index"],
        original_filename=image_record["original_filename"],
        status=image_record["status"],
        time_classification=_build_time_classification_block(result_record),
        warnings=[
            str(item)
            for item in (result_record.get("warnings") or [])
        ] if result_record else [],
        error_message=image_record.get("error_message"),
        inference_time_ms=(
            result_record.get("inference_time_ms")
            if result_record is not None
            else None
        ),
    )


def get_analysis_session_results(
    session_id: UUID,
) -> AnalysisSessionResultsResponse:
    session_summary = get_analysis_session(session_id)
    session_record = get_session_record(session_id)

    image_records = sorted(
        get_session_image_records(session_record),
        key=lambda item: item["image_index"],
    )

    results = [
        _build_image_result(image_record)
        for image_record in image_records
    ]

    return AnalysisSessionResultsResponse(
        session=session_summary,
        results=results,
    )