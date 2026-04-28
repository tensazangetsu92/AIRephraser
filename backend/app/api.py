# app/api.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models import UserLogin, UserRegister, Token, HumanizeRequest
from app.config import FRONTEND_PATH
from app.database import get_db, create_tables, User
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_user_by_email
)
from llm import humanize_pipeline

router = APIRouter()

# Создаем таблицы при старте
create_tables()

@router.get("/")
async def serve_frontend():
    """Отдача фронтенда"""
    return FileResponse(FRONTEND_PATH)

@router.post("/register", response_model=dict)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        user = create_user(db, user_data.email, user_data.username, user_data.password)
        return {
            "success": True,
            "message": "Пользователь успешно зарегистрирован",
            "user": {"email": user.email, "username": user.username}
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
        user={"email": user.email, "username": user.username}
    )


@router.post("/humanize")
async def humanize(
        req: HumanizeRequest,
        current_user: Optional[User] = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    result = await humanize_pipeline(
        req.text,
        req.intensity,
        req.tone,
        req.style,
        req.length,
        req.target_language
    )

    return {"success": True, "result": result}