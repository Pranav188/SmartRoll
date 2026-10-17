from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    FaceSample,
    FaceSampleState,
    JobKind,
    JobState,
    ProcessingJob,
    Student,
)
from app.schemas import JobAccepted, ProcessingJobRead, StudentCreate, StudentList, StudentRead
from app.security import require_safe_browser_request
from app.services.recognition import ENCODING_MODEL_VERSION
from app.services.storage import (
    PrivateStorage,
    UploadValidationError,
    read_limited,
    validate_image,
)
from app.tasks import dispatch_job


router = APIRouter(prefix="/api")
storage = PrivateStorage(settings.storage_root)


def _enrollment_state(student: Student) -> FaceSampleState | None:
    states = {sample.state for sample in student.face_samples}
    if FaceSampleState.READY in states:
        return FaceSampleState.READY
    if FaceSampleState.PENDING in states:
        return FaceSampleState.PENDING
    if FaceSampleState.FAILED in states:
        return FaceSampleState.FAILED
    return None


def _student_read(student: Student) -> StudentRead:
    return StudentRead(
        id=student.id,
        name=student.name,
        created_at=student.created_at,
        enrollment_state=_enrollment_state(student),
    )


@router.get("/students", response_model=StudentList)
def list_students(
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> StudentList:
    filters = []
    if search and search.strip():
        filters.append(Student.name.ilike(f"%{search.strip()}%"))
    total = db.scalar(select(func.count(Student.id)).where(*filters)) or 0
    students = db.execute(
        select(Student)
        .options(selectinload(Student.face_samples))
        .where(*filters)
        .order_by(func.lower(Student.name), Student.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return StudentList(
        items=[_student_read(student) for student in students],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/students",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_safe_browser_request)],
)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    student = Student(name=payload.name)
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A student with this name already exists."
        ) from exc
    db.refresh(student)
    return StudentRead(
        id=student.id,
        name=student.name,
        created_at=student.created_at,
        enrollment_state=None,
    )


@router.post(
    "/students/{student_id}/photos",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_safe_browser_request)],
)
def upload_student_photos(
    student_id: int,
    photos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> JobAccepted:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    if not photos or len(photos) > 10:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Choose between one and ten student photos.",
        )

    validated = []
    try:
        for photo in photos:
            content = read_limited(photo.file, settings.enrollment_max_bytes)
            validated.append(validate_image(content))
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc
    finally:
        for photo in photos:
            photo.file.close()

    existing_hashes = set(
        db.execute(
            select(FaceSample.sha256).where(FaceSample.student_id == student_id)
        ).scalars()
    )
    unique_images = []
    request_hashes: set[str] = set()
    for image in validated:
        if image.sha256 in existing_hashes or image.sha256 in request_hashes:
            continue
        request_hashes.add(image.sha256)
        unique_images.append(image)
    if not unique_images:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "These student photos have already been uploaded."
        )

    job = ProcessingJob(kind=JobKind.ENROLLMENT, state=JobState.PENDING, student_id=student_id)
    written_keys: list[str] = []
    samples: list[FaceSample] = []
    try:
        for image in unique_images:
            key = storage.enrollment_key(student_id, image.extension)
            storage.write(key, image.content)
            written_keys.append(key)
            samples.append(
                FaceSample(
                    student_id=student_id,
                    storage_key=key,
                    sha256=image.sha256,
                    state=FaceSampleState.PENDING,
                    model_version=ENCODING_MODEL_VERSION,
                )
            )
    except OSError:
        storage.delete_many(written_keys)
        raise
    job.input_keys = written_keys
    db.add_all([job, *samples])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        storage.delete_many(written_keys)
        raise HTTPException(
            status.HTTP_409_CONFLICT, "One or more photos were already enrolled."
        ) from exc
    dispatched = dispatch_job(job.id)
    return JobAccepted(
        job_id=job.id,
        state=JobState.PENDING if dispatched else JobState.DISPATCH_FAILED,
    )


@router.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_safe_browser_request)],
)
def delete_student(student_id: int, db: Session = Depends(get_db)) -> Response:
    student = db.execute(
        select(Student)
        .options(selectinload(Student.face_samples))
        .where(Student.id == student_id)
        .with_for_update()
    ).scalar_one_or_none()
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    keys = [sample.storage_key for sample in student.face_samples]
    try:
        storage.delete_many(keys)
    except OSError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Private photos could not be removed. Retry deleting this student.",
        ) from exc
    db.delete(student)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/recognition-jobs",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_safe_browser_request)],
)
def create_recognition_job(
    classroom_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JobAccepted:
    try:
        content = read_limited(classroom_photo.file, settings.classroom_max_bytes)
        image = validate_image(content)
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc
    finally:
        classroom_photo.file.close()

    job = ProcessingJob(kind=JobKind.RECOGNITION, state=JobState.PENDING)
    db.add(job)
    db.flush()
    key = storage.recognition_input_key(job.id, image.extension)
    storage.write(key, image.content)
    job.input_keys = [key]
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    dispatched = dispatch_job(job.id)
    return JobAccepted(
        job_id=job.id,
        state=JobState.PENDING if dispatched else JobState.DISPATCH_FAILED,
    )


@router.get("/jobs/{job_id}", response_model=ProcessingJobRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobRead:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    payload = ProcessingJobRead.model_validate(job)
    if payload.result and payload.result.get("output_key"):
        public_result = dict(payload.result)
        public_result.pop("output_key", None)
        public_result["processed_image_url"] = f"/api/jobs/{job.id}/image"
        payload = payload.model_copy(update={"result": public_result})
    return payload


@router.get("/jobs/{job_id}/image")
def get_job_image(job_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    output_key = (job.result or {}).get("output_key")
    if (job.result or {}).get("expired"):
        raise HTTPException(status.HTTP_410_GONE, "The processed image has expired.")
    if not output_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This job has no processed image.")
    path = storage.resolve(output_key)
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "The processed image has expired.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_safe_browser_request)],
)
def retry_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobAccepted:
    job = db.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    if job.state not in {JobState.PENDING, JobState.FAILED, JobState.DISPATCH_FAILED}:
        raise HTTPException(status.HTTP_409_CONFLICT, "This job is not eligible for retry.")
    if job.attempt_count >= 3 or job.error_code in {
        "invalid_image",
        "no_face",
        "no_faces",
        "multiple_faces",
        "enrollment_rejected",
        "target_deleted",
        "invalid_job_input",
        "expired",
    }:
        raise HTTPException(status.HTTP_409_CONFLICT, "This job cannot be retried.")
    job.state = JobState.PENDING
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    db.commit()
    dispatched = dispatch_job(job.id)
    return JobAccepted(
        job_id=job.id,
        state=JobState.PENDING if dispatched else JobState.DISPATCH_FAILED,
    )
