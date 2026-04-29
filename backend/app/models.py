# app/models.py
from datetime import datetime

from pydantic import BaseModel, EmailStr
from typing import Literal, Optional

class UserLogin(BaseModel):
    """Модель для входа пользователя"""
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    """Модель для регистрации пользователя"""
    email: EmailStr
    password: str

class Token(BaseModel):
    """Модель для JWT токена"""
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: Optional[datetime] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class HumanizeRequest(BaseModel):
    """Модель запроса на обработку текста"""
    text: str
    intensity: Literal["low", "medium", "high"] = "medium"
    tone: Literal["neutral", "formal", "casual", "friendly", "academic"] = "neutral"
    style: Literal["simple", "creative", "professional"] = "simple"
    length: Literal["same", "shorter", "longer"] = "same"
    target_language: Literal["ru", "en"] = "ru"

class ApiResponse(BaseModel):
    """Стандартный ответ API"""
    success: bool
    message: str
    data: Optional[dict] = None