from __future__ import annotations

import uuid

from app import api
from app.models import JobKind, JobState, ProcessingJob


class _JobResult:
    def __init__(self, job: ProcessingJob) -> None:
        self.job = job

    def scalar_one_or_none(self) -> ProcessingJob:
        return self.job


class _JobSession:
    def __init__(self, job: ProcessingJob) -> None:
        self.job = job
        self.committed = False

    def execute(self, _statement) -> _JobResult:
        return _JobResult(self.job)

    def commit(self) -> None:
        self.committed = True


def test_pending_job_can_be_safely_redispatched(monkeypatch) -> None:
    job = ProcessingJob(
        id=uuid.uuid4(),
        kind=JobKind.RECOGNITION,
        state=JobState.PENDING,
        input_keys=["jobs/input.jpg"],
        attempt_count=0,
    )
    session = _JobSession(job)
    dispatched: list[uuid.UUID] = []
    monkeypatch.setattr(api, "dispatch_job", lambda job_id: dispatched.append(job_id) or True)

    response = api.retry_job(job.id, session)

    assert session.committed
    assert dispatched == [job.id]
    assert response.state == JobState.PENDING
