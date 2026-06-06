# app/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import hashlib
import os

from app.database import get_db, User
from app.config import SECRET_KEY
from app.subscription import get_user_subscription
from app.email_utils import generate_verification_code, send_verification_email, store_verification_code, verify_code

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
security = HTTPBearer()


def get_hash_password(password: str) -> str:
    """Хеширование пароля"""
    salt = "humary_salt_2024"
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_hash_password(plain_password) == hashed_password


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


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

    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Неверный токен")

        user = db.query(User).filter(User.email == email).first()
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
        print(f"🧹 Cleaned up {len(expired)} expired pending users")


def create_pending_user(email: str, password_hash: str):
    """Сохраняет пользователя до подтверждения email"""
    # Очищаем истекшие коды перед созданием нового
    cleanup_expired_pending_users()

    code = generate_verification_code()
    pending_users[email] = {
        "password_hash": password_hash,
        "verification_code": code,
        "expires_at": datetime.now() + timedelta(minutes=10)
    }
    send_verification_email(email, code)
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

    # Удаляем из временного хранилища
    del pending_users[email]

    return db_user, None