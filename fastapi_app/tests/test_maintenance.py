from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app import maintenance
from app.models import JobKind, JobState, ProcessingJob


class _Scalars:
    def __init__(self, jobs: list[ProcessingJob]) -> None:
        self.jobs = jobs

    def all(self) -> list[ProcessingJob]:
        return self.jobs


class _Result:
    def __init__(self, jobs: list[ProcessingJob]) -> None:
        self.jobs = jobs

    def scalars(self) -> _Scalars:
        return _Scalars(self.jobs)


class _Session:
    def __init__(self, jobs: list[ProcessingJob]) -> None:
        self.jobs = jobs

    def execute(self, _statement) -> _Result:
        return _Result(self.jobs)


class _SessionContext:
    def __init__(self, jobs: list[ProcessingJob]) -> None:
        self.session = _Session(jobs)

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *_args) -> None:
        return None


class _SessionFactory:
    def __init__(self, jobs: list[ProcessingJob]) -> None:
        self.jobs = jobs

    def begin(self) -> _SessionContext:
        return _SessionContext(self.jobs)


class _Storage:
    deleted: list[str] = []

    def __init__(self, _root) -> None:
        type(self).deleted = []

    def delete_many(self, keys: list[str]) -> None:
        type(self).deleted.extend(keys)


def test_stale_recognition_upload_becomes_expired(monkeypatch) -> None:
    job = ProcessingJob(
        id=uuid.uuid4(),
        kind=JobKind.RECOGNITION,
        state=JobState.DISPATCH_FAILED,
        input_keys=["jobs/input.jpg"],
        attempt_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    monkeypatch.setattr(maintenance, "SessionLocal", _SessionFactory([job]))
    monkeypatch.setattr(maintenance, "PrivateStorage", _Storage)

    cleaned = maintenance.cleanup_completed_jobs(24)

    assert cleaned == 1
    assert _Storage.deleted == ["jobs/input.jpg"]
    assert job.state == JobState.FAILED
    assert job.error_code == "expired"
    assert job.result == {"expired": True}
    assert job.input_keys == []
