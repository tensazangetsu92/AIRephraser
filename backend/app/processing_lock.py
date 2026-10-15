"""Database-backed single-processing guard shared by all AI tools."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import USER_PROCESSING_LOCK_TTL_SECONDS
from app.database import UserProcessingLock


def _now() -> datetime:
    return datetime.now(timezone.utc)


def acquire_user_processing_lock(db: Session, user_id: int) -> str | None:
    """Atomically reserve one AI operation slot for a user."""
    now = _now()
    operation_id = str(uuid4())

    db.query(UserProcessingLock).filter(
        UserProcessingLock.expires_at <= now
    ).delete(synchronize_session=False)
    db.add(UserProcessingLock(
        user_id=user_id,
        operation_id=operation_id,
        expires_at=now + timedelta(seconds=USER_PROCESSING_LOCK_TTL_SECONDS),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return operation_id


def release_user_processing_lock(db: Session, user_id: int, operation_id: str) -> None:
    """Release only the exact operation that acquired the user lock."""
    try:
        db.query(UserProcessingLock).filter(
            UserProcessingLock.user_id == user_id,
            UserProcessingLock.operation_id == operation_id,
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


@asynccontextmanager
async def user_processing_guard(db: Session, user_id: int):
    operation_id = acquire_user_processing_lock(db, user_id)
    if operation_id is None:
        raise HTTPException(
            status_code=409,
            detail="У вас уже идёт обработка текста. Дождитесь её завершения.",
        )
    try:
        yield
    finally:
        release_user_processing_lock(db, user_id, operation_id)
