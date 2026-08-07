# app/subscription.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import User, Subscription, UsageStats, WordTransaction
from uuid import uuid4
import pytz

# Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_current_datetime():
    """Получить текущую дату/время с часовым поясом"""
    return datetime.now(MOSCOW_TZ)


# Планы подписки: лимит слов за один запрос + общая месячная квота слов
SUBSCRIPTION_PLANS = {
    "free": {
        "max_words_per_request": 300,
        "word_limit": 300,
        "price_monthly": 0
    },
    "premium": {
        "max_words_per_request": 5000,
        "word_limit": 5000,
        "price_monthly": 169
    },
    "pro": {
        "max_words_per_request": 25000,
        "word_limit": 25000,
        "price_monthly": 319
    },
    "unlimited": {
        "max_words_per_request": 25000,
        "word_limit": None,  # None = безлимит по месячной квоте
        "price_monthly": 599
    }
}

PURCHASE_PACKAGES = {
    "words_2000": {"words": 2000, "price_rub": 100},
    "words_5000": {"words": 5000, "price_rub": 200},
    "words_10000": {"words": 10000, "price_rub": 300},
}


def get_word_balance(db: Session, user_id: int) -> dict:
    subscription = get_user_subscription(db, user_id)
    limits = get_plan_limits(subscription.plan_type)
    subscription_words = None if limits["word_limit"] is None else max(0, limits["word_limit"] - get_words_used(db, user_id))
    available = {}
    totals = {}
    for bucket in ("bonus", "purchased"):
        rows = db.query(WordTransaction).filter(
            WordTransaction.user_id == user_id, WordTransaction.kind == "credit",
            WordTransaction.bucket == bucket, WordTransaction.status == "confirmed",
        ).all()
        available[bucket] = sum(row.remaining_words for row in rows)
        totals[bucket] = sum(row.words for row in rows)
    return {
        "subscription_words": subscription_words,
        "bonus_words": available["bonus"],
        "purchased_words": available["purchased"],
        "bonus_total_words": totals["bonus"],
        "purchased_total_words": totals["purchased"],
        "total_words": None if subscription_words is None else subscription_words + available["bonus"] + available["purchased"],
        "is_unlimited": subscription_words is None,
    }


def grant_words(db: Session, user_id: int, bucket: str, words: int, reason: str, payment_id: str = None):
    """Credit a confirmed bonus or paid package. Call from a verified payment webhook."""
    if bucket not in {"bonus", "purchased"} or words <= 0:
        raise ValueError("Invalid word credit")
    row = WordTransaction(user_id=user_id, operation_id=str(uuid4()), kind="credit", bucket=bucket,
                          reason=reason, words=words, remaining_words=words, payment_id=payment_id)
    db.add(row); db.commit(); db.refresh(row)
    return row


def purchase_word_package(db: Session, user_id: int, package_id: str, payment_id: str = None):
    """Activate a package for MVP; production should call this from a verified payment webhook."""
    package = PURCHASE_PACKAGES.get(package_id)
    if not package:
        raise HTTPException(status_code=400, detail="Invalid word package")
    row = grant_words(db, user_id, "purchased", package["words"], f"purchase:{package_id}", payment_id or f"mvp_{uuid4()}")
    return package, row


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
    """Обновить подписку пользователя и сбросить статистику использования слов"""
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
    """Проверить срок подписки и ежемесячный сброс статистики слов"""
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


def count_words(text: str) -> int:
    """Подсчёт количества слов в тексте"""
    if not text:
        return 0
    return len(text.strip().split())


def get_or_create_usage_stats(db: Session, user_id: int) -> UsageStats:
    """Получить (или создать) запись статистики использования слов"""
    stats = db.query(UsageStats).filter(UsageStats.user_id == user_id).first()

    if not stats:
        stats = UsageStats(user_id=user_id, words_used=0)
        db.add(stats)
        db.commit()
        db.refresh(stats)

    return stats


def get_words_used(db: Session, user_id: int) -> int:
    """Получить количество слов, использованных в текущем расчётном периоде"""
    stats = get_or_create_usage_stats(db, user_id)
    return stats.words_used or 0


def check_usage_limit(db: Session, user_id: int, text: str = "") -> bool:
    """
    Проверяет два ограничения:
    1. Лимит слов на один запрос (max_words_per_request) — фиксированный потолок для тарифа
    2. Месячную квоту слов (word_limit) — суммарно за расчётный период
    """
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id)

    plan_type = subscription.plan_type
    limits = get_plan_limits(plan_type)
    max_words_per_request = limits["max_words_per_request"]
    word_limit = limits["word_limit"]

    word_count = count_words(text)

    # 1. Проверка лимита на один запрос
    if word_count > max_words_per_request:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен лимит слов на один запрос. Максимум {max_words_per_request} слов для вашего тарифа. Сейчас {word_count} слов."
        )

    # 2. Проверка месячной квоты (пропускаем для безлимитного тарифа)
    if word_limit is not None:
        words_used = get_words_used(db, user_id)

        if words_used + word_count > word_limit:
            remaining = max(0, word_limit - words_used)
            extra_words = get_word_balance(db, user_id)["bonus_words"] + get_word_balance(db, user_id)["purchased_words"]
            if remaining + extra_words >= word_count:
                return True
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Недостаточно слов в рамках месячного лимита. "
                    f"Осталось {remaining} из {word_limit} слов. "
                    f"В этом запросе {word_count} слов. "
                    f"{'Перейдите на более высокий тариф, чтобы продолжить.' if plan_type != 'free' else 'Оформите подписку, чтобы продолжить.'}"
                )
            )

    return True


def increment_usage(db: Session, user_id: int, word_count: int):
    """Увеличить счётчик использованных слов за текущий период"""
    stats = get_or_create_usage_stats(db, user_id)
    subscription = get_user_subscription(db, user_id)
    limit = get_plan_limits(subscription.plan_type)["word_limit"]
    credits_left = word_count
    if credits_left:
        credits = db.query(WordTransaction).filter(
            WordTransaction.user_id == user_id,
            WordTransaction.kind == "credit",
            WordTransaction.bucket.in_(["bonus", "purchased"]),
            WordTransaction.status == "confirmed",
            WordTransaction.remaining_words > 0,
        ).order_by(WordTransaction.id.asc()).with_for_update().all()
        for credit in credits:
            used = min(credits_left, credit.remaining_words)
            credit.remaining_words -= used
            credits_left -= used
            if credits_left == 0:
                break
        if credits_left:
            raise HTTPException(status_code=409, detail="Insufficient word balance")

    # The remaining part is charged to the subscription quota.
    if limit is not None:
        stats.words_used = (stats.words_used or 0) + credits_left
    db.commit()


def get_usage_stats(db: Session, user_id: int) -> dict:
    """Получить статистику использования слов для пользователя"""
    subscription = get_user_subscription(db, user_id)
    limits = get_plan_limits(subscription.plan_type)
    word_limit = limits["word_limit"]

    words_used = get_words_used(db, user_id)
    remaining_words = None if word_limit is None else max(0, word_limit - words_used)

    return {
        "plan_type": subscription.plan_type,
        "words_used": words_used,
        "word_limit": word_limit,
        "remaining_words": remaining_words,
        "is_unlimited": word_limit is None,
        "max_words_per_request": limits["max_words_per_request"],
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None
    }


def reset_usage_stats(db: Session, user_id: int):
    """Сбрасывает статистику использования слов (при оплате или ежемесячном цикле)"""
    stats = db.query(UsageStats).filter(UsageStats.user_id == user_id).first()

    if stats:
        stats.words_used = 0
    else:
        stats = UsageStats(user_id=user_id, words_used=0)
        db.add(stats)

    db.commit()
    print(f"🔄 Reset word usage stats for user {user_id}")
