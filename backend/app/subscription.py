# app/subscription.py
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.database import User, Subscription, UsageStats
import pytz

# Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_current_datetime():
    """Получить текущую дату/время с часовым поясом"""
    return datetime.now(MOSCOW_TZ)


# Планы подписки и их лимиты
SUBSCRIPTION_PLANS = {
    "free": {
        "total_requests": 5,
        "max_words": 300,
        "price_monthly": 0
    },
    "premium": {
        "total_requests": 300,
        "max_words": 20000,
        "price_monthly": 169
    },
    "pro": {
        "total_requests": 1000,
        "max_words": 50000,
        "price_monthly": 319
    }
}


def get_user_subscription(db: Session, user_id: int) -> Subscription:
    """Получить подписку пользователя"""
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()

    if not subscription:
        plan = SUBSCRIPTION_PLANS["free"]
        subscription = Subscription(
            user_id=user_id,
            plan_type="free",
            is_active=True,
            total_requests=plan["total_requests"],
            max_words=plan["max_words"]
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

    end_date = get_current_datetime() + timedelta(days=30)

    subscription.plan_type = plan_type
    subscription.is_active = True
    subscription.end_date = end_date
    subscription.payment_id = payment_id
    subscription.total_requests = plan["total_requests"]
    subscription.max_words = plan["max_words"]

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
    subscription.max_words = free_plan["max_words"]

    db.commit()
    return subscription


def check_subscription_expired(db: Session, user_id: int):
    """Проверить, не истекла ли подписка"""
    subscription = get_user_subscription(db, user_id)

    if subscription.plan_type != "free" and subscription.end_date:
        if get_current_datetime() > subscription.end_date:
            downgrade_to_free(db, user_id)
            return True
    return False


def get_total_requests_count(db: Session, user_id: int) -> int:
    """Получить общее количество запросов пользователя за всё время"""
    total = db.query(func.sum(UsageStats.requests_count)).filter(
        UsageStats.user_id == user_id
    ).scalar()
    return total or 0


def count_words(text: str) -> int:
    """Подсчёт количества слов в тексте"""
    if not text:
        return 0
    return len(text.strip().split())


def check_usage_limit(db: Session, user_id: int, text: str = "") -> bool:
    """Проверить лимиты использования (по словам)"""
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id)

    plan_type = subscription.plan_type

    # Подсчитываем количество слов
    word_count = count_words(text)

    # Проверяем лимит слов за раз
    if word_count > subscription.max_words:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен лимит слов. Максимум {subscription.max_words} слов для вашего тарифа. Сейчас {word_count} слов."
        )

    # Получаем общее количество запросов за всё время
    total_requests = get_total_requests_count(db, user_id)

    # Проверяем общий лимит запросов
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

    return True


def increment_usage(db: Session, user_id: int, word_count: int):
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
    stats.total_chars_processed += word_count
    db.commit()


def get_usage_stats(db: Session, user_id: int) -> dict:
    """Получить статистику использования"""
    subscription = get_user_subscription(db, user_id)

    today = date.today()

    stats_today = db.query(UsageStats).filter(
        UsageStats.user_id == user_id,
        UsageStats.request_date == today
    ).first()

    requests_today = stats_today.requests_count if stats_today else 0
    total_requests = get_total_requests_count(db, user_id)
    remaining_requests = max(0, subscription.total_requests - total_requests)

    return {
        "plan_type": subscription.plan_type,
        "total_requests_used": total_requests,
        "total_requests_limit": subscription.total_requests,
        "remaining_requests": remaining_requests,
        "requests_today": requests_today,
        "max_words": subscription.max_words,
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None
    }