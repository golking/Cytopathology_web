import logging
import threading
from datetime import datetime, timezone

from app.core.config import settings
from app.data.job_store import JOB_STORE
from app.data.result_store import RESULT_STORE
from app.domain.enums import (
    AnalysisImageStatus,
    AnalysisSessionStatus,
    ProcessingJobStatus,
)
from app.services.inference_service import run_classification_inference
from app.services.session_service import (
    get_session_image_records,
    get_session_record,
    refresh_session_counters,
)

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _get_next_queued_job() -> dict | None:
    queued_jobs = [
        job
        for job in JOB_STORE.values()
        if job["status"] == ProcessingJobStatus.QUEUED
    ]

    if not queued_jobs:
        return None

    queued_jobs.sort(key=lambda item: item["created_at"])
    return queued_jobs[0]


def _mark_unfinished_images_failed(session: dict, message: str) -> None:
    for image_record in get_session_image_records(session):
        if image_record["status"] in {
            AnalysisImageStatus.UPLOADED,
            AnalysisImageStatus.QUEUED,
            AnalysisImageStatus.PROCESSING,
        }:
            image_record["status"] = AnalysisImageStatus.FAILED
            image_record["error_message"] = message


def _process_job(job: dict) -> None:
    session = get_session_record(job["session_id"])
    image_records = sorted(
        get_session_image_records(session),
        key=lambda item: item["image_index"],
    )

    started_at = datetime.now(timezone.utc)

    job["status"] = ProcessingJobStatus.PROCESSING
    job["started_at"] = started_at
    job["error_message"] = None

    session["status"] = AnalysisSessionStatus.PROCESSING
    session["started_at"] = started_at
    session["error_message"] = None

    success_count = 0
    failure_count = 0

    for image_record in image_records:
        if image_record["status"] not in {
            AnalysisImageStatus.QUEUED,
            AnalysisImageStatus.UPLOADED,
        }:
            continue

        image_record["status"] = AnalysisImageStatus.PROCESSING
        image_record["error_message"] = None
        refresh_session_counters(session)

        try:
            result_record = run_classification_inference(session, image_record)
            RESULT_STORE[image_record["id"]] = result_record

            image_record["status"] = AnalysisImageStatus.COMPLETED
            image_record["error_message"] = None
            success_count += 1

        except Exception as exc:
            logger.exception(
                "Failed to process image %s in session %s",
                image_record["id"],
                session["id"],
            )

            RESULT_STORE.pop(image_record["id"], None)
            image_record["status"] = AnalysisImageStatus.FAILED
            image_record["error_message"] = str(exc)
            failure_count += 1

        finally:
            refresh_session_counters(session)

    finished_at = datetime.now(timezone.utc)
    job["finished_at"] = finished_at
    session["finished_at"] = finished_at

    if success_count == 0:
        job["status"] = ProcessingJobStatus.FAILED
        job["error_message"] = "No images were processed successfully."

        session["status"] = AnalysisSessionStatus.FAILED
        session["error_message"] = "Не удалось обработать ни одного изображения."
    else:
        job["status"] = ProcessingJobStatus.COMPLETED

        if failure_count > 0:
            job["error_message"] = (
                f"{failure_count} image(s) failed during analysis."
            )
            session["error_message"] = (
                f"Не удалось обработать {failure_count} "
                f"из {len(image_records)} изображений."
            )
        else:
            job["error_message"] = None
            session["error_message"] = None

        session["status"] = AnalysisSessionStatus.COMPLETED

    refresh_session_counters(session)


def _run_loop() -> None:
    logger.info("Dev inference worker loop started.")

    while not _stop_event.is_set():
        job = _get_next_queued_job()

        if job is None:
            _stop_event.wait(settings.dev_worker_poll_interval_sec)
            continue

        try:
            _process_job(job)

        except Exception as exc:
            logger.exception("Fatal error while processing job %s", job.get("id"))

            job["status"] = ProcessingJobStatus.FAILED
            job["error_message"] = str(exc)
            job["finished_at"] = datetime.now(timezone.utc)

            try:
                session = get_session_record(job["session_id"])
            except Exception:
                session = None

            if session is not None:
                _mark_unfinished_images_failed(session, str(exc))
                session["status"] = AnalysisSessionStatus.FAILED
                session["error_message"] = str(exc)
                session["finished_at"] = job["finished_at"]
                refresh_session_counters(session)

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