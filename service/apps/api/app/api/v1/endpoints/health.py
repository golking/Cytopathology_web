from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка доступности backend",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")