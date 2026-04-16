from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.enums import TaskType
from app.repositories.catalog_repository import (
    get_supported_cell_line_by_code,
    get_supported_profile_by_pair,
    get_supported_virus_by_code,
    list_supported_cell_lines,
    list_supported_profiles,
    list_supported_viruses,
)
from app.schemas.catalog import (
    CellLineRef,
    SupportMatrixResponse,
    SupportProfile,
    VirusRef,
)


@dataclass(slots=True)
class ResolvedCatalogPair:
    inference_profile_id: int
    profile_key: str
    virus_id: int
    cell_line_id: int
    virus: VirusRef
    cell_line: CellLineRef
    classifier_model_key: str | None = None
    segmenter_model_key: str | None = None
    scorer_model_key: str | None = None


def _to_virus_ref(obj) -> VirusRef:
    return VirusRef(
        id=obj.id,
        code=obj.code,
        name=obj.name,
    )


def _to_cell_line_ref(obj) -> CellLineRef:
    return CellLineRef(
        id=obj.id,
        code=obj.code,
        name=obj.name,
    )


def _extract_tasks(profile) -> list[TaskType]:
    tasks: list[TaskType] = []

    if profile.classifier_model_id is not None:
        tasks.append(TaskType.TIME_CLASSIFICATION)

    if profile.segmenter_model_id is not None:
        tasks.append(TaskType.CPE_SEGMENTATION)

    if profile.scorer_model_id is not None:
        tasks.append(TaskType.CPE_SCORING)

    return tasks


def list_viruses_from_db(db: Session) -> list[VirusRef]:
    return [_to_virus_ref(item) for item in list_supported_viruses(db)]


def get_supported_virus_by_code_from_db(
    db: Session,
    virus_code: str,
) -> VirusRef | None:
    obj = get_supported_virus_by_code(db, virus_code)
    if obj is None:
        return None
    return _to_virus_ref(obj)


def list_cell_lines_from_db(
    db: Session,
    virus_code: str | None = None,
) -> list[CellLineRef]:
    return [
        _to_cell_line_ref(item)
        for item in list_supported_cell_lines(db, virus_code=virus_code)
    ]


def get_supported_cell_line_by_code_from_db(
    db: Session,
    cell_line_code: str,
) -> CellLineRef | None:
    obj = get_supported_cell_line_by_code(db, cell_line_code)
    if obj is None:
        return None
    return _to_cell_line_ref(obj)


def list_profiles_from_db(db: Session) -> list[SupportProfile]:
    profiles = list_supported_profiles(db)

    return [
        SupportProfile(
            profile_key=profile.profile_key,
            virus_code=profile.virus.code,
            cell_line_code=profile.cell_line.code,
            tasks=_extract_tasks(profile),
            is_default=profile.is_default,
        )
        for profile in profiles
    ]


def resolve_supported_pair_from_db(
    db: Session,
    virus_code: str,
    cell_line_code: str,
) -> ResolvedCatalogPair | None:
    profile = get_supported_profile_by_pair(
        db=db,
        virus_code=virus_code,
        cell_line_code=cell_line_code,
    )
    if profile is None:
        return None

    return ResolvedCatalogPair(
        inference_profile_id=profile.id,
        profile_key=profile.profile_key,
        virus_id=profile.virus.id,
        cell_line_id=profile.cell_line.id,
        virus=_to_virus_ref(profile.virus),
        cell_line=_to_cell_line_ref(profile.cell_line),
        classifier_model_key=(
            profile.classifier_model.model_key
            if profile.classifier_model is not None
            else None
        ),
        segmenter_model_key=(
            profile.segmenter_model.model_key
            if profile.segmenter_model is not None
            else None
        ),
        scorer_model_key=(
            profile.scorer_model.model_key
            if profile.scorer_model is not None
            else None
        ),
    )


def get_support_matrix_from_db(db: Session) -> SupportMatrixResponse:
    return SupportMatrixResponse(
        viruses=list_viruses_from_db(db),
        cell_lines=list_cell_lines_from_db(db),
        profiles=list_profiles_from_db(db),
    )