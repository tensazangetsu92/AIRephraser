# app/routers/auth_routes.py
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from datetime import datetime, timedelta, timezone
import math
import logging
import hashlib
import hmac
import secrets
from sqlalchemy.orm import Session

from app.models import EmailCodeConfirm, EmailCodeRequest, PasswordResetConfirm, PasswordResetRequest, UserLogin, UserRegister, Token
from app.database import EmailLoginCode, get_db, PasswordResetCode, User
from auth import (
    authenticate_user,
    clear_refresh_token_cookie,
    create_user_access_token,
    create_refresh_session,
    get_user_by_email,
    get_hash_password,
    pending_users,
    create_pending_user,
    REFRESH_COOKIE_NAME,
    revoke_refresh_session,
    revoke_all_refresh_sessions,
    refresh_active_session,
    set_refresh_token_cookie,
)
from app.config import DEV_LOG_VERIFICATION_CODE, SECRET_KEY
from app.email_utils import (
    VerificationEmailDeliveryError,
    generate_password_reset_code,
    send_email_login_code,
    send_password_reset_email,
)
from app.rate_limit import (
    EMAIL_SEND_IP_LIMIT,
    EMAIL_SEND_LIMIT,
    EMAIL_SEND_WINDOW_SECONDS,
    LOGIN_EMAIL_LIMIT,
    LOGIN_IP_LIMIT,
    LOGIN_WINDOW_SECONDS,
    PASSWORD_RESET_IP_LIMIT,
    PASSWORD_RESET_LIMIT,
    PASSWORD_RESET_WINDOW_SECONDS,
    clear_failed_login_attempts,
    enforce_auth_rate_limit,
    enforce_login_failure_lock,
    record_failed_login,
)
from app.subscription import initialise_new_user_entitlements
from app.legal_consent import (
    LEGAL_DOCUMENTS_VERSION,
    persist_legal_consent,
    record_pending_legal_consent,
    require_pending_legal_consent,
)

router = APIRouter(tags=["auth"])
logger = logging.getLogger("uvicorn.error")

PASSWORD_RESET_CODE_LIFETIME = timedelta(minutes=10)
PASSWORD_RESET_RESEND_DELAY = timedelta(seconds=60)
PASSWORD_RESET_MAX_ATTEMPTS = 5
EMAIL_CODE_LIFETIME = timedelta(minutes=10)
EMAIL_CODE_RESEND_DELAY = timedelta(seconds=60)
EMAIL_CODE_MAX_ATTEMPTS = 5


@router.post("/auth/legal-consent")
async def accept_legal_documents(request: Request):
    """Store a short-lived, signed pre-auth acknowledgement in the session."""
    record_pending_legal_consent(request)
    return {"success": True, "version": LEGAL_DOCUMENTS_VERSION}


def _utc_now() -> datetime:
    """Return an aware UTC timestamp for PostgreSQL timestamptz columns."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalise SQLite's naive datetimes and PostgreSQL's aware datetimes."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _password_reset_code_hash(user_id: int, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode("utf-8")).hexdigest()


def _email_login_code_hash(email: str, code: str) -> str:
    """Key the short numeric code with the app secret before persisting it."""
    value = f"{email}:{code}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), value, hashlib.sha256).hexdigest()


def _token_response(user: User) -> Token:
    return Token(
        access_token=create_user_access_token(user),
        token_type="bearer",
        user={"email": user.email, "id": user.id, "display_name": user.display_name, "avatar_url": user.avatar_url},
    )


@router.post("/auth/email-code/request")
async def request_email_code(
        data: EmailCodeRequest,
        request: Request,
        db: Session = Depends(get_db),
):
    """Issue a passwordless sign-in code for an existing or new account."""
    require_pending_legal_consent(request)
    email = str(data.email).strip().casefold()
    now = _utc_now()
    recent_code = db.query(EmailLoginCode).filter(
        EmailLoginCode.email == email,
        EmailLoginCode.used_at.is_(None),
        EmailLoginCode.expires_at > now,
        EmailLoginCode.created_at >= now - EMAIL_CODE_RESEND_DELAY,
    ).order_by(EmailLoginCode.created_at.desc()).first()
    if recent_code:
        retry_after = max(
            1,
            math.ceil((_as_utc(recent_code.created_at) + EMAIL_CODE_RESEND_DELAY - now).total_seconds()),
        )
        if retry_after <= int(EMAIL_CODE_RESEND_DELAY.total_seconds()):
            # Reusing an existing code is a normal flow after a reload. It is
            # not an error and must not consume the email-delivery quota.
            return {
                "success": True,
                "message": "Код уже отправлен. Используйте письмо или повторите отправку позже.",
                "email": email,
                "already_sent": True,
                "retry_after": retry_after,
            }

        # Records created before UTC normalisation can have a clock-shifted
        # created_at value. They must not block the user for tens of minutes.
        recent_code.used_at = now
        db.commit()

    enforce_auth_rate_limit(
        db,
        request,
        scope="email-code-request",
        email=email,
        ip_limit=EMAIL_SEND_IP_LIMIT,
        email_limit=EMAIL_SEND_LIMIT,
        window_seconds=EMAIL_SEND_WINDOW_SECONDS,
    )

    db.query(EmailLoginCode).filter(
        EmailLoginCode.email == email,
        EmailLoginCode.used_at.is_(None),
    ).update({EmailLoginCode.used_at: now}, synchronize_session=False)

    code = generate_password_reset_code()
    login_code = EmailLoginCode(
        email=email,
        code_hash=_email_login_code_hash(email, code),
        expires_at=now + EMAIL_CODE_LIFETIME,
        created_at=now,
    )
    db.add(login_code)
    db.commit()

    if DEV_LOG_VERIFICATION_CODE:
        logger.warning("Development passwordless sign-in code: %s", code)
    elif not send_email_login_code(email, code):
        login_code.used_at = now
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить код. Проверьте настройки почты и повторите попытку позже.",
        )

    return {"success": True, "message": "Код отправлен на email.", "email": email}


@router.post("/auth/email-code/confirm", response_model=Token)
async def confirm_email_code(
        data: EmailCodeConfirm,
        response: Response,
        request: Request,
        db: Session = Depends(get_db),
):
    """Validate the code, then sign in or create the verified account."""
    require_pending_legal_consent(request)
    email = str(data.email).strip().casefold()
    enforce_auth_rate_limit(db, request, scope="email-code-confirm", email=email)
    if not data.code.isdigit() or len(data.code) != 6:
        raise HTTPException(status_code=400, detail="Введите 6-значный код из письма")

    now = _utc_now()
    login_code = db.query(EmailLoginCode).filter(
        EmailLoginCode.email == email,
        EmailLoginCode.used_at.is_(None),
    ).order_by(EmailLoginCode.created_at.desc()).with_for_update().first()
    if not login_code:
        raise HTTPException(status_code=400, detail="Код не найден. Запросите новый код.")
    if _as_utc(login_code.expires_at) <= now:
        login_code.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Срок действия кода истёк. Запросите новый код.")
    if login_code.attempts >= EMAIL_CODE_MAX_ATTEMPTS:
        login_code.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Превышено число попыток. Запросите новый код.")

    if not hmac.compare_digest(login_code.code_hash, _email_login_code_hash(email, data.code)):
        login_code.attempts += 1
        remaining_attempts = EMAIL_CODE_MAX_ATTEMPTS - login_code.attempts
        if remaining_attempts <= 0:
            login_code.used_at = now
        db.commit()
        if remaining_attempts <= 0:
            raise HTTPException(status_code=400, detail="Превышено число попыток. Запросите новый код.")
        raise HTTPException(status_code=400, detail=f"Неверный код. Осталось попыток: {remaining_attempts}.")

    user = get_user_by_email(db, email)
    created = False
    if user and not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт отключён")
    if not user:
        # Keep the existing non-null column for legacy accounts. The random value
        # is never shown or accepted by the passwordless UI.
        user = User(email=email, password_hash=get_hash_password(secrets.token_urlsafe(48)), is_active=True)
        db.add(user)
        db.flush()
        created = True

    persist_legal_consent(db, user)
    login_code.used_at = now
    db.commit()
    db.refresh(user)
    if created:
        initialise_new_user_entitlements(db, user.id, user.email)

    token = _token_response(user)
    set_refresh_token_cookie(response, create_refresh_session(db, user))
    return token


def _password_reset_request_response() -> dict:
    """Build the success response after issuing a password-reset code."""
    return {
        "success": True,
        "message": "Если аккаунт с таким email существует, код отправлен на почту.",
    }


async def register(
        user_data: UserRegister,
        request: Request,
        db: Session = Depends(get_db),
):
    try:
        enforce_auth_rate_limit(
            db,
            request,
            scope="registration",
            email=user_data.email,
            ip_limit=EMAIL_SEND_IP_LIMIT,
            email_limit=EMAIL_SEND_LIMIT,
            window_seconds=EMAIL_SEND_WINDOW_SECONDS,
        )
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        password_hash = get_hash_password(user_data.password)
        create_pending_user(user_data.email, password_hash)
        return {
            "success": True,
            "message": "Код подтверждения отправлен на email",
            "email": user_data.email,
            "requires_verification": True,
        }
    except VerificationEmailDeliveryError:
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить код подтверждения. Попробуйте позже.",
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при регистрации: {str(e)}")


async def login(
        user_data: UserLogin,
        response: Response,
        request: Request,
        db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(
        db,
        request,
        scope="login",
        email=user_data.email,
        ip_limit=LOGIN_IP_LIMIT,
        email_limit=LOGIN_EMAIL_LIMIT,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    enforce_login_failure_lock(db, user_data.email)
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        record_failed_login(db, user_data.email)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    clear_failed_login_attempts(db, user_data.email)
    access_token = create_user_access_token(user)
    set_refresh_token_cookie(response, create_refresh_session(db, user))
    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"email": user.email, "id": user.id, "display_name": user.display_name, "avatar_url": user.avatar_url}
    )


@router.post("/auth/refresh")
async def refresh_login(
        response: Response,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    """Issue a fresh short-lived access token for an active persistent session."""
    user = refresh_active_session(db, refresh_token)
    if not user:
        clear_refresh_token_cookie(response)
        response.status_code = 401
        return {"detail": "Сессия истекла. Войдите снова."}

    return Token(
        access_token=create_user_access_token(user),
        token_type="bearer",
        user={"email": user.email, "id": user.id, "display_name": user.display_name, "avatar_url": user.avatar_url},
    )


@router.post("/auth/logout")
async def logout(
        response: Response,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    revoke_refresh_session(db, refresh_token)
    clear_refresh_token_cookie(response)
    return {"success": True}


async def send_verification(
        user_data: UserRegister,
        request: Request,
        db: Session = Depends(get_db),
):
    """Отправляет код подтверждения на email"""
    try:
        enforce_auth_rate_limit(
            db,
            request,
            scope="registration",
            email=user_data.email,
            ip_limit=EMAIL_SEND_IP_LIMIT,
            email_limit=EMAIL_SEND_LIMIT,
            window_seconds=EMAIL_SEND_WINDOW_SECONDS,
        )
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        hashed_password = get_hash_password(user_data.password)
        code = create_pending_user(user_data.email, hashed_password)

        return {
            "success": True,
            "message": f"Код подтверждения отправлен на {user_data.email}",
            "email": user_data.email
        }
    except VerificationEmailDeliveryError:
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить код подтверждения. Попробуйте позже.",
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


async def request_password_reset(
        data: PasswordResetRequest,
        request: Request,
        db: Session = Depends(get_db),
):
    """Issue a short-lived reset code without revealing account existence."""
    enforce_auth_rate_limit(
        db,
        request,
        scope="password-reset-request",
        email=data.email,
        ip_limit=PASSWORD_RESET_IP_LIMIT,
        email_limit=PASSWORD_RESET_LIMIT,
        window_seconds=PASSWORD_RESET_WINDOW_SECONDS,
    )
    user = get_user_by_email(db, data.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Аккаунт с таким email не найден")

    now = _utc_now()
    recent_code = db.query(PasswordResetCode).filter(
        PasswordResetCode.user_id == user.id,
        PasswordResetCode.used_at.is_(None),
        PasswordResetCode.expires_at > now,
        PasswordResetCode.created_at >= now - PASSWORD_RESET_RESEND_DELAY,
    ).order_by(PasswordResetCode.created_at.desc()).first()
    if recent_code:
        retry_after_seconds = max(
            1,
            math.ceil((_as_utc(recent_code.created_at) + PASSWORD_RESET_RESEND_DELAY - now).total_seconds()),
        )
        if retry_after_seconds <= int(PASSWORD_RESET_RESEND_DELAY.total_seconds()):
            raise HTTPException(
                status_code=429,
                detail="Код уже отправлен. Повторите попытку через минуту.",
                headers={"Retry-After": str(retry_after_seconds)},
            )

        recent_code.used_at = now
        db.commit()

    db.query(PasswordResetCode).filter(
        PasswordResetCode.user_id == user.id,
        PasswordResetCode.used_at.is_(None),
    ).update({PasswordResetCode.used_at: now}, synchronize_session=False)

    code = generate_password_reset_code()
    reset_code = PasswordResetCode(
        user_id=user.id,
        code_hash=_password_reset_code_hash(user.id, code),
        expires_at=now + PASSWORD_RESET_CODE_LIFETIME,
        created_at=now,
    )
    db.add(reset_code)
    db.commit()

    if DEV_LOG_VERIFICATION_CODE:
        logger.warning("Development password-reset code for %s: %s", data.email, code)
    elif not send_password_reset_email(data.email, code):
        reset_code.used_at = now
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить код. Проверьте настройки почты и повторите попытку позже.",
        )

    return _password_reset_request_response()


async def confirm_password_reset(
        data: PasswordResetConfirm,
        request: Request,
        db: Session = Depends(get_db),
):
    """Validate a one-time code, set a new password, and revoke persistent sessions."""
    enforce_auth_rate_limit(db, request, scope="password-reset-confirm", email=data.email)
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Новый пароль должен содержать минимум 8 символов")
    if not data.code.isdigit() or len(data.code) != 6:
        raise HTTPException(status_code=400, detail="Введите 6-значный код из письма")

    user = get_user_by_email(db, data.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Код недействителен или истёк")

    now = _utc_now()
    reset_code = db.query(PasswordResetCode).filter(
        PasswordResetCode.user_id == user.id,
        PasswordResetCode.used_at.is_(None),
    ).order_by(PasswordResetCode.created_at.desc()).first()
    if not reset_code:
        raise HTTPException(status_code=400, detail="Код не найден. Запросите новый код.")
    if _as_utc(reset_code.expires_at) <= now:
        reset_code.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Срок действия кода истёк. Запросите новый код.")
    if reset_code.attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
        reset_code.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Превышено число попыток. Запросите новый код.")

    expected_hash = _password_reset_code_hash(user.id, data.code)
    if not hmac.compare_digest(reset_code.code_hash, expected_hash):
        reset_code.attempts += 1
        remaining_attempts = PASSWORD_RESET_MAX_ATTEMPTS - reset_code.attempts
        if remaining_attempts <= 0:
            reset_code.used_at = now
            db.commit()
            raise HTTPException(status_code=400, detail="Превышено число попыток. Запросите новый код.")
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Неверный код. Осталось попыток: {remaining_attempts}.",
        )

    user.password_hash = get_hash_password(data.new_password)
    reset_code.used_at = now
    revoke_all_refresh_sessions(db, user.id)
    return {"success": True, "message": "Пароль изменён. Войдите с новым паролем."}


async def verify_registration_code(
        data: dict,
        response: Response,
        request: Request,
        db: Session = Depends(get_db),
):
    """Подтверждает код и завершает регистрацию"""
    email = data.get("email")
    code = data.get("code")

    enforce_auth_rate_limit(db, request, scope="registration-verify", email=email)

    if not email or not code:
        raise HTTPException(status_code=400, detail="Email и код обязательны")

    if email not in pending_users:
        raise HTTPException(status_code=400, detail="Код не найден. Запросите новый код")

    pending = pending_users[email]

    if datetime.now() > pending["expires_at"]:
        del pending_users[email]
        raise HTTPException(status_code=400, detail="Код подтверждения истек. Запросите новый")

    if pending["verification_code"] != code:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже зарегистрирован")

    db_user = User(
        email=email,
        password_hash=pending["password_hash"],
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    del pending_users[email]

    initialise_new_user_entitlements(db, db_user.id, db_user.email)

    access_token = create_user_access_token(db_user)
    set_refresh_token_cookie(response, create_refresh_session(db, db_user))

    return {
        "success": True,
        "message": "Регистрация успешно завершена",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": db_user.email, "id": db_user.id, "display_name": db_user.display_name, "avatar_url": db_user.avatar_url}
    }
