from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.exceptions import EmptyFilesPayloadError, ImageNotFoundError
from app.data.asset_store import ASSET_STORE
from app.data.image_store import IMAGE_STORE
from app.domain.enums import AnalysisImageStatus
from app.schemas.image import AnalysisImageRead
from app.services.session_service import (
    ensure_session_is_editable,
    get_session_image_records,
    get_session_record,
    refresh_session_counters,
)
from app.services.storage_service import (
    delete_stored_asset_file,
    persist_original_image,
    prepare_original_image,
)


def _get_image_record_from_session(session: dict, image_id: UUID) -> dict:
    session_image_ids = set(session.get("image_ids", []))
    if image_id not in session_image_ids:
        raise ImageNotFoundError(session_id=session["id"], image_id=image_id)

    image_record = IMAGE_STORE.get(image_id)
    if image_record is None:
        raise ImageNotFoundError(session_id=session["id"], image_id=image_id)

    if image_record.get("session_id") != session["id"]:
        raise ImageNotFoundError(session_id=session["id"], image_id=image_id)

    return image_record


def _reindex_session_images(session: dict) -> None:
    for index, current_image_id in enumerate(session.get("image_ids", []), start=1):
        image_record = IMAGE_STORE.get(current_image_id)
        if image_record is not None:
            image_record["image_index"] = index


def _delete_linked_assets(image_record: dict) -> None:
    asset_fields = (
        "original_asset_id",
        "preprocessed_asset_id",
        "mask_asset_id",
        "overlay_asset_id",
        "heatmap_asset_id",
    )

    for asset_field in asset_fields:
        asset_id = image_record.get(asset_field)
        if asset_id is None:
            continue

        asset_record = ASSET_STORE.pop(asset_id, None)
        if asset_record is not None:
            delete_stored_asset_file(asset_record)


def list_analysis_session_images(session_id: UUID) -> list[AnalysisImageRead]:
    session = get_session_record(session_id)
    image_records = get_session_image_records(session)

    sorted_records = sorted(
        image_records,
        key=lambda item: item["image_index"],
    )

    return [
        AnalysisImageRead.model_validate(record)
        for record in sorted_records
    ]


def get_analysis_session_image(
    session_id: UUID,
    image_id: UUID,
) -> AnalysisImageRead:
    session = get_session_record(session_id)
    image_record = _get_image_record_from_session(session, image_id)
    return AnalysisImageRead.model_validate(image_record)


def delete_analysis_session_image(
    session_id: UUID,
    image_id: UUID,
) -> None:
    session = get_session_record(session_id)
    ensure_session_is_editable(session)

    image_record = _get_image_record_from_session(session, image_id)

    _delete_linked_assets(image_record)
    IMAGE_STORE.pop(image_id, None)

    session["image_ids"] = [
        current_image_id
        for current_image_id in session.get("image_ids", [])
        if current_image_id != image_id
    ]

    _reindex_session_images(session)
    refresh_session_counters(session)


async def upload_images_to_session(
    session_id: UUID,
    files: list[UploadFile],
) -> list[AnalysisImageRead]:
    if not files:
        raise EmptyFilesPayloadError()

    session = get_session_record(session_id)
    ensure_session_is_editable(session)

    prepared_uploads = []
    for file in files:
        prepared_uploads.append(await prepare_original_image(file))

    created_asset_ids: list[UUID] = []
    created_image_ids: list[UUID] = []
    uploaded_images: list[AnalysisImageRead] = []

    existing_image_count = len(session.get("image_ids", []))

    try:
        for offset, prepared in enumerate(prepared_uploads, start=1):
            asset_record = persist_original_image(
                session_id=session_id,
                prepared=prepared,
            )
            ASSET_STORE[asset_record["id"]] = asset_record
            created_asset_ids.append(asset_record["id"])

            image_id = uuid4()
            image_record = {
                "id": image_id,
                "session_id": session_id,
                "image_index": existing_image_count + offset,
                "original_filename": prepared.original_filename,
                "mime_type": prepared.mime_type,
                "width": prepared.width,
                "height": prepared.height,
                "channels": prepared.channels,
                "checksum": prepared.checksum,
                "status": AnalysisImageStatus.UPLOADED,
                "original_asset_id": asset_record["id"],
                "preprocessed_asset_id": None,
                "error_message": None,
                "created_at": datetime.now(timezone.utc),
            }

            IMAGE_STORE[image_id] = image_record
            created_image_ids.append(image_id)
            session.setdefault("image_ids", []).append(image_id)

            uploaded_images.append(AnalysisImageRead.model_validate(image_record))

        refresh_session_counters(session)
        return uploaded_images

    except Exception:
        for image_id in created_image_ids:
            IMAGE_STORE.pop(image_id, None)

        session["image_ids"] = [
            image_id
            for image_id in session.get("image_ids", [])
            if image_id not in created_image_ids
        ]

        for asset_id in created_asset_ids:
            asset_record = ASSET_STORE.pop(asset_id, None)
            if asset_record is not None:
                delete_stored_asset_file(asset_record)

        refresh_session_counters(session)
        raise