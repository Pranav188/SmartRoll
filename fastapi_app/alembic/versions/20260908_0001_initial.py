"""Create FastAPI application tables.

Revision ID: 20260908_0001
Revises:
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260908_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100", name="ck_students_name_length"
        ),
        sa.CheckConstraint("name = btrim(name)", name="ck_students_name_trimmed"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_students_name_ci", "students", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "face_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "pending",
                "ready",
                "failed",
                name="face_sample_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "embedding IS NULL OR CASE "
            "WHEN jsonb_typeof(embedding) = 'array' "
            "THEN jsonb_array_length(embedding) = 128 ELSE false END",
            name="ck_face_samples_embedding_length",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("student_id", "sha256", name="uq_face_samples_student_sha256"),
    )
    op.create_index("ix_face_samples_student_id", "face_samples", ["student_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "enrollment",
                "recognition",
                name="job_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "pending",
                "running",
                "succeeded",
                "failed",
                "dispatch_failed",
                name="job_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("input_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_jobs_state", "processing_jobs", ["state"])
    op.create_index("ix_processing_jobs_student_id", "processing_jobs", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_student_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_state", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_face_samples_student_id", table_name="face_samples")
    op.drop_table("face_samples")
    op.drop_index("uq_students_name_ci", table_name="students")
    op.drop_table("students")
