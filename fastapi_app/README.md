# FastAPI application

See the [repository README](../README.md) for setup, Docker Compose commands,
testing, and maintenance. Run those commands from the repository root.

- `app/`: FastAPI routes, models, services, Celery jobs, templates, and static assets.
- `alembic/`: versioned PostgreSQL schema migrations.
- `tests/`: application and browser tests using synthetic fixtures.
- `Dockerfile`: the API/worker image, built by the root Compose configuration.
- `requirements.txt` and `requirements-dev.txt`: runtime and test dependencies.

Local secrets remain in the root `.env.fastapi` file. The API is available at
`http://127.0.0.1:8001` when the stack is running.
