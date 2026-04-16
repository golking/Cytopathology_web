from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    SessionAlreadyStartedError,
    SessionHasNoImagesError,
    SessionNotFoundError,
    SessionStartConflictError,
    UnsupportedCellLineError,
    UnsupportedProfileError,
    UnsupportedVirusError,
)
from app.db.models import (
    AnalysisImage,
    AnalysisSession,
    CellLine,
    InferenceProfile,
    ProcessingJob,
    Virus,
)
from app.domain.enums import AnalysisImageStatus, AnalysisSessionStatus, ProcessingJobStatus
from app.schemas.catalog import CellLineRef, VirusRef
from app.schemas.session import (
    AnalysisSessionCreateRequest,
    AnalysisSessionDetailRead,
    AnalysisSessionListItem,
    AnalysisSessionProgress,
    AnalysisSessionRead,
    AnalysisSessionsListResponse,
    AnalysisSessionStartResponse,
)
from app.services.catalog_db_service import (
    get_supported_cell_line_by_code_from_db,
    get_supported_virus_by_code_from_db,
    resolve_supported_pair_from_db,
)


def _to_virus_ref(obj) -> VirusRef:
    return VirusRef(
        id=obj.id,
        code=obj.code,
        name=obj.name,
    )


def _to_cell_line_ref(obj) -> CellLineRef:
    return CellLineRef(
        id=obj.id,
        code=obj.code,
        name=obj.name,
    )


def calculate_session_counters(
    db: Session,
    session_db_id: int,
) -> tuple[int, int, int]:
    stmt = select(
        func.count(AnalysisImage.id),
        func.coalesce(
            func.sum(
                case(
                    (AnalysisImage.status == AnalysisImageStatus.COMPLETED.value, 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (AnalysisImage.status == AnalysisImageStatus.FAILED.value, 1),
                    else_=0,
                )
            ),
            0,
        ),
        ).where(AnalysisImage.session_id == session_db_id)

    total_images, completed_images, failed_images = db.execute(stmt).one()
    return int(total_images or 0), int(completed_images or 0), int(failed_images or 0)


def sync_session_counters(
    db: Session,
    session: AnalysisSession,
) -> tuple[int, int, int]:
    total_images, completed_images, failed_images = calculate_session_counters(
        db,
        session.id,
    )

    session.images_count = total_images
    session.completed_images_count = completed_images
    session.failed_images_count = failed_images
    session.summary_metrics = {
        "total_images": total_images,
        "completed_images": completed_images,
        "failed_images": failed_images,
    }

    return total_images, completed_images, failed_images


def _build_progress(
    total_images: int,
    completed_images: int,
    failed_images: int,
) -> AnalysisSessionProgress:
    done_images = completed_images + failed_images
    percent = 0 if total_images == 0 else min(100, int((done_images / total_images) * 100))

    return AnalysisSessionProgress(
        total_images=total_images,
        completed_images=completed_images,
        failed_images=failed_images,
        percent=percent,
    )


def get_session_record(
    db: Session,
    session_public_id: UUID,
    *,
    load_images: bool = False,
    load_results: bool = False,
    load_job: bool = False,
    load_profile: bool = False,
) -> AnalysisSession:
    options = [
        selectinload(AnalysisSession.virus),
        selectinload(AnalysisSession.cell_line),
    ]

    if load_job:
        options.append(selectinload(AnalysisSession.processing_job))

    if load_profile:
        options.append(
            selectinload(AnalysisSession.inference_profile).selectinload(
                InferenceProfile.classifier_model
            )
        )

    if load_images:
        options.extend(
            [
                selectinload(AnalysisSession.images).selectinload(AnalysisImage.original_asset),
                selectinload(AnalysisSession.images).selectinload(AnalysisImage.preprocessed_asset),
            ]
        )

        if load_results:
            options.append(
                selectinload(AnalysisSession.images).selectinload(AnalysisImage.result)
            )

    stmt = (
        select(AnalysisSession)
        .options(*options)
        .where(AnalysisSession.public_id == session_public_id)
        .limit(1)
    )

    session = db.scalar(stmt)
    if session is None:
        raise SessionNotFoundError(session_public_id)

    return session


def ensure_session_is_editable(session: AnalysisSession) -> None:
    if session.status != AnalysisSessionStatus.CREATED.value:
        raise SessionAlreadyStartedError(
            session_id=session.public_id,
            current_status=session.status,
        )


def _to_analysis_session_read(
    *,
    session: AnalysisSession,
    virus: VirusRef | None = None,
    cell_line: CellLineRef | None = None,
) -> AnalysisSessionRead:
    virus_ref = virus or _to_virus_ref(session.virus)
    cell_line_ref = cell_line or _to_cell_line_ref(session.cell_line)

    return AnalysisSessionRead(
        id=session.public_id,
        status=session.status,
        virus=virus_ref,
        cell_line=cell_line_ref,
        images_count=session.images_count,
        completed_images_count=session.completed_images_count,
        failed_images_count=session.failed_images_count,
        notes=session.notes,
        error_message=session.error_message,
        created_at=session.created_at,
        started_at=session.started_at,
        finished_at=session.finished_at,
    )

def _to_analysis_session_list_item(
    session: AnalysisSession,
) -> AnalysisSessionListItem:
    queued_at = None
    if session.processing_job is not None:
        queued_at = session.processing_job.created_at

    return AnalysisSessionListItem(
        id=session.public_id,
        status=session.status,
        virus=_to_virus_ref(session.virus),
        cell_line=_to_cell_line_ref(session.cell_line),
        images_count=session.images_count,
        completed_images_count=session.completed_images_count,
        failed_images_count=session.failed_images_count,
        notes=session.notes,
        error_message=session.error_message,
        created_at=session.created_at,
        queued_at=queued_at,
        started_at=session.started_at,
        finished_at=session.finished_at,
    )
    
def _to_analysis_session_detail(
    *,
    session: AnalysisSession,
    total_images: int,
    completed_images: int,
    failed_images: int,
) -> AnalysisSessionDetailRead:
    queued_at = None
    if session.processing_job is not None:
        queued_at = session.processing_job.created_at

    return AnalysisSessionDetailRead(
        id=session.public_id,
        status=session.status,
        virus=_to_virus_ref(session.virus),
        cell_line=_to_cell_line_ref(session.cell_line),
        progress=_build_progress(total_images, completed_images, failed_images),
        notes=session.notes,
        error_message=session.error_message,
        created_at=session.created_at,
        queued_at=queued_at,
        started_at=session.started_at,
        finished_at=session.finished_at,
    )


def create_analysis_session(
    payload: AnalysisSessionCreateRequest,
    db: Session,
    client_token: UUID | None = None,
) -> AnalysisSessionRead:
    virus = get_supported_virus_by_code_from_db(db, payload.virus_code)
    if virus is None:
        raise UnsupportedVirusError(payload.virus_code)

    cell_line = get_supported_cell_line_by_code_from_db(db, payload.cell_line_code)
    if cell_line is None:
        raise UnsupportedCellLineError(payload.cell_line_code)

    profile = resolve_supported_pair_from_db(
        db,
        payload.virus_code,
        payload.cell_line_code,
    )
    if profile is None:
        raise UnsupportedProfileError(payload.virus_code, payload.cell_line_code)

    now = datetime.now(timezone.utc)

    session = AnalysisSession(
        public_id=uuid4(),
        client_token=client_token,
        virus_id=profile.virus_id,
        cell_line_id=profile.cell_line_id,
        inference_profile_id=profile.inference_profile_id,
        status=AnalysisSessionStatus.CREATED.value,
        images_count=0,
        completed_images_count=0,
        failed_images_count=0,
        summary_metrics={
            "total_images": 0,
            "completed_images": 0,
            "failed_images": 0,
        },
        notes=payload.notes,
        error_message=None,
        created_at=now,
        started_at=None,
        finished_at=None,
    )

    db.add(session)
    db.commit()

    return AnalysisSessionRead(
        id=session.public_id,
        status=session.status,
        virus=profile.virus,
        cell_line=profile.cell_line,
        images_count=0,
        completed_images_count=0,
        failed_images_count=0,
        notes=session.notes,
        error_message=None,
        created_at=session.created_at,
        started_at=None,
        finished_at=None,
    )
    
def list_analysis_sessions(
    db: Session,
    *,
    client_token: UUID,
    session_status: AnalysisSessionStatus | None = None,
    virus_code: str | None = None,
    cell_line_code: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> AnalysisSessionsListResponse:
    filters = [AnalysisSession.client_token == client_token]

    if session_status is not None:
        filters.append(AnalysisSession.status == session_status.value)

    if virus_code is not None:
        filters.append(Virus.code == virus_code)

    if cell_line_code is not None:
        filters.append(CellLine.code == cell_line_code)

    total_stmt = (
        select(func.count(AnalysisSession.id))
        .join(AnalysisSession.virus)
        .join(AnalysisSession.cell_line)
        .where(*filters)
    )
    total = int(db.scalar(total_stmt) or 0)

    items_stmt = (
        select(AnalysisSession)
        .join(AnalysisSession.virus)
        .join(AnalysisSession.cell_line)
        .options(
            selectinload(AnalysisSession.virus),
            selectinload(AnalysisSession.cell_line),
            selectinload(AnalysisSession.processing_job),
        )
        .where(*filters)
        .order_by(AnalysisSession.created_at.desc(), AnalysisSession.id.desc())
        .limit(limit)
        .offset(offset)
    )

    sessions = list(db.scalars(items_stmt).all())

    return AnalysisSessionsListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_analysis_session_list_item(item) for item in sessions],
    )

def get_analysis_session(
    db: Session,
    session_id: UUID,
) -> AnalysisSessionDetailRead:
    session = get_session_record(
        db,
        session_id,
        load_job=True,
    )
    total_images, completed_images, failed_images = calculate_session_counters(
        db,
        session.id,
    )

    return _to_analysis_session_detail(
        session=session,
        total_images=total_images,
        completed_images=completed_images,
        failed_images=failed_images,
    )


def start_analysis_session(
    db: Session,
    session_id: UUID,
) -> AnalysisSessionStartResponse:
    session = get_session_record(
        db,
        session_id,
        load_images=True,
        load_job=True,
        load_profile=True,
    )

    if session.status != AnalysisSessionStatus.CREATED.value:
        raise SessionStartConflictError(
            session_id=session.public_id,
            current_status=session.status,
        )

    total_images, _, _ = sync_session_counters(db, session)
    if total_images == 0:
        db.rollback()
        raise SessionHasNoImagesError(session_id)

    if session.processing_job is not None:
        raise SessionStartConflictError(
            session_id=session.public_id,
            current_status=session.status,
        )

    queued_at = datetime.now(timezone.utc)

    for image in session.images:
        if image.status == AnalysisImageStatus.UPLOADED.value:
            image.status = AnalysisImageStatus.QUEUED.value
            image.error_message = None

    job = ProcessingJob(
        session_id=session.id,
        job_type="analysis",
        status=ProcessingJobStatus.QUEUED.value,
        attempt_no=1,
        worker_id=None,
        payload={
            "profile_key": session.inference_profile.profile_key,
            "virus_code": session.virus.code,
            "cell_line_code": session.cell_line.code,
            "image_ids": [str(image.public_id) for image in sorted(session.images, key=lambda x: x.image_index)],
            "images_count": total_images,
        },
        error_message=None,
        created_at=queued_at,
        started_at=None,
        finished_at=None,
    )

    db.add(job)

    session.status = AnalysisSessionStatus.QUEUED.value
    session.error_message = None
    sync_session_counters(db, session)

    db.commit()

    return AnalysisSessionStartResponse(
        id=session.public_id,
        status=session.status,
        queued_at=queued_at,
    )
    
    