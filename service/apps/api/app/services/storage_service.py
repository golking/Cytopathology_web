import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import InvalidImageFileError, UnsupportedFileTypeError


ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "TIFF"}
FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "TIFF": "image/tiff",
}
FORMAT_TO_EXTENSION = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "TIFF": ".tif",
}


@dataclass(slots=True)
class PreparedImageUpload:
    original_filename: str
    safe_stem: str
    suffix: str
    mime_type: str
    size_bytes: int
    checksum: str
    width: int
    height: int
    channels: int
    content: bytes


def _extract_client_filename(raw_filename: str | None) -> str:
    filename = PurePath(raw_filename or "image").name.strip()
    return filename or "image"


def _sanitize_stem(filename: str) -> str:
    stem = Path(filename).stem.strip() or "image"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return sanitized or "image"


async def prepare_original_image(upload: UploadFile) -> PreparedImageUpload:
    original_filename = _extract_client_filename(upload.filename)
    content = await upload.read()

    if not content:
        raise InvalidImageFileError(original_filename)

    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            detected_format = (image.format or "").upper()

            if detected_format not in ALLOWED_PIL_FORMATS:
                raise UnsupportedFileTypeError(
                    filename=original_filename,
                    detected_format=detected_format or None,
                )

            width, height = image.size
            channels = len(image.getbands())
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageFileError(original_filename) from exc

    return PreparedImageUpload(
        original_filename=original_filename,
        safe_stem=_sanitize_stem(original_filename),
        suffix=FORMAT_TO_EXTENSION[detected_format],
        mime_type=FORMAT_TO_MIME[detected_format],
        size_bytes=len(content),
        checksum=sha256(content).hexdigest(),
        width=width,
        height=height,
        channels=channels,
        content=content,
    )


def persist_original_image(session_id: UUID, prepared: PreparedImageUpload) -> dict:
    asset_id = uuid4()
    relative_path = (
        Path("originals")
        / str(session_id)
        / f"{asset_id}_{prepared.safe_stem}{prepared.suffix}"
    )
    absolute_path = settings.storage_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(prepared.content)

    created_at = datetime.now(timezone.utc)

    return {
        "id": asset_id,
        "asset_type": "original_image",
        "storage_backend": "fs",
        "storage_path": relative_path.as_posix(),
        "absolute_path": str(absolute_path),
        "mime_type": prepared.mime_type,
        "size_bytes": prepared.size_bytes,
        "checksum": prepared.checksum,
        "width": prepared.width,
        "height": prepared.height,
        "created_at": created_at,
    }


def delete_stored_asset_file(asset_record: dict) -> None:
    absolute_path = Path(asset_record["absolute_path"])
    absolute_path.unlink(missing_ok=True)