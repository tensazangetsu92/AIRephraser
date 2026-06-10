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
        "max_words": 1000,
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
        subscription = Subscription(
            user_id=user_id,
            plan_type="free",
            is_active=True
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    return subscription

def get_plan_limits(plan_type: str) -> dict:
    """Получить лимиты для типа подписки"""
    return SUBSCRIPTION_PLANS.get(plan_type, SUBSCRIPTION_PLANS["free"])

def upgrade_subscription(db: Session, user_id: int, plan_type: str, payment_id: str = None, duration_days: int = 30):
    """Обновить подписку пользователя и сбросить статистику"""
    if plan_type not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    subscription = get_user_subscription(db, user_id)

    now = get_current_datetime()
    end_date = now + timedelta(days=duration_days)

    subscription.plan_type = plan_type
    subscription.is_active = True
    subscription.end_date = end_date
    subscription.payment_id = payment_id
    subscription.last_reset_date = now

    reset_usage_stats(db, user_id)

    db.commit()
    db.refresh(subscription)

    return subscription



def downgrade_to_free(db: Session, user_id: int):
    """Понизить подписку до бесплатной после истечения"""
    subscription = get_user_subscription(db, user_id)

    subscription.plan_type = "free"
    subscription.end_date = None
    subscription.last_reset_date = None

    db.commit()

    reset_usage_stats(db, user_id)

    return subscription


def check_subscription_expired(db: Session, user_id: int):
    """Проверить срок подписки и ежемесячный сброс статистики"""
    subscription = get_user_subscription(db, user_id)
    now = get_current_datetime()

    if subscription.plan_type != "free" and subscription.end_date:
        if now > subscription.end_date:
            downgrade_to_free(db, user_id)
            return True

        if subscription.last_reset_date:
            next_reset = subscription.last_reset_date + timedelta(days=30)
            if now >= next_reset:
                reset_usage_stats(db, user_id)
                subscription.last_reset_date = next_reset
                db.commit()

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
    limits = get_plan_limits(plan_type)

    word_count = count_words(text)

    if word_count > limits["max_words"]:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен лимит слов. Максимум {limits['max_words']} слов для вашего тарифа. Сейчас {word_count} слов."
        )

    total_requests = get_total_requests_count(db, user_id)

    if total_requests >= limits["total_requests"]:
        if plan_type == "free":
            raise HTTPException(
                status_code=429,
                detail=f"Достигнут лимит бесплатного тарифа. Вы использовали все {limits['total_requests']} бесплатных запросов. Пожалуйста, приобретите подписку, чтобы продолжить."
            )
        else:
            raise HTTPException(
                status_code=429,
                detail=f"Достигнут лимит вашего тарифа — {limits['total_requests']} запросов. Пожалуйста, перейдите на следующий тариф, чтобы продолжить."
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
            requests_count=0
        )
        db.add(stats)

    stats.requests_count += 1
    db.commit()


def get_usage_stats(db: Session, user_id: int) -> dict:
    """Получить статистику использования"""
    subscription = get_user_subscription(db, user_id)
    limits = get_plan_limits(subscription.plan_type)

    today = date.today()

    stats_today = db.query(UsageStats).filter(
        UsageStats.user_id == user_id,
        UsageStats.request_date == today
    ).first()

    requests_today = stats_today.requests_count if stats_today else 0
    total_requests = get_total_requests_count(db, user_id)
    remaining_requests = max(0, limits["total_requests"] - total_requests)

    return {
        "plan_type": subscription.plan_type,
        "total_requests_used": total_requests,
        "total_requests_limit": limits["total_requests"],
        "remaining_requests": remaining_requests,
        "requests_today": requests_today,
        "max_words": limits["max_words"],
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None
    }


# app/subscription.py

def reset_usage_stats(db: Session, user_id: int):
    """Сбрасывает статистику использования при смене подписки"""
    today = date.today()

    db.query(UsageStats).filter(UsageStats.user_id == user_id).delete()

    new_stats = UsageStats(
        user_id=user_id,
        request_date=today,
        requests_count=0
    )
    db.add(new_stats)
    db.commit()

    print(f"🔄 Reset usage stats for user {user_id}")