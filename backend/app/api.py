# app/api.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from datetime import timedelta
from typing import Optional

from app.models import UserLogin, UserRegister, Token, HumanizeRequest
from app.config import FRONTEND_PATH
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from llm import humanize_pipeline

# Создаем роутер (без mount!)
router = APIRouter()

@router.get("/")
async def serve_frontend():
    """Отдача фронтенда"""
    return FileResponse(FRONTEND_PATH)

@router.post("/register", response_model=dict)
async def register(user_data: UserRegister):
    """Регистрация нового пользователя"""
    try:
        user = create_user(user_data.email, user_data.username, user_data.password)
        return {
            "success": True,
            "message": "Пользователь успешно зарегистрирован",
            "user": user
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при регистрации: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    """Вход пользователя, возвращает JWT токен"""
    user = authenticate_user(user_data.email, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"email": user["email"], "username": user["username"]}
    )

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "success": True,
        "user": current_user
    }

@router.post("/humanize")
async def humanize(
    req: HumanizeRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Очеловечивание текста с параметрами"""
    result = await humanize_pipeline(
        req.text,
        req.intensity,
        req.tone,
        req.style,
        req.length,
        req.target_language
    )
    return {
        "success": True,
        "result": result
    }

@router.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {
        "success": True,
        "status": "ok",
        "message": "API is running"
    }