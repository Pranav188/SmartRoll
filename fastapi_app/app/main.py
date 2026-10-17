from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from redis import Redis
from sqlalchemy import text

from app.api import router as api_router
from app.config import settings
from app.database import SessionLocal
from app.security import get_csrf_token


APP_ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=APP_ROOT / "templates")

app = FastAPI(title=settings.app_name)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.csrf_secret.get_secret_value(),
    same_site="strict",
    https_only=settings.environment != "local",
)
app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        with Redis.from_url(settings.redis_url) as redis:
            redis.ping()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "A required service is unavailable."
        ) from exc
    return {"status": "ready"}


def _page_context(request: Request, active_page: str) -> dict[str, object]:
    return {
        "request": request,
        "active_page": active_page,
        "csrf_token": get_csrf_token(request),
    }


@app.get("/", response_class=HTMLResponse)
def attendance_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="attendance.html",
        context=_page_context(request, "attendance"),
    )


@app.get("/students", response_class=HTMLResponse)
def students_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="students.html",
        context=_page_context(request, "students"),
    )


@app.get("/students/add", response_class=HTMLResponse)
def add_student_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="add_student.html",
        context=_page_context(request, "add_student"),
    )
