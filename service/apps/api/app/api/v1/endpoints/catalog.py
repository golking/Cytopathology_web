from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.catalog import CellLineRef, SupportMatrixResponse, VirusRef
from app.services.catalog_service import (
    get_support_matrix,
    list_cell_lines,
    list_viruses,
)

router = APIRouter()


@router.get(
    "/viruses",
    response_model=list[VirusRef],
    summary="Список поддерживаемых вирусов",
)
async def get_viruses() -> list[VirusRef]:
    return list_viruses()


@router.get(
    "/cell-lines",
    response_model=list[CellLineRef],
    summary="Список поддерживаемых клеточных линий",
)
async def get_cell_lines(
    virus_code: Annotated[
        str | None,
        Query(description="Опциональный фильтр по коду вируса"),
    ] = None,
) -> list[CellLineRef]:
    return list_cell_lines(virus_code=virus_code)


@router.get(
    "/support-matrix",
    response_model=SupportMatrixResponse,
    summary="Матрица поддерживаемых сочетаний",
)
async def get_supported_configurations() -> SupportMatrixResponse:
    return get_support_matrix()