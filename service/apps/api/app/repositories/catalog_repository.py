from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CellLine, InferenceProfile, Virus


def list_supported_viruses(db: Session) -> list[Virus]:
    stmt = (
        select(Virus)
        .join(InferenceProfile, InferenceProfile.virus_id == Virus.id)
        .join(CellLine, InferenceProfile.cell_line_id == CellLine.id)
        .where(
            Virus.is_active.is_(True),
            CellLine.is_active.is_(True),
            InferenceProfile.is_active.is_(True),
        )
        .distinct()
        .order_by(Virus.name, Virus.id)
    )
    return list(db.scalars(stmt).all())


def get_supported_virus_by_code(db: Session, virus_code: str) -> Virus | None:
    stmt = (
        select(Virus)
        .join(InferenceProfile, InferenceProfile.virus_id == Virus.id)
        .join(CellLine, InferenceProfile.cell_line_id == CellLine.id)
        .where(
            Virus.code == virus_code,
            Virus.is_active.is_(True),
            CellLine.is_active.is_(True),
            InferenceProfile.is_active.is_(True),
        )
        .limit(1)
    )
    return db.scalar(stmt)


def list_supported_cell_lines(
    db: Session,
    virus_code: str | None = None,
) -> list[CellLine]:
    stmt = (
        select(CellLine)
        .join(InferenceProfile, InferenceProfile.cell_line_id == CellLine.id)
        .join(Virus, InferenceProfile.virus_id == Virus.id)
        .where(
            CellLine.is_active.is_(True),
            Virus.is_active.is_(True),
            InferenceProfile.is_active.is_(True),
        )
    )

    if virus_code is not None:
        stmt = stmt.where(Virus.code == virus_code)

    stmt = stmt.distinct().order_by(CellLine.name, CellLine.id)
    return list(db.scalars(stmt).all())


def get_supported_cell_line_by_code(
    db: Session,
    cell_line_code: str,
) -> CellLine | None:
    stmt = (
        select(CellLine)
        .join(InferenceProfile, InferenceProfile.cell_line_id == CellLine.id)
        .join(Virus, InferenceProfile.virus_id == Virus.id)
        .where(
            CellLine.code == cell_line_code,
            CellLine.is_active.is_(True),
            Virus.is_active.is_(True),
            InferenceProfile.is_active.is_(True),
        )
        .limit(1)
    )
    return db.scalar(stmt)


def list_supported_profiles(db: Session) -> list[InferenceProfile]:
    stmt = (
        select(InferenceProfile)
        .join(InferenceProfile.virus)
        .join(InferenceProfile.cell_line)
        .options(
            selectinload(InferenceProfile.virus),
            selectinload(InferenceProfile.cell_line),
            selectinload(InferenceProfile.classifier_model),
            selectinload(InferenceProfile.segmenter_model),
            selectinload(InferenceProfile.scorer_model),
        )
        .where(
            InferenceProfile.is_active.is_(True),
            Virus.is_active.is_(True),
            CellLine.is_active.is_(True),
        )
        .order_by(Virus.name, CellLine.name, InferenceProfile.profile_key)
    )
    return list(db.scalars(stmt).all())


def get_supported_profile_by_pair(
    db: Session,
    virus_code: str,
    cell_line_code: str,
) -> InferenceProfile | None:
    stmt = (
        select(InferenceProfile)
        .join(InferenceProfile.virus)
        .join(InferenceProfile.cell_line)
        .options(
            selectinload(InferenceProfile.virus),
            selectinload(InferenceProfile.cell_line),
            selectinload(InferenceProfile.classifier_model),
            selectinload(InferenceProfile.segmenter_model),
            selectinload(InferenceProfile.scorer_model),
        )
        .where(
            Virus.code == virus_code,
            CellLine.code == cell_line_code,
            InferenceProfile.is_active.is_(True),
            Virus.is_active.is_(True),
            CellLine.is_active.is_(True),
        )
        .order_by(InferenceProfile.is_default.desc(), InferenceProfile.id)
        .limit(1)
    )
    return db.scalar(stmt)