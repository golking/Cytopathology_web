from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import EmptyFilesPayloadError, ImageNotFoundError
from app.db.models import AnalysisImage, FileAsset
from app.domain.enums import AnalysisImageStatus
from app.schemas.image import AnalysisImageRead
from app.services.asset_url_service import build_asset_content_url
from app.services.session_service import (
    ensure_session_is_editable,
    get_session_record,
    sync_session_counters,
)
from app.services.storage_service import (
    build_browser_preview_image,
    build_original_asset_storage_path,
    build_preview_asset_storage_path,
    delete_stored_file_by_storage_path,
    prepare_original_image,
    write_bytes_to_storage,
)


def _to_analysis_image_read(image: AnalysisImage) -> AnalysisImageRead:
    return AnalysisImageRead(
        id=image.public_id,
        image_index=image.image_index,
        original_filename=image.original_filename,
        status=image.status,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        channels=image.channels,
        original_url=build_asset_content_url(
            image.original_asset.public_id if image.original_asset is not None else None
        ),
        preview_url=build_asset_content_url(
            image.preprocessed_asset.public_id if image.preprocessed_asset is not None else None
        ),
        error_message=image.error_message,
        created_at=image.created_at,
    )


def _get_session_image_record(
    db: Session,
    session_public_id: UUID,
    image_public_id: UUID,
    *,
    load_assets: bool = False,
    load_result: bool = False,
) -> AnalysisImage:
    options = []

    if load_assets:
        options.extend(
            [
                selectinload(AnalysisImage.original_asset),
                selectinload(AnalysisImage.preprocessed_asset),
            ]
        )

    if load_result:
        options.append(selectinload(AnalysisImage.result))

    stmt = (
        select(AnalysisImage)
        .join(AnalysisImage.session)
        .options(*options)
        .where(
            AnalysisImage.public_id == image_public_id,
            AnalysisImage.session.has(public_id=session_public_id),
        )
        .limit(1)
    )

    image = db.scalar(stmt)
    if image is None:
        raise ImageNotFoundError(
            session_id=session_public_id,
            image_id=image_public_id,
        )

    return image


def list_analysis_session_images(
    db: Session,
    session_id: UUID,
) -> list[AnalysisImageRead]:
    session = get_session_record(db, session_id)

    stmt = (
        select(AnalysisImage)
        .options(
            selectinload(AnalysisImage.original_asset),
            selectinload(AnalysisImage.preprocessed_asset),
        )
        .where(AnalysisImage.session_id == session.id)
        .order_by(AnalysisImage.image_index, AnalysisImage.id)
    )

    images = list(db.scalars(stmt).all())
    return [_to_analysis_image_read(image) for image in images]


def get_analysis_session_image(
    db: Session,
    session_id: UUID,
    image_id: UUID,
) -> AnalysisImageRead:
    image = _get_session_image_record(
        db,
        session_id,
        image_id,
        load_assets=True,
    )
    return _to_analysis_image_read(image)


async def upload_images_to_session(
    db: Session,
    session_id: UUID,
    files: list[UploadFile],
) -> list[AnalysisImageRead]:
    if not files:
        raise EmptyFilesPayloadError()

    session = get_session_record(db, session_id)
    ensure_session_is_editable(session)

    prepared_uploads = []
    for file in files:
        prepared_uploads.append(await prepare_original_image(file))

    existing_image_count = session.images_count
    written_storage_paths: list[str] = []
    created_images: list[AnalysisImage] = []

    try:
        for offset, prepared in enumerate(prepared_uploads, start=1):
            preview = build_browser_preview_image(prepared)

            original_asset_public_id = uuid4()
            preview_asset_public_id = uuid4()

            original_storage_path = build_original_asset_storage_path(
                original_asset_public_id,
                prepared,
            )
            preview_storage_path = build_preview_asset_storage_path(
                preview_asset_public_id
            )

            original_asset = FileAsset(
                public_id=original_asset_public_id,
                asset_type="original_image",
                storage_backend="fs",
                storage_path=original_storage_path,
                mime_type=prepared.mime_type,
                size_bytes=prepared.size_bytes,
                checksum=prepared.checksum,
                width=prepared.width,
                height=prepared.height,
                expires_at=None,
                created_at=datetime.now(timezone.utc),
            )

            preview_asset = FileAsset(
                public_id=preview_asset_public_id,
                asset_type="preprocessed_image",
                storage_backend="fs",
                storage_path=preview_storage_path,
                mime_type=preview.mime_type,
                size_bytes=preview.size_bytes,
                checksum=preview.checksum,
                width=preview.width,
                height=preview.height,
                expires_at=None,
                created_at=datetime.now(timezone.utc),
            )

            image = AnalysisImage(
                public_id=uuid4(),
                session_id=session.id,
                image_index=existing_image_count + offset,
                original_filename=prepared.original_filename,
                mime_type=prepared.mime_type,
                width=prepared.width,
                height=prepared.height,
                channels=prepared.channels,
                checksum=prepared.checksum,
                status=AnalysisImageStatus.UPLOADED.value,
                original_asset=original_asset,
                preprocessed_asset=preview_asset,
                error_message=None,
                created_at=datetime.now(timezone.utc),
            )

            db.add(image)

            write_bytes_to_storage(original_storage_path, prepared.content)
            written_storage_paths.append(original_storage_path)

            write_bytes_to_storage(preview_storage_path, preview.content)
            written_storage_paths.append(preview_storage_path)

            created_images.append(image)

        sync_session_counters(db, session)
        db.commit()

        return [_to_analysis_image_read(image) for image in created_images]

    except Exception:
        db.rollback()

        for storage_path in written_storage_paths:
            delete_stored_file_by_storage_path(storage_path)

        raise


def delete_analysis_session_image(
    db: Session,
    session_id: UUID,
    image_id: UUID,
) -> None:
    session = get_session_record(db, session_id)
    ensure_session_is_editable(session)

    image = _get_session_image_record(
        db,
        session_id,
        image_id,
        load_assets=True,
        load_result=True,
    )

    storage_paths_to_delete: list[str] = []

    if image.original_asset is not None:
        storage_paths_to_delete.append(image.original_asset.storage_path)

    if image.preprocessed_asset is not None:
        storage_paths_to_delete.append(image.preprocessed_asset.storage_path)

    original_asset = image.original_asset
    preprocessed_asset = image.preprocessed_asset

    db.delete(image)
    db.flush()

    if original_asset is not None:
        db.delete(original_asset)

    if preprocessed_asset is not None:
        db.delete(preprocessed_asset)

    remaining_images = list(
        db.scalars(
            select(AnalysisImage)
            .where(AnalysisImage.session_id == session.id)
            .order_by(AnalysisImage.image_index, AnalysisImage.id)
        ).all()
    )

    for index, item in enumerate(remaining_images, start=1):
        item.image_index = index

    sync_session_counters(db, session)
    db.commit()

    for storage_path in storage_paths_to_delete:
        delete_stored_file_by_storage_path(storage_path)