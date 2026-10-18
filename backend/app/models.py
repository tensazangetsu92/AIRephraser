# app/models.py
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional


class UserLogin(BaseModel):
    """Модель для входа пользователя"""
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserRegister(BaseModel):
    """Модель для регистрации пользователя"""
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(min_length=8, max_length=256)


class EmailCodeRequest(BaseModel):
    """Request a one-time code for passwordless sign-in or registration."""
    email: EmailStr


class EmailCodeConfirm(BaseModel):
    """Complete passwordless sign-in with a short-lived code."""
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class Token(BaseModel):
    """Модель для JWT токена"""
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    id: int
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
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
    package_id: Literal["words_2000", "words_5000", "words_10000", "words_30000"]
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
    style: Literal["human", "literary", "academic"] = "human"
    target_language: Literal["ru", "en"] = "ru"
    academic_work_type: Optional[Literal["report", "essay", "presentation", "coursework", "other"]] = None


class StudyWorkDownloadRequest(BaseModel):
    text: str


class DetectRequest(BaseModel):
    text: str


class ApiResponse(BaseModel):
    """Стандартный ответ API"""
    success: bool
    message: str
    data: Optional[dict] = None

class ParaphraseRequest(BaseModel):
    text: str
    style: str = "synonyms"
