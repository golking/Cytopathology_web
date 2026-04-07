from datetime import datetime
from uuid import uuid4

from app.data.job_store import JOB_STORE
from app.domain.enums import ProcessingJobStatus


def create_analysis_job(session: dict, *, queued_at: datetime) -> dict:
    job_id = uuid4()

    record = {
        "id": job_id,
        "session_id": session["id"],
        "job_type": "analysis",
        "status": ProcessingJobStatus.QUEUED,
        "attempt_no": 1,
        "worker_id": None,
        "payload": {
            "profile_key": session["profile_key"],
            "virus_code": session["virus"]["code"],
            "cell_line_code": session["cell_line"]["code"],
            "image_ids": [str(image_id) for image_id in session.get("image_ids", [])],
            "images_count": len(session.get("image_ids", [])),
        },
        "error_message": None,
        "created_at": queued_at,
        "started_at": None,
        "finished_at": None,
    }

    JOB_STORE[job_id] = record
    return record