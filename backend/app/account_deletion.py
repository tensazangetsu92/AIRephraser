"""Account-deletion and one-time-free-entitlement safeguards."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from sqlalchemy.orm import Session

from app.config import SECRET_KEY
from app.database import DeletedAccountMarker


# This period is published in the privacy policy. It is intentionally finite:
# the marker is kept only for the anti-abuse purpose, not as an account archive.
FREE_ENTITLEMENT_MARKER_RETENTION_DAYS = 365


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalise_email(email: str) -> str:
    return email.strip().casefold()


def email_deletion_hmac(email: str) -> str:
    """Return a keyed, non-plain-email lookup value for the deletion marker."""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"humary:deleted-account-free-entitlement:{normalise_email(email)}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def has_consumed_free_entitlement(db: Session, email: str, *, now: datetime | None = None) -> bool:
    """Return whether a still-valid deletion marker exists for this email."""
    now = now or _utc_now()
    marker = db.get(DeletedAccountMarker, email_deletion_hmac(email))
    if not marker:
        return False
    if _as_utc(marker.expires_at) > now:
        return True

    db.delete(marker)
    db.flush()
    return False


def record_deleted_account_marker(db: Session, email: str, *, now: datetime | None = None) -> None:
    """Record the finite anti-abuse marker in the same transaction as deletion."""
    now = now or _utc_now()
    expires_at = now + timedelta(days=FREE_ENTITLEMENT_MARKER_RETENTION_DAYS)
    marker = db.get(DeletedAccountMarker, email_deletion_hmac(email))
    if marker:
        marker.deleted_at = now
        marker.expires_at = expires_at
        return
    db.add(DeletedAccountMarker(
        email_hmac=email_deletion_hmac(email),
        deleted_at=now,
        expires_at=expires_at,
    ))
