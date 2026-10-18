# SmartRoll

SmartRoll uses FastAPI, OpenCV, and dlib to enroll students from photos and
recognize faces in classroom images. Enrollment and recognition run in Celery
workers through Redis. PostgreSQL stores students, face embeddings, job states,
and recognition results.

Recognition results are suggestions for review. The app does not yet implement
authentication, class ownership, or saved, teacher-confirmed attendance.

## Architecture

The default `docker-compose.yml` runs four services:

| Service | Responsibility |
| --- | --- |
| `fastapi_api` | FastAPI/Jinja2 UI, JSON APIs, upload validation, job dispatch, and Alembic migrations |
| `fastapi_worker` | Celery worker for enrollment and classroom recognition |
| `fastapi_db` | PostgreSQL database for student records, embeddings, and jobs |
| `fastapi_redis` | Redis message broker for Celery |

The API returns a job ID after accepting an upload. The browser polls
`/api/jobs/{job_id}` for its status and result. Failed jobs can be retried when
eligible. Uploaded and annotated images live in a private named volume shared
by the API and worker; embeddings are stored in PostgreSQL.

## Start locally

Run commands from the repository root with Docker running.

1. For a fresh checkout, create the local environment file:

   ```bash
   cp .env.fastapi.example .env.fastapi
   ```

   Keep an existing `.env.fastapi` when restarting an existing installation.
   For a new installation, replace the password in both
   `FASTAPI_DATABASE_URL` and `FASTAPI_POSTGRES_PASSWORD`, and set a random
   `FASTAPI_CSRF_SECRET`. The environment file is ignored by Git.

2. Build and start the stack:

   ```bash
   docker compose --env-file .env.fastapi up -d --build
   ```

   The API applies existing Alembic migrations before starting Uvicorn.
   PostgreSQL and Redis must pass their health checks before the API and worker
   start. Open <http://127.0.0.1:8001>.

3. Verify the API and its dependencies:

   ```bash
   curl --fail http://127.0.0.1:8001/health
   curl --fail http://127.0.0.1:8001/ready
   ```

   Expect `{"status":"ok"}` and `{"status":"ready"}` respectively. Readiness
   checks PostgreSQL and Redis connectivity; it does not verify worker health.

Inspect services and logs:

```bash
docker compose --env-file .env.fastapi ps
docker compose --env-file .env.fastapi logs --tail=100 fastapi_api fastapi_worker
```

Stop the stack while retaining its data:

```bash
docker compose --env-file .env.fastapi down
```

The project name remains `smartroll-fastapi`, with the existing service and
named-volume names. Existing installations keep using the same PostgreSQL,
Redis, and private-upload volumes. Do not add `--volumes` when stopping the stack
unless you intend to delete that data.

## Tests

The application targets Python 3.10. Its Dockerfile installs the native build
dependencies required by dlib and OpenCV. For a fresh local environment, run
`python3.10 -m venv .venv` first; otherwise reuse the existing virtual environment.
Install the development dependencies and run pytest:

```bash
./.venv/bin/python -m pip install -r fastapi_app/requirements-dev.txt
PYTHONPATH=fastapi_app ./.venv/bin/python -m pytest -q fastapi_app/tests
```

The suite covers image validation, recognition rules, storage boundaries, job
retry and cleanup behavior, page/API contracts, and browser interactions. The
browser tests use synthetic data and a temporary local Uvicorn server. They
exercise responsive layouts, keyboard controls, and axe-core accessibility
checks; API responses in these browser scenarios are mocked. They do not prove
that a live PostgreSQL/Redis/Celery pipeline works.

Browser tests use Google Chrome when installed. Otherwise install Playwright's
Chromium once:

```bash
./.venv/bin/python -m playwright install chromium
```

Generated screenshots are written to the ignored `fastapi_app/var/screenshots/`
directory.

## Maintenance

Remove expired classroom inputs and annotated results using the configured
retention window:

```bash
docker compose --env-file .env.fastapi exec fastapi_api python -m app.maintenance
```

This command preserves job records, marks results expired, and excludes student
enrollment photos. Review the configured retention period before running it.

## Source layout

- `fastapi_app/app/`: routes, schemas, SQLAlchemy models, configuration, and jobs.
- `fastapi_app/app/services/`: recognition and private-storage helpers.
- `fastapi_app/app/templates/` and `fastapi_app/app/static/`: Jinja2 pages, CSS,
  local fonts, and browser JavaScript modules.
- `fastapi_app/alembic/`: database migrations.
- `fastapi_app/tests/`: pytest and Playwright tests.
- `fastapi_app/Dockerfile` and `fastapi_app/requirements*.txt`: application build
  and dependencies.
- `design.md`: UI design reference.

Existing photo datasets, image files, dumps, and local database backups are
retained as data and are not read by the application. The running app uses its
PostgreSQL database and private storage volume. Keep student photos, embeddings,
database exports, credentials, and private keys out of Git and test artifacts.

## License

MIT
