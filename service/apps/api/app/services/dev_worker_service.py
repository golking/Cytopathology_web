import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    AnalysisImage,
    AnalysisSession,
    ImageAnalysisResult,
    InferenceProfile,
    ProcessingJob,
)
from app.db.session import get_session_factory
from app.domain.enums import (
    AnalysisImageStatus,
    AnalysisSessionStatus,
    ProcessingJobStatus,
)
from app.services.inference_service import run_classification_inference
from app.services.session_service import sync_session_counters

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _claim_next_queued_job_id() -> int | None:
    session_factory = get_session_factory()
    db = session_factory()

    try:
        stmt = (
            select(ProcessingJob)
            .options(selectinload(ProcessingJob.session))
            .where(ProcessingJob.status == ProcessingJobStatus.QUEUED.value)
            .order_by(ProcessingJob.created_at, ProcessingJob.id)
            .limit(1)
        )

        job = db.scalar(stmt)
        if job is None:
            return None

        now = datetime.now(timezone.utc)

        job.status = ProcessingJobStatus.PROCESSING.value
        job.started_at = now
        job.worker_id = "dev-inference-worker"
        job.error_message = None

        if job.session is not None:
            job.session.status = AnalysisSessionStatus.PROCESSING.value
            if job.session.started_at is None:
                job.session.started_at = now
            job.session.error_message = None

        db.commit()
        return job.id

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _load_job_for_processing(db, job_id: int) -> ProcessingJob | None:
    stmt = (
        select(ProcessingJob)
        .options(
            selectinload(ProcessingJob.session)
            .selectinload(AnalysisSession.inference_profile)
            .selectinload(InferenceProfile.classifier_model),
            selectinload(ProcessingJob.session)
            .selectinload(AnalysisSession.images)
            .selectinload(AnalysisImage.original_asset),
            selectinload(ProcessingJob.session)
            .selectinload(AnalysisSession.images)
            .selectinload(AnalysisImage.result),
        )
        .where(ProcessingJob.id == job_id)
        .limit(1)
    )
    return db.scalar(stmt)


def _process_job(job_id: int) -> None:
    session_factory = get_session_factory()
    db = session_factory()

    try:
        job = _load_job_for_processing(db, job_id)
        if job is None or job.session is None:
            return

        analysis_session = job.session
        image_records = sorted(
            analysis_session.images,
            key=lambda item: item.image_index,
        )

        success_count = 0
        failure_count = 0

        for image_record in image_records:
            if image_record.status not in {
                AnalysisImageStatus.QUEUED.value,
                AnalysisImageStatus.UPLOADED.value,
                AnalysisImageStatus.PROCESSING.value,
            }:
                continue

            image_record.status = AnalysisImageStatus.PROCESSING.value
            image_record.error_message = None
            db.commit()

            try:
                result_data = run_classification_inference(
                    analysis_session,
                    image_record,
                )

                result_record = image_record.result
                if result_record is None:
                    result_record = ImageAnalysisResult(
                        image_id=image_record.id,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(result_record)
                    image_record.result = result_record

                result_record.classifier_model_id = result_data["classifier_model_id"]
                result_record.predicted_time_class = result_data["predicted_time_class"]
                result_record.predicted_time_confidence = result_data["predicted_time_confidence"]
                result_record.top2_predictions = result_data["top2_predictions"]
                result_record.confidence_flag = result_data["confidence_flag"]
                result_record.metrics = result_data["metrics"]
                result_record.warnings = result_data["warnings"]
                result_record.inference_time_ms = result_data["inference_time_ms"]

                image_record.status = AnalysisImageStatus.COMPLETED.value
                image_record.error_message = None
                success_count += 1

            except Exception as exc:
                logger.exception(
                    "Failed to process image %s in session %s",
                    image_record.public_id,
                    analysis_session.public_id,
                )

                if image_record.result is not None:
                    db.delete(image_record.result)
                    db.flush()

                image_record.status = AnalysisImageStatus.FAILED.value
                image_record.error_message = str(exc)
                failure_count += 1

            finally:
                sync_session_counters(db, analysis_session)
                db.commit()

        finished_at = datetime.now(timezone.utc)

        sync_session_counters(db, analysis_session)

        job.finished_at = finished_at
        analysis_session.finished_at = finished_at

        if success_count == 0:
            job.status = ProcessingJobStatus.FAILED.value
            job.error_message = "No images were processed successfully."

            analysis_session.status = AnalysisSessionStatus.FAILED.value
            analysis_session.error_message = "Не удалось обработать ни одного изображения."
        else:
            job.status = ProcessingJobStatus.COMPLETED.value

            if failure_count > 0:
                job.error_message = f"{failure_count} image(s) failed during analysis."
                analysis_session.error_message = (
                    f"Не удалось обработать {failure_count} "
                    f"из {len(image_records)} изображений."
                )
            else:
                job.error_message = None
                analysis_session.error_message = None

            analysis_session.status = AnalysisSessionStatus.COMPLETED.value

        sync_session_counters(db, analysis_session)
        db.commit()

    except Exception as exc:
        logger.exception("Fatal error while processing job %s", job_id)

        db.rollback()

        try:
            job = _load_job_for_processing(db, job_id)
            if job is not None:
                job.status = ProcessingJobStatus.FAILED.value
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)

                if job.session is not None:
                    analysis_session = job.session

                    for image_record in analysis_session.images:
                        if image_record.status in {
                            AnalysisImageStatus.UPLOADED.value,
                            AnalysisImageStatus.QUEUED.value,
                            AnalysisImageStatus.PROCESSING.value,
                        }:
                            image_record.status = AnalysisImageStatus.FAILED.value
                            image_record.error_message = str(exc)

                    analysis_session.status = AnalysisSessionStatus.FAILED.value
                    analysis_session.error_message = str(exc)
                    analysis_session.finished_at = job.finished_at
                    sync_session_counters(db, analysis_session)

                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist terminal failure state for job %s", job_id)

    finally:
        db.close()


def _run_loop() -> None:
    logger.info("Dev inference worker loop started.")

    while not _stop_event.is_set():
        job_id = _claim_next_queued_job_id()

        if job_id is None:
            _stop_event.wait(settings.dev_worker_poll_interval_sec)
            continue

        _process_job(job_id)

    logger.info("Dev inference worker loop stopped.")


def start_dev_worker() -> None:
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _stop_event.clear()

    _worker_thread = threading.Thread(
        target=_run_loop,
        name="dev-inference-worker",
        daemon=True,
    )
    _worker_thread.start()


def stop_dev_worker() -> None:
    global _worker_thread

    _stop_event.set()

    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=2.0)

    _worker_thread = None