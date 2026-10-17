import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FaceSampleState(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class JobKind(str, enum.Enum):
    ENROLLMENT = "enrollment"
    RECOGNITION = "recognition"


class JobState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DISPATCH_FAILED = "dispatch_failed"


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_class]


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="ck_students_name_length"),
        CheckConstraint("name = btrim(name)", name="ck_students_name_trimmed"),
        Index("uq_students_name_ci", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    face_samples: Mapped[list["FaceSample"]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="student", passive_deletes=True
    )


class FaceSample(Base):
    __tablename__ = "face_samples"
    __table_args__ = (
        UniqueConstraint("student_id", "sha256", name="uq_face_samples_student_sha256"),
        CheckConstraint(
            "embedding IS NULL OR CASE "
            "WHEN jsonb_typeof(embedding) = 'array' "
            "THEN jsonb_array_length(embedding) = 128 ELSE false END",
            name="ck_face_samples_embedding_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[FaceSampleState] = mapped_column(
        Enum(
            FaceSampleState,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="face_sample_state",
        ),
        default=FaceSampleState.PENDING,
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped[Student] = relationship(back_populates="face_samples")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[JobKind] = mapped_column(
        Enum(
            JobKind,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="job_kind",
        ),
        nullable=False,
    )
    state: Mapped[JobState] = mapped_column(
        Enum(
            JobState,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=True,
            name="job_state",
        ),
        default=JobState.PENDING,
        nullable=False,
        index=True,
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), index=True
    )
    input_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student | None] = relationship(back_populates="jobs")
