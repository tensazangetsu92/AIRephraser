# app/routers/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import UserLogin, UserRegister, Token
from app.database import get_db, User
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_email,
    get_hash_password,
    pending_users,
    create_pending_user,
)
from app.subscription import get_user_subscription

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=dict)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        user = create_user(db, user_data.email, user_data.password)
        return {
            "success": True,
            "message": "Пользователь успешно зарегистрирован",
            "user": {"email": user.email}
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при регистрации: {str(e)}")


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    access_token = create_access_token(data={"sub": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"email": user.email, "id": user.id}
    )


@router.post("/auth/send-verification")
async def send_verification(user_data: UserRegister, db: Session = Depends(get_db)):
    """Отправляет код подтверждения на email"""
    try:
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
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/auth/verify-code")
async def verify_registration_code(data: dict, db: Session = Depends(get_db)):
    """Подтверждает код и завершает регистрацию"""
    email = data.get("email")
    code = data.get("code")

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

    get_user_subscription(db, db_user.id)

    access_token = create_access_token(data={"sub": db_user.email})

    return {
        "success": True,
        "message": "Регистрация успешно завершена",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": db_user.email, "id": db_user.id}
    }