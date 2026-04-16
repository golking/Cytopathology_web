import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePath
from uuid import UUID

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


@dataclass(slots=True)
class PreparedBrowserPreview:
    suffix: str
    mime_type: str
    size_bytes: int
    checksum: str
    width: int
    height: int
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

    checksum = hashlib.sha256(content).hexdigest()

    return PreparedImageUpload(
        original_filename=original_filename,
        safe_stem=_sanitize_stem(original_filename),
        suffix=FORMAT_TO_EXTENSION[detected_format],
        mime_type=FORMAT_TO_MIME[detected_format],
        size_bytes=len(content),
        checksum=checksum,
        width=width,
        height=height,
        channels=channels,
        content=content,
    )


def build_browser_preview_image(
    prepared: PreparedImageUpload,
) -> PreparedBrowserPreview:
    """
    Формируем browser-friendly PNG для <img> в UI.
    Оригинальный файл не меняем и сохраняем отдельно как есть.
    """
    with Image.open(BytesIO(prepared.content)) as image:
        preview_image = image.convert("RGB")

        output = BytesIO()
        preview_image.save(output, format="PNG")
        preview_bytes = output.getvalue()

        width, height = preview_image.size

    checksum = hashlib.sha256(preview_bytes).hexdigest()

    return PreparedBrowserPreview(
        suffix=".png",
        mime_type="image/png",
        size_bytes=len(preview_bytes),
        checksum=checksum,
        width=width,
        height=height,
        content=preview_bytes,
    )


def build_original_asset_storage_path(
    asset_public_id: UUID,
    prepared: PreparedImageUpload,
) -> str:
    return (Path("originals") / f"{asset_public_id}{prepared.suffix}").as_posix()


def build_preview_asset_storage_path(
    asset_public_id: UUID,
) -> str:
    return (Path("previews") / f"{asset_public_id}.png").as_posix()


def resolve_storage_absolute_path(storage_path: str) -> Path:
    return settings.storage_root / storage_path


def write_bytes_to_storage(storage_path: str, content: bytes) -> Path:
    absolute_path = resolve_storage_absolute_path(storage_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    return absolute_path


def delete_stored_file_by_storage_path(storage_path: str) -> None:
    absolute_path = resolve_storage_absolute_path(storage_path)
    absolute_path.unlink(missing_ok=True)