# Repository Guidelines

## Project Structure & Module Organization

SmartRoll is a Django facial-recognition attendance app. The Django project lives in `smart_roll/` (`settings.py`, `urls.py`, `celery.py`, WSGI/ASGI entrypoints). The main app is `core/`, with models, views, routes, admin registration, migrations, and templates under `core/templates/core/`. Face-recognition helpers are in `core/face_recognition_engine.py`; utilities include `encode_faces.py`, `benchmark_async_latency.py`, and `stress_test.py`. Runtime assets are stored in `dataset/`, `media/`, `encodings.pickle`, and `screenshots/`; avoid committing private data or generated uploads unless intentionally updating fixtures or docs.

## Build, Test, and Development Commands

- `docker compose up -d --build`: build and start Django, Celery, PostgreSQL, and Redis.
- `docker compose exec web python manage.py migrate`: apply database migrations.
- `docker compose exec web python manage.py loaddata datadump.json`: load the sample dataset.
- `docker compose exec web python manage.py createsuperuser`: create an admin user.
- `docker compose logs web --tail=100`: inspect recent web service logs.
- `docker compose down`: stop the local stack.
- `python manage.py test` or `docker compose exec web python manage.py test`: run Django tests.
- `./.venv/bin/python benchmark_async_latency.py`: reproduce the async latency benchmark.

## Coding Style & Naming Conventions

Use Python 3.10-compatible Django code with 4-space indentation. Keep Django conventions: `PascalCase` for models/classes, `snake_case` for functions, variables, modules, and template names, and descriptive URL names. Place app behavior in `core/` unless it is project configuration, Celery setup, or a standalone script. No formatter config is checked in; keep imports tidy and avoid unrelated formatting churn.

## Testing Guidelines

Tests use Django's built-in runner. Add tests in `core/tests.py` or a `core/tests/` package as coverage grows. Name methods `test_<behavior>`, and cover models, views, and face-encoding job orchestration when changing those paths. Run `python manage.py test` before opening a PR; use Docker when the change depends on PostgreSQL, Redis, or Celery.

## Commit & Pull Request Guidelines

Recent commits use short, direct messages such as `refining readme` and `adding async latency benchmark`. Keep commits focused and imperative or action-oriented, for example `add attendance view tests`. Pull requests should include a concise summary, test commands run, any database or `.env` changes, and screenshots when UI templates or documentation images change. Link issues when available.

## Security & Configuration Tips

Configure secrets through `.env` as described in `README.md`; do not commit private keys, production passwords, or new `.pem` files. Treat `dataset/`, `media/`, and `encodings.pickle` as sensitive when they contain real student images or derived biometric data.
