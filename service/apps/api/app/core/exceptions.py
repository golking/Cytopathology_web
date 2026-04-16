from typing import Any
from uuid import UUID


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class UnsupportedVirusError(AppError):
    def __init__(self, virus_code: str) -> None:
        super().__init__(
            status_code=422,
            code="unsupported_virus",
            message="Указанный вирус не поддерживается.",
            details={"virus_code": virus_code},
        )


class UnsupportedCellLineError(AppError):
    def __init__(self, cell_line_code: str) -> None:
        super().__init__(
            status_code=422,
            code="unsupported_cell_line",
            message="Указанная клеточная линия не поддерживается.",
            details={"cell_line_code": cell_line_code},
        )


class UnsupportedProfileError(AppError):
    def __init__(self, virus_code: str, cell_line_code: str) -> None:
        super().__init__(
            status_code=422,
            code="unsupported_profile",
            message="Нет активного профиля моделей для выбранной пары virus/cell_line.",
            details={
                "virus_code": virus_code,
                "cell_line_code": cell_line_code,
            },
        )


class SessionNotFoundError(AppError):
    def __init__(self, session_id: UUID) -> None:
        super().__init__(
            status_code=404,
            code="session_not_found",
            message="Сеанс анализа не найден.",
            details={"session_id": str(session_id)},
        )

class ImageNotFoundError(AppError):
    def __init__(self, session_id: UUID, image_id: UUID) -> None:
        super().__init__(
            status_code=404,
            code="image_not_found",
            message="Изображение не найдено в указанном сеансе.",
            details={
                "session_id": str(session_id),
                "image_id": str(image_id),
            },
        )
        
class SessionAlreadyStartedError(AppError):
    def __init__(self, session_id: UUID, current_status: str) -> None:
        super().__init__(
            status_code=409,
            code="session_already_started",
            message="Изображения можно изменять только в сеансе со статусом created.",
            details={
                "session_id": str(session_id),
                "current_status": current_status,
            },
        )


class SessionStartConflictError(AppError):
    def __init__(self, session_id: UUID, current_status: str) -> None:
        super().__init__(
            status_code=409,
            code="session_already_started",
            message="Сеанс можно запустить только из статуса created.",
            details={
                "session_id": str(session_id),
                "current_status": current_status,
            },
        )


class SessionHasNoImagesError(AppError):
    def __init__(self, session_id: UUID) -> None:
        super().__init__(
            status_code=409,
            code="session_has_no_images",
            message="Нельзя запустить сеанс без загруженных изображений.",
            details={"session_id": str(session_id)},
        )


class UnsupportedFileTypeError(AppError):
    def __init__(
        self,
        filename: str,
        detected_format: str | None = None,
    ) -> None:
        super().__init__(
            status_code=400,
            code="unsupported_file_type",
            message="Формат файла не поддерживается.",
            details={
                "filename": filename,
                "detected_format": detected_format,
                "allowed_formats": ["jpg", "jpeg", "png", "tif", "tiff"],
            },
        )


class InvalidImageFileError(AppError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            status_code=400,
            code="invalid_image_file",
            message="Файл не удалось распознать как корректное изображение.",
            details={"filename": filename},
        )


class EmptyFilesPayloadError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            code="validation_error",
            message="Нужно передать хотя бы один файл изображения.",
            details={"field": "files[]"},
        )
        
class AssetNotFoundError(AppError):
    def __init__(self, asset_id: UUID) -> None:
        super().__init__(
            status_code=404,
            code="asset_not_found",
            message="Артефакт не найден.",
            details={"asset_id": str(asset_id)},
        )