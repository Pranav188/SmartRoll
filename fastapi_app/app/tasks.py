from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from celery.exceptions import Retry
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import (
    FaceSample,
    FaceSampleState,
    JobKind,
    JobState,
    ProcessingJob,
    Student,
)
from app.services.recognition import (
    ENCODING_MODEL_VERSION,
    KnownSample,
    RecognitionError,
    encode_enrollment_image,
    recognize_classroom,
)
from app.services.storage import PrivateStorage


logger = logging.getLogger(__name__)
storage = PrivateStorage(settings.storage_root)


def dispatch_job(job_id: uuid.UUID) -> bool:
    try:
        run_processing_job.delay(str(job_id))
        return True
    except Exception:
        logger.exception("Could not dispatch processing job %s", job_id)
        with SessionLocal.begin() as db:
            job = db.get(ProcessingJob, job_id)
            if job and job.state == JobState.PENDING:
                job.state = JobState.DISPATCH_FAILED
                job.error_code = "broker_unavailable"
                job.error_message = "Processing could not start. Retry this job."
        return False


def _claim_job(
    job_id: uuid.UUID, *, allow_running: bool = False
) -> tuple[JobKind, int | None, list[str]] | None:
    with SessionLocal.begin() as db:
        job = db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if job is None:
            return None
        if job.state == JobState.RUNNING:
            if not allow_running:
                return None
        elif job.state != JobState.PENDING:
            return None
        if job.attempt_count >= 3:
            job.state = JobState.FAILED
            job.error_code = "attempts_exhausted"
            job.error_message = "Processing stopped after three attempts."
            job.finished_at = datetime.now(timezone.utc)
            return None
        job.state = JobState.RUNNING
        job.attempt_count += 1
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = None
        job.error_code = None
        job.error_message = None
        return job.kind, job.student_id, list(job.input_keys)


def _fail_job(job_id: uuid.UUID, code: str, message: str) -> None:
    with SessionLocal.begin() as db:
        job = db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if job is None or job.state == JobState.SUCCEEDED:
            return
        job.state = JobState.FAILED
        job.error_code = code
        job.error_message = message
        job.finished_at = datetime.now(timezone.utc)


def _prepare_retry(job_id: uuid.UUID) -> int:
    with SessionLocal.begin() as db:
        job = db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if job is None:
            return 3
        if job.attempt_count < 3:
            job.state = JobState.PENDING
            job.error_code = "transient_failure"
            job.error_message = "Processing will retry automatically."
            job.finished_at = None
        return job.attempt_count


def _run_enrollment(job_id: uuid.UUID, student_id: int | None, keys: list[str]) -> None:
    if student_id is None:
        raise RecognitionError("target_deleted", "The student no longer exists.")

    with SessionLocal() as db:
        student_exists = db.get(Student, student_id) is not None
        samples = db.execute(
            select(FaceSample).where(
                FaceSample.student_id == student_id,
                FaceSample.storage_key.in_(keys),
            )
        ).scalars().all()
        sample_snapshots = [
            (sample.id, sample.storage_key, sample.state) for sample in samples
        ]
    if not student_exists:
        raise RecognitionError("target_deleted", "The student no longer exists.")

    outcomes: dict[uuid.UUID, tuple[list[float] | None, str | None, str | None]] = {}
    for sample_id, storage_key, state in sample_snapshots:
        if state == FaceSampleState.READY:
            outcomes[sample_id] = ([], None, None)
            continue
        try:
            embedding = encode_enrollment_image(storage.resolve(storage_key))
            outcomes[sample_id] = (embedding, None, None)
        except RecognitionError as exc:
            outcomes[sample_id] = (None, exc.code, exc.message)

    accepted = 0
    rejected: list[dict[str, str]] = []
    with SessionLocal.begin() as db:
        student = db.execute(
            select(Student).where(Student.id == student_id).with_for_update()
        ).scalar_one_or_none()
        job = db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if job is None:
            return
        if student is None:
            job.state = JobState.FAILED
            job.error_code = "target_deleted"
            job.error_message = "The student was deleted before encoding finished."
            job.finished_at = datetime.now(timezone.utc)
            return

        current_samples = {
            sample.id: sample
            for sample in db.execute(
                select(FaceSample).where(FaceSample.id.in_(outcomes))
            ).scalars()
        }
        for sample_id, (embedding, code, message) in outcomes.items():
            sample = current_samples.get(sample_id)
            if sample is None:
                continue
            if embedding == [] and sample.state == FaceSampleState.READY:
                accepted += 1
            elif embedding is not None:
                sample.embedding = embedding
                sample.state = FaceSampleState.READY
                sample.rejection_reason = None
                sample.model_version = ENCODING_MODEL_VERSION
                accepted += 1
            else:
                sample.embedding = None
                sample.state = FaceSampleState.FAILED
                sample.rejection_reason = message
                rejected.append(
                    {
                        "sample_id": str(sample_id),
                        "code": code or "failed",
                        "message": message or "Encoding failed.",
                    }
                )

        job.result = {"accepted_count": accepted, "rejected": rejected}
        job.finished_at = datetime.now(timezone.utc)
        if accepted:
            job.state = JobState.SUCCEEDED
        else:
            job.state = JobState.FAILED
            job.error_code = "enrollment_rejected"
            job.error_message = "No enrollment photo contained exactly one usable face."


def _run_recognition(job_id: uuid.UUID, keys: list[str]) -> None:
    if len(keys) != 1:
        raise RecognitionError("invalid_job_input", "Recognition requires one classroom image.")

    output_key = storage.recognition_output_key(job_id)
    try:
        with SessionLocal.begin() as db:
            job = db.execute(
                select(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .with_for_update()
            ).scalar_one_or_none()
            if job is None:
                return
            students = db.execute(
                select(Student).order_by(Student.name).with_for_update()
            ).scalars().all()
            sample_rows = db.execute(
                select(FaceSample)
                .options(selectinload(FaceSample.student))
                .where(
                    FaceSample.state == FaceSampleState.READY,
                    FaceSample.embedding.is_not(None),
                )
            ).scalars().all()
            known_samples = [
                KnownSample(
                    sample.student_id,
                    sample.student.name,
                    sample.embedding or [],
                )
                for sample in sample_rows
            ]
            student_pairs = [(student.id, student.name) for student in students]
            result = recognize_classroom(
                storage.resolve(keys[0]),
                storage.resolve(output_key),
                known_samples,
                student_pairs,
            )
            result["output_key"] = output_key
            job.result = result
            job.state = JobState.SUCCEEDED
            job.finished_at = datetime.now(timezone.utc)
    except Exception:
        storage.delete(output_key)
        raise


@celery_app.task(bind=True, name="app.tasks.run_processing_job", max_retries=2)
def run_processing_job(self: Any, job_id: str) -> None:
    parsed_job_id = uuid.UUID(job_id)
    delivery_info = self.request.delivery_info or {}
    claim = _claim_job(
        parsed_job_id, allow_running=bool(delivery_info.get("redelivered"))
    )
    if claim is None:
        return
    kind, student_id, keys = claim
    try:
        if kind == JobKind.ENROLLMENT:
            _run_enrollment(parsed_job_id, student_id, keys)
        elif kind == JobKind.RECOGNITION:
            _run_recognition(parsed_job_id, keys)
        else:
            raise RecognitionError("unknown_job", "The processing job type is unsupported.")
    except RecognitionError as exc:
        _fail_job(parsed_job_id, exc.code, exc.message)
    except Retry:
        raise
    except Exception as exc:
        logger.exception("Processing job %s failed", parsed_job_id)
        attempt_count = _prepare_retry(parsed_job_id)
        if attempt_count < 3:
            raise self.retry(exc=exc, countdown=2**attempt_count)
        _fail_job(
            parsed_job_id,
            "processing_error",
            "Processing stopped. Retry this job after checking the worker logs.",
        )
