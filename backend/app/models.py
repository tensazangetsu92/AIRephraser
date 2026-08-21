# app/models.py
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
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


class SubscriptionResponse(BaseModel):
    """Модель для информации о подписке"""
    id: int
    user_id: int
    plan_type: str
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    requests_per_day: int
    requests_per_month: int
    max_text_length: int

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    """Модель для создания подписки"""
    plan_type: Literal["premium", "pro", "unlimited"]
    payment_id: Optional[str] = None


class WordPackagePurchase(BaseModel):
    package_id: Literal["words_2000", "words_5000", "words_10000"]
    payment_id: Optional[str] = None


class UsageStatsResponse(BaseModel):
    """Модель для статистики использования"""
    user_id: int
    request_date: date
    requests_count: int
    total_chars_processed: int
    remaining_today: int
    remaining_this_month: int


class HumanizeRequest(BaseModel):
    """Модель запроса на обработку текста"""
    text: str
    tone: Literal["neutral", "formal", "casual", "friendly", "academic"] = "neutral"
    style: Literal["simple", "creative", "professional"] = "simple"
    target_language: Literal["ru", "en"] = "ru"
    academic_work_type: Optional[Literal["report", "essay", "presentation", "coursework", "other"]] = None
    preserve_options: list[Literal["numbers", "terms", "sources", "formulas"]] = Field(default_factory=list)

class DetectRequest(BaseModel):
    text: str


class GrammarRequest(BaseModel):
    text: str


class ApiResponse(BaseModel):
    """Стандартный ответ API"""
    success: bool
    message: str
    data: Optional[dict] = None

class ParaphraseRequest(BaseModel):
    text: str
    style: str = "similar"
    tone: str = "neutral"
