import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import FaceSampleState, JobKind, JobState


class StudentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    enrollment_state: FaceSampleState | None = None


class StudentList(BaseModel):
    items: list[StudentRead]
    page: int
    page_size: int
    total: int


class FaceSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: int
    state: FaceSampleState
    rejection_reason: str | None
    model_version: str
    created_at: datetime
    updated_at: datetime


class JobAccepted(BaseModel):
    job_id: uuid.UUID
    state: JobState


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: JobKind
    state: JobState
    student_id: int | None
    attempt_count: int
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ErrorResponse(BaseModel):
    detail: str
