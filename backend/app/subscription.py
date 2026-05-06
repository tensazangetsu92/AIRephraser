# app/subscription.py
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.database import User, Subscription, UsageStats

# Планы подписки и их лимиты
# Для free - total_requests (всего запросов за всё время)
# Для premium и pro - daily_limit + total_requests (общий лимит)
SUBSCRIPTION_PLANS = {
    "free": {
        "total_requests": 5,  # Всего 5 запросов за всё время
        "daily_limit": None,  # Нет дневного лимита
        "max_text_length": 1000,
        "price_monthly": 0,
        "price_yearly": 0
    },
    "premium": {
        "total_requests": 300,  # Всего 300 запросов
        "daily_limit": 50,  # Максимум 50 в день
        "max_text_length": 5000,
        "price_monthly": 9.99,
        "price_yearly": 99.99
    },
    "pro": {
        "total_requests": 1000,  # Всего 1000 запросов
        "daily_limit": 100,  # Максимум 100 в день
        "max_text_length": 20000,
        "price_monthly": 29.99,
        "price_yearly": 299.99
    }
}


def get_user_subscription(db: Session, user_id: int) -> Subscription:
    """Получить подписку пользователя"""
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()

    # Если подписки нет - создаём бесплатную
    if not subscription:
        subscription = Subscription(
            user_id=user_id,
            plan_type="free",
            is_active=True,
            total_requests=SUBSCRIPTION_PLANS["free"]["total_requests"],
            daily_limit=SUBSCRIPTION_PLANS["free"]["daily_limit"],
            max_text_length=SUBSCRIPTION_PLANS["free"]["max_text_length"]
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    return subscription


def upgrade_subscription(db: Session, user_id: int, plan_type: str, payment_id: str = None):
    """Обновить подписку пользователя"""
    if plan_type not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    subscription = get_user_subscription(db, user_id)

    plan = SUBSCRIPTION_PLANS[plan_type]

    # Рассчитываем дату окончания (через месяц)
    end_date = datetime.now() + timedelta(days=30)

    subscription.plan_type = plan_type
    subscription.is_active = True
    subscription.end_date = end_date
    subscription.payment_id = payment_id
    subscription.total_requests = plan["total_requests"]
    subscription.daily_limit = plan["daily_limit"]
    subscription.max_text_length = plan["max_text_length"]

    db.commit()
    db.refresh(subscription)

    return subscription


def downgrade_to_free(db: Session, user_id: int):
    """Понизить подписку до бесплатной после истечения"""
    subscription = get_user_subscription(db, user_id)
    free_plan = SUBSCRIPTION_PLANS["free"]

    subscription.plan_type = "free"
    subscription.end_date = None
    subscription.total_requests = free_plan["total_requests"]
    subscription.daily_limit = free_plan["daily_limit"]
    subscription.max_text_length = free_plan["max_text_length"]

    db.commit()

    return subscription


def check_subscription_expired(db: Session, user_id: int):
    """Проверить, не истекла ли подписка"""
    subscription = get_user_subscription(db, user_id)

    if subscription.plan_type != "free" and subscription.end_date:
        if datetime.now() > subscription.end_date:
            # Подписка истекла - понижаем до бесплатной
            downgrade_to_free(db, user_id)
            return True

    return False


def get_total_requests_count(db: Session, user_id: int) -> int:
    """Получить общее количество запросов пользователя за всё время"""
    total = db.query(func.sum(UsageStats.requests_count)).filter(
        UsageStats.user_id == user_id
    ).scalar()

    return total or 0


def check_usage_limit(db: Session, user_id: int, text_length: int = 0) -> bool:
    """Проверить лимиты использования"""
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id)

    plan_type = subscription.plan_type
    plan = SUBSCRIPTION_PLANS[plan_type]

    # Проверяем длину текста
    if text_length > subscription.max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен лимит длины текста. Максимум {subscription.max_text_length} символов для вашего тарифа"
        )

    # Получаем общее количество запросов за всё время
    total_requests = get_total_requests_count(db, user_id)

    # Проверяем общий лимит
    if total_requests >= subscription.total_requests:
        if plan_type == "free":
            raise HTTPException(
                status_code=429,
                detail=f"Достигнут лимит бесплатного тарифа. Вы использовали все {subscription.total_requests} бесплатных запросов. Пожалуйста, приобретите подписку, чтобы продолжить."
            )
        else:
            raise HTTPException(
                status_code=429,
                detail=f"Достигнут лимит вашего тарифа — {subscription.total_requests} запросов. Пожалуйста, перейдите на следующий тариф, чтобы продолжить."
            )

    # Проверяем дневной лимит (только для premium и pro)
    if subscription.daily_limit is not None:
        today = date.today()

        stats_today = db.query(UsageStats).filter(
            UsageStats.user_id == user_id,
            UsageStats.request_date == today
        ).first()

        # 👇 ВАЖНО: здесь создаётся запись, если её нет
        if not stats_today:
            stats_today = UsageStats(
                user_id=user_id,
                request_date=today,
                requests_count=0,
                total_chars_processed=0
            )
            db.add(stats_today)
            db.commit()  # 👈 НЕ ЗАБУДЬТЕ commit!

        requests_today = stats_today.requests_count if stats_today else 0

        if requests_today >= subscription.daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Превышен лимит длины текста. Максимум {subscription.max_text_length} символов для вашего тарифа"
            )

    return True


def increment_usage(db: Session, user_id: int, text_length: int):
    """Увеличить счётчики использования"""
    today = date.today()

    stats = db.query(UsageStats).filter(
        UsageStats.user_id == user_id,
        UsageStats.request_date == today
    ).first()

    if not stats:
        stats = UsageStats(
            user_id=user_id,
            request_date=today,
            requests_count=0,
            total_chars_processed=0
        )
        db.add(stats)

    stats.requests_count += 1
    stats.total_chars_processed += text_length
    db.commit()


def get_usage_stats(db: Session, user_id: int) -> dict:
    """Получить статистику использования"""
    subscription = get_user_subscription(db, user_id)
    plan = SUBSCRIPTION_PLANS[subscription.plan_type]

    today = date.today()

    # Статистика за сегодня
    stats_today = db.query(UsageStats).filter(
        UsageStats.user_id == user_id,
        UsageStats.request_date == today
    ).first()

    requests_today = stats_today.requests_count if stats_today else 0

    # Общее количество запросов за всё время
    total_requests = get_total_requests_count(db, user_id)

    # Оставшиеся запросы
    remaining_requests = max(0, subscription.total_requests - total_requests)

    # Оставшиеся запросы на сегодня (если есть дневной лимит)
    remaining_today = max(0,
                          subscription.daily_limit - requests_today) if subscription.daily_limit is not None else None

    return {
        "plan_type": subscription.plan_type,
        "total_requests_used": total_requests,
        "total_requests_limit": subscription.total_requests,
        "remaining_requests": remaining_requests,
        "requests_today": requests_today,
        "daily_limit": subscription.daily_limit,
        "remaining_today": remaining_today,
        "max_text_length": subscription.max_text_length,
        "end_date": subscription.end_date
    }