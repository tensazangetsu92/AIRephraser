"""FastAPI application entry point."""

import logging
import re
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import Scope

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
    IS_PRODUCTION,
    LOG_LEVEL,
    SECRET_KEY,
    SESSION_SECRET_KEY,
)
from app.database import SessionLocal, delete_old_history
from app.rate_limit import (
    API_WRITE_LIMIT,
    API_WRITE_WINDOW_SECONDS,
    client_ip,
    delete_expired_rate_limits,
    enforce_rate_limit,
)
from app.upload_validation import MAX_DOCX_REQUEST_SIZE_BYTES
from app.yandex_oauth import router as yandex_router
from app.vk_oauth import router as vk_router


logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

_SENSITIVE_LOG_VALUE_PATTERN = re.compile(
    r"""(?ix)
    (?P<key>
        [\"']?(?:password|current_password|new_password|password_hash|smtp_password|
        authorization|proxy-authorization|access_token|refresh_token|id_token|token|cookie|
        code|code_verifier|code_challenge|state|device_id|ext_id|
        (?:x-)?api[_-]?key|client_secret|gigachat_auth_key|gpt_auth_key|yookassa_secret_key|
        robokassa_password[12])[\"']?
    )
    \s*(?P<separator>[:=])\s*
    (?P<value>
        bearer\s+[^\s,;}&]+ |
        \"(?:[^\"\\]|\\.)*\" |
        '(?:[^'\\]|\\.)*' |
        [^\s,;}&]+
    )
    """
)

_USER_TEXT_LOG_VALUE_PATTERN = re.compile(
    r"""(?isx)
    (?P<key>
        [\"']?(?:text|source_text|original_text|result_text|content|prompt|payload|body|input)[\"']?
    )
    \s*(?P<separator>[:=])\s*
    (?P<value>.*)$
    """
)


def _redact_sensitive_log_values(message: str) -> str:
    """Prevent credentials and full user text from reaching application logs."""
    sanitized = _SENSITIVE_LOG_VALUE_PATTERN.sub(
        lambda match: f"{match.group('key')}{match.group('separator')}[REDACTED]",
        message,
    )
    return _USER_TEXT_LOG_VALUE_PATTERN.sub(
        lambda match: f"{match.group('key')}{match.group('separator')}[REDACTED]",
        sanitized,
    )


class SensitiveLogFilter(logging.Filter):
    """Redact known credential fields after logging has interpolated arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        sanitized_message = _redact_sensitive_log_values(message)
        if sanitized_message != message:
            record.msg = sanitized_message
            record.args = ()
        return True


def configure_logging() -> None:
    """Use a stable production-friendly format for application log records."""
    numeric_level = getattr(logging, LOG_LEVEL)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger().setLevel(numeric_level)
    # Most application modules use uvicorn.error so their records share the
    # same destination as Uvicorn/Docker logs without extra handlers.
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(numeric_level)

    # Uvicorn installs handlers before importing the application. Add the
    # redaction filter to both possible handler sets, without adding handlers
    # or duplicating records.
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(numeric_level)
    for configured_logger in (logging.getLogger(), uvicorn_error_logger, uvicorn_access_logger):
        for handler in configured_logger.handlers:
            if not any(isinstance(item, SensitiveLogFilter) for item in handler.filters):
                handler.addFilter(SensitiveLogFilter())


configure_logging()


class CachedStaticFiles(StaticFiles):
    """Serve versioned frontend assets with long-lived browser caching."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code < 400:
            query = parse_qs(scope.get("query_string", b"").decode("ascii", "ignore"))
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
                if query.get("v")
                else "public, max-age=3600"
            )
        return response


def cleanup_job() -> None:
    """Remove history records and expired rate-limit counters."""
    db = SessionLocal()
    try:
        history_deleted = delete_old_history(db, days=90)
        rate_limit_deleted = delete_expired_rate_limits(db)
        logger.info(
            "Cleanup completed; history_deleted=%s rate_limit_deleted=%s",
            history_deleted,
            rate_limit_deleted,
        )
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
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)


def _is_state_changing_api_request(request: Request) -> bool:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    path = request.url.path
    return (
        path in {"/register", "/login", "/humanize", "/detect", "/paraphrase"}
        or path.startswith("/auth/")
        or path.startswith("/study-work/")
        or path.startswith("/subscription/")
        or (path.startswith("/payments/") and path != "/payments/robokassa/result")
        or path.startswith("/user/")
    )


@app.middleware("http")
async def limit_state_changing_api_requests(request: Request, call_next):
    """Apply a broad per-IP ceiling before any state-changing API endpoint."""
    if not _is_state_changing_api_request(request):
        return await call_next(request)

    db = SessionLocal()
    try:
        enforce_rate_limit(
            db,
            scope="api-write:ip",
            identifier=client_ip(request),
            limit=API_WRITE_LIMIT,
            window_seconds=API_WRITE_WINDOW_SECONDS,
        )
    except HTTPException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail},
            headers=error.headers,
        )
    finally:
        db.close()

    return await call_next(request)


@app.middleware("http")
async def reject_oversized_docx_uploads(request: Request, call_next):
    """Reject known oversized multipart uploads before FastAPI parses them."""
    if request.method == "POST" and request.url.path == "/study-work/docx/process":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_DOCX_REQUEST_SIZE_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Файл Word больше 10 МБ."},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Некорректный размер загрузки."})
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(_: Request, call_next):
    """Apply browser-side XSS and clickjacking protections to every response."""
    response = await call_next(_)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://mc.yandex.ru; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://mc.yandex.ru; "
        "worker-src 'self' blob: https://cdnjs.cloudflare.com; "
        "object-src 'none'; base-uri 'self'; form-action 'self' https://robokassa.ru https://*.robokassa.ru; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="humary_session",
    max_age=3600,
    same_site="lax",
    https_only=COOKIE_SECURE,
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error while handling %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Временная ошибка базы данных. Попробуйте ещё раз позже."},
    )

app.include_router(router)
app.include_router(yandex_router)
app.include_router(vk_router)

for directory, mount_path in (
        ("css", "/css"),
        ("js", "/js"),
        ("images", "/images"),
        ("fonts", "/fonts"),
        ("vendor", "/vendor"),
):
    path = FRONTEND_DIR / directory
    if path.exists():
        app.mount(mount_path, CachedStaticFiles(directory=str(path)), name=directory)


@app.get("/api", tags=["info"])
async def api_info():
    return {"name": API_TITLE, "version": API_VERSION, "docs": "/docs", "status": "running"}


@app.get("/health", tags=["info"])
async def health_check():
    """Readiness endpoint for the host and an external uptime monitor."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Do not expose database details or credentials through a public URL.
        logger.warning("Health check failed: database is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable.",
        )
    finally:
        db.close()

    return {"status": "ok", "checks": {"database": "ok"}}
