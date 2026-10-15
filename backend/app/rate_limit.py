"""PostgreSQL-backed API rate limiting shared by every application worker."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math
from threading import Lock

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import API_RATE_LIMIT_ENABLED, SECRET_KEY
from app.database import ApiRateLimit


# Broad protection for every state-changing API endpoint is applied by middleware.
API_WRITE_LIMIT = 120
API_WRITE_WINDOW_SECONDS = 60

# Tighter limits protect email delivery and password guessing without affecting
# normal use of the service.
AUTH_IP_LIMIT = 10
AUTH_EMAIL_LIMIT = 5
AUTH_WINDOW_SECONDS = 15 * 60
LOGIN_IP_LIMIT = 30
LOGIN_EMAIL_LIMIT = 20
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_SCOPE = "login-failure:email"
EMAIL_SEND_IP_LIMIT = 10
EMAIL_SEND_LIMIT = 10
EMAIL_SEND_WINDOW_SECONDS = 60 * 60
PASSWORD_RESET_IP_LIMIT = 5
PASSWORD_RESET_LIMIT = 3
PASSWORD_RESET_WINDOW_SECONDS = 60 * 60

# Processing is also protected per account, so users sharing one network do not
# block one another. The IP limit prevents mass account creation from one host.
TOOL_USER_LIMIT = 60
TOOL_IP_LIMIT = 120
TOOL_WINDOW_SECONDS = 60 * 60
STUDY_WORK_USER_LIMIT = 20
STUDY_WORK_IP_LIMIT = 40
STUDY_WORK_WINDOW_SECONDS = 60 * 60
RATE_LIMIT_CLEANUP_INTERVAL_SECONDS = 60 * 60

_cleanup_lock = Lock()
_last_cleanup_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def client_ip(request: Request) -> str:
    """Use the client address populated by the trusted reverse proxy/Uvicorn."""
    return request.client.host if request.client else "unknown"


def _key_hash(scope: str, identifier: str) -> str:
    value = f"{scope}:{identifier}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), value, hashlib.sha256).hexdigest()


def _retry_after_seconds(window_started_at: datetime, window_seconds: int, now: datetime) -> int:
    started_at = window_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    reset_at = started_at + timedelta(seconds=window_seconds)
    return max(1, math.ceil((reset_at - now).total_seconds()))


def _cleanup_expired_counters_if_due(db: Session, now: datetime) -> None:
    """Prune stale counters once per worker per hour, including production."""
    global _last_cleanup_at
    if _last_cleanup_at and now - _last_cleanup_at < timedelta(seconds=RATE_LIMIT_CLEANUP_INTERVAL_SECONDS):
        return

    with _cleanup_lock:
        if _last_cleanup_at and now - _last_cleanup_at < timedelta(seconds=RATE_LIMIT_CLEANUP_INTERVAL_SECONDS):
            return
        db.query(ApiRateLimit).filter(ApiRateLimit.expires_at < now).delete(
            synchronize_session=False
        )
        db.commit()
        _last_cleanup_at = now


def enforce_rate_limit(
        db: Session,
        *,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int,
) -> None:
    """Count one request or raise 429, using a short transaction and row lock.

    The stored key is an HMAC hash, therefore rate-limit rows contain neither a
    raw IP address nor an email address. A retry handles the only race: two
    workers creating the first counter for one key at the same moment.
    """
    if not API_RATE_LIMIT_ENABLED:
        return

    now = _now()
    key_hash = _key_hash(scope, identifier)
    _cleanup_expired_counters_if_due(db, now)

    for attempt in range(2):
        try:
            with db.begin_nested():
                counter = db.execute(
                    select(ApiRateLimit)
                    .where(ApiRateLimit.key_hash == key_hash)
                    .with_for_update()
                ).scalar_one_or_none()

                if counter is None:
                    counter = ApiRateLimit(
                        key_hash=key_hash,
                        scope=scope,
                        window_started_at=now,
                        request_count=1,
                        expires_at=now + timedelta(seconds=window_seconds),
                    )
                    db.add(counter)
                    # Flush now so a duplicate first insert can be retried.
                    db.flush()
                else:
                    window_started_at = counter.window_started_at
                    if window_started_at.tzinfo is None:
                        window_started_at = window_started_at.replace(tzinfo=timezone.utc)
                    if now >= window_started_at + timedelta(seconds=window_seconds):
                        counter.window_started_at = now
                        counter.request_count = 1
                    else:
                        counter.request_count += 1
                    counter.expires_at = now + timedelta(seconds=window_seconds)

                if counter.request_count > limit:
                    retry_after = _retry_after_seconds(counter.window_started_at, window_seconds, now)
                    raise HTTPException(
                        status_code=429,
                        detail="Слишком много запросов. Повторите попытку позже.",
                        headers={"Retry-After": str(retry_after)},
                    )

            db.commit()
            return
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise
        except Exception:
            db.rollback()
            raise
def enforce_auth_rate_limit(
        db: Session,
        request: Request,
        *,
        scope: str,
        email: str | None,
        ip_limit: int = AUTH_IP_LIMIT,
        email_limit: int = AUTH_EMAIL_LIMIT,
        window_seconds: int = AUTH_WINDOW_SECONDS,
) -> None:
    """Limit authentication attempts by both source network and email hash."""
    enforce_rate_limit(
        db,
        scope=f"{scope}:ip",
        identifier=client_ip(request),
        limit=ip_limit,
        window_seconds=window_seconds,
    )
    if email:
        enforce_rate_limit(
            db,
            scope=f"{scope}:email",
            identifier=str(email).strip().casefold(),
            limit=email_limit,
            window_seconds=window_seconds,
        )


def enforce_login_failure_lock(db: Session, email: str) -> None:
    """Block an email after repeated wrong-password attempts without storing it."""
    normalized_email = email.strip().casefold()
    if not normalized_email:
        return

    now = _now()
    counter = db.execute(
        select(ApiRateLimit).where(
            ApiRateLimit.key_hash == _key_hash(LOGIN_FAILURE_SCOPE, normalized_email)
        )
    ).scalar_one_or_none()
    if not counter or counter.request_count < LOGIN_FAILURE_LIMIT:
        return

    expires_at = counter.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return

    retry_after = _retry_after_seconds(
        counter.window_started_at,
        LOGIN_FAILURE_WINDOW_SECONDS,
        now,
    )
    raise HTTPException(
        status_code=429,
        detail="Слишком много неверных попыток входа. Повторите попытку позже.",
        headers={"Retry-After": str(retry_after)},
    )


def record_failed_login(db: Session, email: str) -> None:
    """Persist one failed login attempt for the temporary email lock."""
    enforce_rate_limit(
        db,
        scope=LOGIN_FAILURE_SCOPE,
        identifier=email.strip().casefold(),
        limit=LOGIN_FAILURE_LIMIT,
        window_seconds=LOGIN_FAILURE_WINDOW_SECONDS,
    )


def clear_failed_login_attempts(db: Session, email: str) -> None:
    """A successful login clears the failure counter for this email."""
    normalized_email = email.strip().casefold()
    if not normalized_email:
        return
    deleted = db.query(ApiRateLimit).filter(
        ApiRateLimit.key_hash == _key_hash(LOGIN_FAILURE_SCOPE, normalized_email)
    ).delete(synchronize_session=False)
    if deleted:
        db.commit()


def enforce_processing_rate_limit(
        db: Session,
        request: Request,
        *,
        user_id: int,
        is_study_work: bool = False,
) -> None:
    """Limit costly LLM calls by user and source network."""
    user_limit = STUDY_WORK_USER_LIMIT if is_study_work else TOOL_USER_LIMIT
    ip_limit = STUDY_WORK_IP_LIMIT if is_study_work else TOOL_IP_LIMIT
    window_seconds = STUDY_WORK_WINDOW_SECONDS if is_study_work else TOOL_WINDOW_SECONDS
    scope_prefix = "study-work" if is_study_work else "tool"
    enforce_rate_limit(
        db,
        scope=f"{scope_prefix}:user",
        identifier=str(user_id),
        limit=user_limit,
        window_seconds=window_seconds,
    )
    enforce_rate_limit(
        db,
        scope=f"{scope_prefix}:ip",
        identifier=client_ip(request),
        limit=ip_limit,
        window_seconds=window_seconds,
    )


def delete_expired_rate_limits(db: Session) -> int:
    """Remove expired counters; their keys are already non-identifying hashes."""
    deleted = db.query(ApiRateLimit).filter(ApiRateLimit.expires_at < _now()).delete(
        synchronize_session=False
    )
    db.commit()
    return deleted
