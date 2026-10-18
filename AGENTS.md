# Repository Guidelines

## Project structure

SmartRoll is a FastAPI facial-recognition application. Runtime code lives in
`fastapi_app/app/`: `api.py` defines JSON routes, `main.py` serves pages and health
checks, `models.py` contains SQLAlchemy models, and `tasks.py` handles Celery jobs.
Recognition and private-file helpers live in `app/services/`. The frontend uses
Jinja2 templates, local CSS/fonts, and small JavaScript modules in `app/static/`.
Alembic migrations live in `fastapi_app/alembic/`; tests live in
`fastapi_app/tests/`.

The default `docker-compose.yml` runs FastAPI, Celery, PostgreSQL, and Redis.
Application dependencies and its Dockerfile are under `fastapi_app/`.

## Development commands

Run these from the repository root:

- `docker compose --env-file .env.fastapi up -d --build`: build and start the stack;
  the API runs Alembic migrations before starting Uvicorn.
- `docker compose --env-file .env.fastapi ps`: inspect service status.
- `docker compose --env-file .env.fastapi logs --tail=100 fastapi_api fastapi_worker`:
  inspect API and worker logs.
- `docker compose --env-file .env.fastapi down`: stop services and retain volumes.
- `PYTHONPATH=fastapi_app ./.venv/bin/python -m pytest -q fastapi_app/tests`: run
  the application and browser tests.

Open `http://127.0.0.1:8001`. `/health` checks API liveness; `/ready` checks
PostgreSQL and Redis connectivity, not worker health.

## Coding and data conventions

Target Python 3.10, use four-space indentation, `PascalCase` classes, and
`snake_case` functions and modules. Keep changes focused and imports tidy.
Retain API contracts and job states unless the requested behavior changes them.
Recognition results are suggestions; confirmed attendance and authentication
are not implemented.

Use new Alembic migrations for schema changes. Do not rewrite applied migration
history, reset databases, or remove named volumes as part of code cleanup.
Maintain transaction boundaries and retry behavior when modifying processing.

## Verification

Use pytest with `test_<behavior>` names. Run targeted tests during development
and the full FastAPI suite before opening a PR. Browser tests need Chrome or
Playwright Chromium and permission to launch a local server. They use synthetic
fixtures and mock API results; passing them does not establish live worker or
database behavior. Changes to persistence, dispatch, or Docker runtime settings
also require appropriate PostgreSQL/Redis/Celery integration checks.

UI changes should preserve upload validation, polling, retry eligibility,
keyboard/focus behavior, responsive layouts, and accessible labels. Generated
test screenshots belong in ignored `fastapi_app/var/screenshots/`.

## Commits, configuration, and privacy

Use short, focused commit messages. PR descriptions should explain behavior,
checks run, environment or migration changes, and include screenshots for UI
changes. Preserve user edits and do not commit generated artifacts.

Use `.env.fastapi` for local secrets; `.env.fastapi.example` documents settings.
Do not commit credentials, private keys, real student photos, embeddings, or
database dumps. Existing datasets and backups are sensitive retained data and
are outside routine source-code cleanup. Uploads and processed images live in
the private storage volume; embeddings are stored in PostgreSQL.
