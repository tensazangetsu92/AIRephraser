"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import router
from app.config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    COOKIE_SECURE,
    CORS_CREDENTIALS,
    CORS_HEADERS,
    CORS_METHODS,
    CORS_ORIGINS,
    ENABLE_IN_APP_SCHEDULER,
    FRONTEND_DIR,
    SECRET_KEY,
)
from app.database import SessionLocal, delete_old_history
from app.oauth import router as google_router


logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def cleanup_job() -> None:
    """Remove history records older than the retention period."""
    db = SessionLocal()
    try:
        deleted = delete_old_history(db, days=90)
        logger.info("History cleanup completed; deleted=%s", deleted)
    except Exception:
        logger.exception("History cleanup failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if ENABLE_IN_APP_SCHEDULER:
        scheduler.add_job(
            cleanup_job,
            "interval",
            days=1,
            id="history_cleanup",
            replace_existing=True,
        )
        scheduler.start()
        cleanup_job()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="humary_session",
    max_age=3600,
    same_site="lax",
    https_only=COOKIE_SECURE,
)

app.include_router(router)
app.include_router(google_router)

for directory, mount_path in (("css", "/css"), ("js", "/js"), ("images", "/images")):
    path = FRONTEND_DIR / directory
    if path.exists():
        app.mount(mount_path, StaticFiles(directory=str(path)), name=directory)


@app.get("/api", tags=["info"])
async def api_info():
    return {"name": API_TITLE, "version": API_VERSION, "docs": "/docs", "status": "running"}


@app.get("/health", tags=["info"])
async def health_check():
    return {"status": "ok"}
