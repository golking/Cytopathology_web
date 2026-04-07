from fastapi import APIRouter

from app.api.v1.endpoints.catalog import router as catalog_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.images import router as images_router
from app.api.v1.endpoints.results import router as results_router
from app.api.v1.endpoints.sessions import router as sessions_router

router = APIRouter()
router.include_router(health_router, tags=["service"])
router.include_router(catalog_router, tags=["catalog"])
router.include_router(sessions_router, tags=["analysis-sessions"])
router.include_router(images_router, tags=["analysis-images"])
router.include_router(results_router, tags=["analysis-results"])