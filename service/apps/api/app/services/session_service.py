from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import (
    SessionAlreadyStartedError,
    SessionHasNoImagesError,
    SessionNotFoundError,
    SessionStartConflictError,
    UnsupportedCellLineError,
    UnsupportedProfileError,
    UnsupportedVirusError,
)
from app.data.image_store import IMAGE_STORE
from app.data.job_store import JOB_STORE
from app.data.session_store import SESSION_STORE
from app.domain.enums import AnalysisImageStatus, AnalysisSessionStatus
from app.schemas.session import (
    AnalysisSessionCreateRequest,
    AnalysisSessionDetailRead,
    AnalysisSessionProgress,
    AnalysisSessionRead,
    AnalysisSessionStartResponse,
)
from app.services.catalog_service import (
    get_profile_for_pair,
    get_supported_cell_line_by_code,
    get_supported_virus_by_code,
)
from app.services.job_service import create_analysis_job


def _enum_value(
    value: AnalysisSessionStatus | AnalysisImageStatus | str | None,
) -> str | None:
    if value is None:
        return None

    if isinstance(value, (AnalysisSessionStatus, AnalysisImageStatus)):
        return value.value

    return str(value)


def create_analysis_session(
    payload: AnalysisSessionCreateRequest,
    client_token: UUID | None = None,
) -> AnalysisSessionRead:
    virus = get_supported_virus_by_code(payload.virus_code)
    if virus is None:
        raise UnsupportedVirusError(payload.virus_code)

    cell_line = get_supported_cell_line_by_code(payload.cell_line_code)
    if cell_line is None:
        raise UnsupportedCellLineError(payload.cell_line_code)

    profile = get_profile_for_pair(payload.virus_code, payload.cell_line_code)
    if profile is None:
        raise UnsupportedProfileError(payload.virus_code, payload.cell_line_code)

    session_id = uuid4()
    now = datetime.now(timezone.utc)

    record = {
        "id": session_id,
        "status": AnalysisSessionStatus.CREATED,
        "virus": virus.model_dump(),
        "cell_line": cell_line.model_dump(),
        "profile_key": profile.profile_key,
        "image_ids": [],
        "images_count": 0,
        "completed_images_count": 0,
        "failed_images_count": 0,
        "notes": payload.notes,
        "error_message": None,
        "created_at": now,
        "queued_at": None,
        "started_at": None,
        "finished_at": None,
        "client_token": client_token,
        "job_id": None,
    }

    SESSION_STORE[session_id] = record
    return AnalysisSessionRead.model_validate(record)


def get_session_record(session_id: UUID) -> dict:
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def get_session_image_records(session: dict) -> list[dict]:
    return [
        IMAGE_STORE[image_id]
        for image_id in session.get("image_ids", [])
        if image_id in IMAGE_STORE
    ]


def refresh_session_counters(session: dict) -> None:
    image_records = get_session_image_records(session)

    completed_images_count = sum(
        1
        for image in image_records
        if _enum_value(image.get("status")) == AnalysisImageStatus.COMPLETED.value
    )
    failed_images_count = sum(
        1
        for image in image_records
        if _enum_value(image.get("status")) == AnalysisImageStatus.FAILED.value
    )

    session["images_count"] = len(image_records)
    session["completed_images_count"] = completed_images_count
    session["failed_images_count"] = failed_images_count


def build_session_progress(session: dict) -> AnalysisSessionProgress:
    refresh_session_counters(session)

    total_images = session["images_count"]
    completed_images = session["completed_images_count"]
    failed_images = session["failed_images_count"]

    done_images = completed_images + failed_images
    percent = 0 if total_images == 0 else min(100, int((done_images / total_images) * 100))

    return AnalysisSessionProgress(
        total_images=total_images,
        completed_images=completed_images,
        failed_images=failed_images,
        percent=percent,
    )


def get_analysis_session(session_id: UUID) -> AnalysisSessionDetailRead:
    session = get_session_record(session_id)
    progress = build_session_progress(session)

    return AnalysisSessionDetailRead(
        id=session["id"],
        status=session["status"],
        virus=session["virus"],
        cell_line=session["cell_line"],
        progress=progress,
        notes=session.get("notes"),
        error_message=session.get("error_message"),
        created_at=session["created_at"],
        queued_at=session.get("queued_at"),
        started_at=session.get("started_at"),
        finished_at=session.get("finished_at"),
    )


def ensure_session_is_editable(session: dict) -> None:
    current_status = _enum_value(session["status"])

    if current_status != AnalysisSessionStatus.CREATED.value:
        raise SessionAlreadyStartedError(
            session_id=session["id"],
            current_status=current_status or "unknown",
        )


def start_analysis_session(session_id: UUID) -> AnalysisSessionStartResponse:
    session = get_session_record(session_id)
    refresh_session_counters(session)

    current_status = _enum_value(session["status"])
    if current_status != AnalysisSessionStatus.CREATED.value:
        raise SessionStartConflictError(
            session_id=session["id"],
            current_status=current_status or "unknown",
        )

    image_records = get_session_image_records(session)
    if not image_records:
        raise SessionHasNoImagesError(session_id)

    previous_session_status = session["status"]
    previous_queued_at = session.get("queued_at")
    previous_job_id = session.get("job_id")
    previous_image_statuses = {
        image["id"]: image["status"]
        for image in image_records
    }

    queued_at = datetime.now(timezone.utc)
    created_job_id: UUID | None = None

    try:
        for image in image_records:
            image["status"] = AnalysisImageStatus.QUEUED

        session["status"] = AnalysisSessionStatus.QUEUED
        session["queued_at"] = queued_at

        job_record = create_analysis_job(session, queued_at=queued_at)
        created_job_id = job_record["id"]
        session["job_id"] = created_job_id

        refresh_session_counters(session)

        return AnalysisSessionStartResponse(
            id=session["id"],
            status=session["status"],
            queued_at=queued_at,
        )

    except Exception:
        session["status"] = previous_session_status
        session["queued_at"] = previous_queued_at
        session["job_id"] = previous_job_id

        for image in image_records:
            image["status"] = previous_image_statuses[image["id"]]

        if created_job_id is not None:
            JOB_STORE.pop(created_job_id, None)

        refresh_session_counters(session)
        raise