from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select

from app.config import settings
from app.database import SessionLocal
from app.models import JobKind, JobState, ProcessingJob
from app.services.storage import PrivateStorage


def cleanup_completed_jobs(older_than_hours: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    now = datetime.now(timezone.utc)
    storage = PrivateStorage(settings.storage_root)
    cleaned = 0
    with SessionLocal.begin() as db:
        jobs = db.execute(
            select(ProcessingJob).where(
                ProcessingJob.kind == JobKind.RECOGNITION,
                or_(
                    and_(
                        ProcessingJob.state.in_({JobState.SUCCEEDED, JobState.FAILED}),
                        ProcessingJob.finished_at.is_not(None),
                        ProcessingJob.finished_at < cutoff,
                    ),
                    and_(
                        ProcessingJob.state.in_(
                            {
                                JobState.PENDING,
                                JobState.RUNNING,
                                JobState.DISPATCH_FAILED,
                            }
                        ),
                        ProcessingJob.created_at < cutoff,
                    ),
                ),
            )
        ).scalars().all()
        for job in jobs:
            result = job.result or {}
            keys = [*job.input_keys]
            if result.get("output_key"):
                keys.append(result["output_key"])
            storage.delete_many(keys)
            job.input_keys = []
            job.result = {"expired": True}
            if job.state in {
                JobState.PENDING,
                JobState.RUNNING,
                JobState.DISPATCH_FAILED,
            }:
                job.state = JobState.FAILED
                job.error_code = "expired"
                job.error_message = "This recognition job expired before it finished."
                job.finished_at = now
            cleaned += 1
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartRoll maintenance commands")
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=settings.completed_job_retention_hours,
        help="Remove completed job files older than this many hours.",
    )
    args = parser.parse_args()
    if args.older_than_hours < 1:
        parser.error("--older-than-hours must be at least 1")
    cleaned = cleanup_completed_jobs(args.older_than_hours)
    print(f"Cleaned {cleaned} completed job(s).")


if __name__ == "__main__":
    main()
