from app.data.catalog import CATALOG_CELL_LINES, CATALOG_PROFILES, CATALOG_VIRUSES
from app.domain.enums import TaskType
from app.schemas.catalog import (
    CellLineRef,
    SupportMatrixResponse,
    SupportProfile,
    VirusRef,
)


def _extract_tasks(profile: dict) -> list[TaskType]:
    tasks: list[TaskType] = []

    if profile.get("classifier_model_key"):
        tasks.append(TaskType.TIME_CLASSIFICATION)

    if profile.get("segmenter_model_key"):
        tasks.append(TaskType.CPE_SEGMENTATION)

    if profile.get("scorer_model_key"):
        tasks.append(TaskType.CPE_SCORING)

    if not tasks:
        raise ValueError(
            f"Profile '{profile['profile_key']}' does not reference any model."
        )

    return tasks


def list_viruses() -> list[VirusRef]:
    supported_virus_codes = {profile["virus_code"] for profile in CATALOG_PROFILES}

    return [
        VirusRef.model_validate(item)
        for item in CATALOG_VIRUSES
        if item["code"] in supported_virus_codes
    ]


def get_supported_virus_by_code(virus_code: str) -> VirusRef | None:
    return next(
        (virus for virus in list_viruses() if virus.code == virus_code),
        None,
    )


def list_cell_lines(virus_code: str | None = None) -> list[CellLineRef]:
    supported_profiles = CATALOG_PROFILES

    if virus_code is not None:
        supported_profiles = [
            profile
            for profile in CATALOG_PROFILES
            if profile["virus_code"] == virus_code
        ]

    supported_cell_line_codes = {
        profile["cell_line_code"]
        for profile in supported_profiles
    }

    return [
        CellLineRef.model_validate(item)
        for item in CATALOG_CELL_LINES
        if item["code"] in supported_cell_line_codes
    ]


def get_supported_cell_line_by_code(cell_line_code: str) -> CellLineRef | None:
    return next(
        (
            cell_line
            for cell_line in list_cell_lines()
            if cell_line.code == cell_line_code
        ),
        None,
    )


def list_profiles() -> list[SupportProfile]:
    return [
        SupportProfile(
            profile_key=profile["profile_key"],
            virus_code=profile["virus_code"],
            cell_line_code=profile["cell_line_code"],
            tasks=_extract_tasks(profile),
            is_default=profile.get("is_default", False),
        )
        for profile in CATALOG_PROFILES
    ]


def get_profile_for_pair(
    virus_code: str,
    cell_line_code: str,
) -> SupportProfile | None:
    return next(
        (
            profile
            for profile in list_profiles()
            if profile.virus_code == virus_code
            and profile.cell_line_code == cell_line_code
        ),
        None,
    )


def get_support_matrix() -> SupportMatrixResponse:
    return SupportMatrixResponse(
        viruses=list_viruses(),
        cell_lines=list_cell_lines(),
        profiles=list_profiles(),
    )
    
def get_profile_record_by_key(profile_key: str) -> dict | None:
    return next(
        (
            profile
            for profile in CATALOG_PROFILES
            if profile["profile_key"] == profile_key
        ),
        None,
    )