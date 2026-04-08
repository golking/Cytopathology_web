from pydantic import BaseModel, Field

from app.domain.enums import TaskType

class VirusRef(BaseModel):
    id: int = Field(..., ge=1)
    code: str
    name: str

class CellLineRef(BaseModel):
    id: int = Field(..., ge=1)
    code: str
    name: str

class SupportProfile(BaseModel):
    profile_key: str
    virus_code: str
    cell_line_code: str
    tasks: list[TaskType]
    is_default: bool = True

class SupportMatrixResponse(BaseModel):
    viruses: list[VirusRef]
    cell_lines: list[CellLineRef]
    profiles: list[SupportProfile]