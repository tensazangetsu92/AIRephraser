# app/api.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from datetime import timedelta, datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models import UserLogin, UserRegister, Token, HumanizeRequest, SubscriptionCreate
from app.config import FRONTEND_PATH
from app.database import get_db, create_tables, User
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_user_by_email
)
from llm import humanize_pipeline
from app.subscription import (
    get_user_subscription,
    upgrade_subscription,
    get_usage_stats,
    check_usage_limit,
    increment_usage,
    SUBSCRIPTION_PLANS
)

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


@router.post("/humanize")
async def humanize(
        req: HumanizeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем лимиты (передаём текст целиком)
    check_usage_limit(db, current_user.id, req.text)

    # Обработка текста
    result = await humanize_pipeline(
        req.text,
        req.intensity,
        req.tone,
        req.style,
        req.length,
        req.target_language
    )

    # Увеличиваем счётчик (передаём количество слов)
    word_count = len(req.text.strip().split())
    increment_usage(db, current_user.id, word_count)

    return {"success": True, "result": result}

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "success": True,
        "user": {
            "email": current_user.email,
            "id": current_user.id
        }
    }


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получить информацию о подписке пользователя"""
    subscription = get_user_subscription(db, current_user.id)
    usage_stats = get_usage_stats(db, current_user.id)

    return {
        "success": True,
        "subscription": {
            "id": subscription.id,
            "plan_type": subscription.plan_type,
            "is_active": subscription.is_active,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "total_requests": subscription.total_requests,
            "daily_limit": subscription.daily_limit,
            "max_words": subscription.max_words  # 👈 ИЗМЕНИТЬ: было max_text_length
        },
        "usage": usage_stats,
        "available_plans": SUBSCRIPTION_PLANS
    }


@router.post("/subscription/upgrade")
async def upgrade_subscription_endpoint(
        plan_data: SubscriptionCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    subscription = upgrade_subscription(
        db,
        current_user.id,
        plan_data.plan_type,
        payment_id=f"test_payment_{datetime.now().timestamp()}"
    )

    return {
        "success": True,
        "message": f"Subscription upgraded to {plan_data.plan_type}",
        "subscription": {
            "plan_type": subscription.plan_type,
            "end_date": subscription.end_date,
            "total_requests": subscription.total_requests,
            "daily_limit": subscription.daily_limit,
            "max_words": subscription.max_words  # 👈 ИЗМЕНИТЬ: было max_text_length
        }
    }


@router.get("/subscription/plans")
async def get_subscription_plans():
    """Получить список доступных планов подписки"""
    return {
        "success": True,
        "plans": SUBSCRIPTION_PLANS
    }