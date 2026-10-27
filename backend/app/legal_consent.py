"""Server-side record of acceptance of Humary legal documents."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import User


# This value must match the publication date shown on /terms and /privacy.
LEGAL_DOCUMENTS_VERSION = "2026-10-22"
LEGAL_CONSENT_MAX_AGE = timedelta(minutes=30)
_VERSION_SESSION_KEY = "legal_documents_version"
_TIME_SESSION_KEY = "legal_documents_accepted_at"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session(request: Request) -> dict:
    """Return the signed session, including for isolated route unit tests."""
    request.scope.setdefault("session", {})
    return request.session


def record_pending_legal_consent(request: Request) -> None:
    """Record the affirmative action immediately before an auth attempt."""
    session = _session(request)
    session[_VERSION_SESSION_KEY] = LEGAL_DOCUMENTS_VERSION
    session[_TIME_SESSION_KEY] = _utc_now().isoformat()


def require_pending_legal_consent(request: Request) -> None:
    """Reject authentication attempts that did not first accept the documents."""
    session = _session(request)
    accepted_at = session.get(_TIME_SESSION_KEY)
    if session.get(_VERSION_SESSION_KEY) != LEGAL_DOCUMENTS_VERSION or not isinstance(accepted_at, str):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Примите Условия использования и ознакомьтесь с Политикой конфиденциальности.",
        )
    try:
        timestamp = datetime.fromisoformat(accepted_at)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
    except ValueError:
        timestamp = None

    if timestamp is None or timestamp < _utc_now() - LEGAL_CONSENT_MAX_AGE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите принятие Условий использования ещё раз.",
        )


def has_current_legal_consent(user: User) -> bool:
    """Return whether the account accepted the currently published documents."""
    return (
        user.legal_documents_version == LEGAL_DOCUMENTS_VERSION
        and user.legal_accepted_at is not None
    )


def persist_legal_consent(db: Session, user: User) -> bool:
    """Store the accepted document version once the account identity is proven."""
    if has_current_legal_consent(user):
        return False
    user.legal_documents_version = LEGAL_DOCUMENTS_VERSION
    user.legal_accepted_at = _utc_now()
    return True
