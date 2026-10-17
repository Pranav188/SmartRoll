# SmartRoll FastAPI application

This is an isolated, side-by-side replacement for the Django application. It uses its own PostgreSQL database, Redis instance, private file volume, environment variables, and port. Starting it does not migrate or remove Django data.

## Browser UI

The FastAPI pages retain the original attendance, enrollment, and roster workflow with a restrained dark theme, flat surfaces, consistent navigation, and responsive forms. Decorative glows, blur, and scanning animations are omitted. Templates live in `app/templates/`, styling in `app/static/css/smartroll.css`, and browser API calls in `app/static/js/`.

The UI retains the FastAPI upload validation, enrollment status, job polling, retry controls, and recognition review states. Recognition results remain suggestions; this version does not save confirmed attendance. Authentication is a future backend feature.

## Start the local stack

1. Copy `.env.fastapi.example` to `.env.fastapi` and replace the database password and CSRF secret. The purpose is to keep FastAPI settings separate from Django. The expected result is a local file named `.env.fastapi`; it is ignored by Git.

2. Run:

   ```bash
   docker compose --env-file .env.fastapi -f compose.fastapi.yml up --build
   ```

   This builds Python 3.10 images, upgrades the empty FastAPI database through Alembic, and starts PostgreSQL, Redis, one Celery worker, and Uvicorn. The expected result is a reachable application at `http://127.0.0.1:8001` and worker logs showing it is ready.

3. Check liveness:

   ```bash
   curl --fail http://127.0.0.1:8001/health
   ```

   This confirms the API process is responding. The expected output is `{"status":"ok"}`.

4. Check dependencies:

   ```bash
   curl --fail http://127.0.0.1:8001/ready
   ```

   This confirms PostgreSQL and Redis are reachable from the API. The expected output is `{"status":"ready"}`. A `503` means the process is alive but a required dependency is unavailable.

Stop only this isolated stack with:

```bash
docker compose --env-file .env.fastapi -f compose.fastapi.yml down
```

The purpose is to stop the FastAPI containers without touching Django. The expected result is stopped containers with the three named FastAPI volumes retained.

## Preview the legacy photo import

The preview reads `datadump.json` and `/Users/pranav/docs/dataset`, validates every image, and creates a local CSV manifest. It does not connect to PostgreSQL, copy photos, or dispatch work.

```bash
docker compose --env-file .env.fastapi -f compose.fastapi.yml run --rm --no-deps \
  -v /Users/pranav/projects/SmartRoll/datadump.json:/imports/datadump.json:ro \
  -v /Users/pranav/docs/dataset:/imports/student-photos:ro \
  -v /Users/pranav/projects/SmartRoll/fastapi_app/var:/app/var \
  fastapi_api python -m app.importer preview \
  --dump /imports/datadump.json \
  --source /imports/student-photos \
  --manifest /app/var/import/student-photo-map.csv
```

The expected output reports 14 photo folders, 8 exact matches, 6 unresolved folders, and 1 dump student without an exact photo folder. The generated manifest is ignored by Git.

Inspect `fastapi_app/var/import/student-photo-map.csv`. Every row must be deliberately set to one of:

- `map`: use an existing dump student ID and exact dump name.
- `create`: create a new student using the supplied name and a blank ID.
- `skip`: do not import that photo; leave the target ID and name blank.

Set `confirmed` to `true` on every row, including skipped rows. Apply refuses the whole operation if any row is unconfirmed, duplicated, changed, invalid, or unsafe.

## Apply the confirmed import

Start the stack and ensure `/ready` succeeds, then run:

```bash
docker compose --env-file .env.fastapi -f compose.fastapi.yml run --rm \
  -v /Users/pranav/projects/SmartRoll/datadump.json:/imports/datadump.json:ro \
  -v /Users/pranav/docs/dataset:/imports/student-photos:ro \
  -v /Users/pranav/projects/SmartRoll/fastapi_app/var:/app/var \
  fastapi_api python -m app.importer apply \
  --dump /imports/datadump.json \
  --source /imports/student-photos \
  --manifest /app/var/import/student-photo-map.csv
```

The purpose is to preserve mapped legacy IDs, create approved students and samples, copy source images into private generated keys, and queue enrollment jobs. The expected output is a JSON report containing created counts and job IDs. Re-running the same confirmed manifest should report existing samples and create no duplicate enrollment work. The source photo mount is read-only, and apply rechecks each manifest hash before committing.

## Tests and maintenance

Run the isolated Python tests with:

```bash
PYTHONPATH=fastapi_app ./.venv/bin/python -m pytest -q fastapi_app/tests
```

The purpose is to exercise image validation, recognition ambiguity rules, storage boundaries, and importer safety. The expected output is a passing test count with no failures.

For the browser suite, install development dependencies once with `./.venv/bin/python -m pip install -r fastapi_app/requirements-dev.txt`. Its purpose is to add Playwright to the ignored project environment; the expected output ends with a successful install. On machines without Google Chrome, run `./.venv/bin/python -m playwright install chromium`; this installs Playwright's test browser and should end without an error. The same pytest command then runs responsive screenshots, synthetic recognition states, keyboard interactions, and local axe-core checks. Screenshots are written to the ignored `fastapi_app/var/screenshots/` directory and never use supplied student photos.

Remove staged and annotated job files after the configured retention window with:

```bash
docker compose --env-file .env.fastapi -f compose.fastapi.yml exec fastapi_api python -m app.maintenance
```

The expected output is `Cleaned N completed job(s).` Database job records remain, while completed results and abandoned classroom uploads become explicit expired states. Enrollment-job inputs are excluded because they are the student's private face samples and are removed when that student is deleted.

## Current acceptance boundary

FastAPI should not replace Django as the local default until a fresh Alembic upgrade, real Redis and Celery processing, browser flows, accessibility checks, and responsive screenshots all pass. Authentication, classes, persistent attendance, reports, production deployment, and Django removal are outside this application.
