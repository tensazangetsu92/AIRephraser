# app/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
import hashlib
import hmac
import logging
import os
import secrets
from uuid import uuid4
from sqlalchemy import func

from app.database import get_db, User, UserRefreshSession
from app.config import (
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_REFRESH_TOKEN_ABSOLUTE_DAYS,
    AUTH_REFRESH_TOKEN_IDLE_DAYS,
    COOKIE_SECURE,
    SECRET_KEY,
)
from app.subscription import get_user_subscription, grant_study_work_trial
from app.config import DEV_LOG_VERIFICATION_CODE
from app.email_utils import (
    VerificationEmailDeliveryError,
    generate_verification_code,
    send_verification_email,
    store_verification_code,
    verify_code,
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = AUTH_ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_COOKIE_NAME = "humary_refresh_token"
security = HTTPBearer()
logger = logging.getLogger("uvicorn.error")

# bcrypt is deliberately fed a SHA-256 digest. This removes bcrypt's 72-byte
# input limit while retaining a unique bcrypt salt and its work factor.
PASSWORD_BCRYPT_ROUNDS = 12
_LEGACY_PASSWORD_SALT = "humary_salt_2024"
_DUMMY_PASSWORD_HASH = "$2b$12$dzKGpojKG/A2A6oB.FSGzuU7o7Z8BNwVNf8X/ZYvVgmSvunLS6QmS"


def _password_digest(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def _legacy_password_hash(password: str) -> str:
    """Reproduce the former hash only while accounts are being upgraded."""
    return hashlib.sha256((password + _LEGACY_PASSWORD_SALT).encode("utf-8")).hexdigest()


def _is_bcrypt_hash(password_hash: str) -> bool:
    return password_hash.startswith(("$2a$", "$2b$", "$2y$"))


def get_hash_password(password: str) -> str:
    """Hash a password with a per-password bcrypt salt and work factor."""
    return bcrypt.hashpw(
        _password_digest(password),
        bcrypt.gensalt(rounds=PASSWORD_BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if _is_bcrypt_hash(hashed_password):
        try:
            return bcrypt.checkpw(
                _password_digest(plain_password),
                hashed_password.encode("utf-8"),
            )
        except (TypeError, ValueError):
            return False

    # Existing accounts used a legacy SHA-256 hash. Keep them accessible once,
    # then migrate the hash immediately after a successful login.
    return hmac.compare_digest(_legacy_password_hash(plain_password), hashed_password)


def get_user_by_email(db: Session, email: str):
    normalized_email = email.strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized_email).first()


def create_user(db: Session, email: str, password: str):
    """Создает нового пользователя с бесплатной подпиской"""
    hashed_password = get_hash_password(password)
    db_user = User(
        email=email,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Автоматически создаём бесплатную подписку для нового пользователя
    get_user_subscription(db, db_user.id)
    grant_study_work_trial(db, db_user.id)

    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        # Keep the response time close to that for a real account so login is
        # not an email-existence oracle.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not _is_bcrypt_hash(user.password_hash):
        user.password_hash = get_hash_password(password)
        db.commit()
    return user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user_access_token(user: User) -> str:
    """Create an access token addressed to the immutable internal user id."""
    return create_access_token(data={"sub": f"user:{user.id}"})


def _refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_session(db: Session, user: User) -> str:
    """Create a persistent server-side session and return its opaque secret."""
    now = datetime.now(timezone.utc)
    db.query(UserRefreshSession).filter(
        UserRefreshSession.expires_at <= now,
    ).delete(synchronize_session=False)

    refresh_token = secrets.token_urlsafe(48)
    db.add(UserRefreshSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=_refresh_token_hash(refresh_token),
        last_used_at=now,
        expires_at=now + timedelta(days=AUTH_REFRESH_TOKEN_ABSOLUTE_DAYS),
    ))
    db.commit()
    return refresh_token


def get_user_from_refresh_session(db: Session, refresh_token: str | None) -> User | None:
    """Return the active user for a server-side refresh session without rotating it."""
    if not refresh_token:
        return None

    now = datetime.now(timezone.utc)
    session = db.query(UserRefreshSession).filter(
        UserRefreshSession.token_hash == _refresh_token_hash(refresh_token),
        UserRefreshSession.revoked_at.is_(None),
        UserRefreshSession.expires_at > now,
        UserRefreshSession.last_used_at > now - timedelta(days=AUTH_REFRESH_TOKEN_IDLE_DAYS),
    ).first()
    if not session:
        return None

    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    return user


def refresh_active_session(db: Session, refresh_token: str | None) -> User | None:
    """Refresh session activity without replacing its browser secret.

    The opaque session secret intentionally remains stable for its lifetime.
    Replacing it on every access-token refresh creates a race: two tabs (or a
    navigation and an API request) can send the same old cookie, after which
    one of them appears logged out. The server still validates, expires and
    can revoke this session on every use.
    """
    if not refresh_token:
        return None

    now = datetime.now(timezone.utc)
    session = db.query(UserRefreshSession).filter(
        UserRefreshSession.token_hash == _refresh_token_hash(refresh_token),
        UserRefreshSession.revoked_at.is_(None),
        UserRefreshSession.expires_at > now,
        UserRefreshSession.last_used_at > now - timedelta(days=AUTH_REFRESH_TOKEN_IDLE_DAYS),
    ).first()
    if not session:
        return None

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or not user.is_active:
        session.revoked_at = now
        db.commit()
        return None

    session.last_used_at = now
    db.commit()
    return user


def revoke_refresh_session(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return

    session = db.query(UserRefreshSession).filter(
        UserRefreshSession.token_hash == _refresh_token_hash(refresh_token),
        UserRefreshSession.revoked_at.is_(None),
    ).first()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_refresh_sessions(db: Session, user_id: int) -> None:
    db.query(UserRefreshSession).filter(
        UserRefreshSession.user_id == user_id,
        UserRefreshSession.revoked_at.is_(None),
    ).update({UserRefreshSession.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()


def set_refresh_token_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=AUTH_REFRESH_TOKEN_ABSOLUTE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_refresh_token_cookie(response) -> None:
    # Mirror the original cookie attributes so every browser reliably removes
    # the protected refresh cookie on logout or a failed refresh.
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise HTTPException(status_code=401, detail="Неверный токен")

        if subject.startswith("user:"):
            try:
                user_id = int(subject.removeprefix("user:"))
            except ValueError:
                raise HTTPException(status_code=401, detail="Неверный токен")
            user = db.query(User).filter(User.id == user_id).first()
        else:
            # Existing access tokens are email-based; accept them until expiry.
            user = db.query(User).filter(User.email == subject).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Пользователь не найден")

        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")


# Временное хранение данных пользователя до подтверждения
pending_users = {}


def cleanup_expired_pending_users():
    """Удаляет истёкшие коды из временного хранилища"""
    now = datetime.now()
    expired = [
        email for email, data in pending_users.items()
        if now > data["expires_at"]
    ]
    for email in expired:
        del pending_users[email]
    if expired:
        logger.info("Removed %s expired pending registrations", len(expired))


def create_pending_user(email: str, password_hash: str):
    """Сохраняет пользователя до подтверждения email"""
    # Очищаем истекшие коды перед созданием нового
    cleanup_expired_pending_users()

    code = generate_verification_code()
    pending_user = {
        "password_hash": password_hash,
        "verification_code": code,
        "expires_at": datetime.now() + timedelta(minutes=10)
    }
    if DEV_LOG_VERIFICATION_CODE:
        logger.warning("Development verification code for %s: %s", email, code)
    elif not send_verification_email(email, code):
        raise VerificationEmailDeliveryError("Verification email delivery failed")
    pending_users[email] = pending_user
    return code


def verify_and_create_user(db: Session, email: str, code: str):
    """Подтверждает email и создает пользователя"""
    # Очищаем истекшие коды перед проверкой
    cleanup_expired_pending_users()

    if email not in pending_users:
        return None, "Код не найден или истек"

    pending = pending_users[email]
    if datetime.now() > pending["expires_at"]:
        del pending_users[email]
        return None, "Код подтверждения истек"

    if pending["verification_code"] != code:
        return None, "Неверный код подтверждения"

    # Создаем пользователя
    db_user = User(
        email=email,
        password_hash=pending["password_hash"],
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    get_user_subscription(db, db_user.id)
    grant_study_work_trial(db, db_user.id)

    # Удаляем из временного хранилища
    del pending_users[email]

    return db_user, None
