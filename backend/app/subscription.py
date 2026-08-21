# app/subscription.py
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import User, Subscription, UsageStats, WordTransaction, StudyWorkTrial
from uuid import uuid4
import pytz

# Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_current_datetime():
    """Получить текущую дату/время с часовым поясом"""
    return datetime.now(MOSCOW_TZ)


STUDY_WORK_TRIAL_RESERVATION_MINUTES = 15


def grant_study_work_trial(db: Session, user_id: int) -> None:
    """Give a new user one separate, no-word-cost Study Work processing."""
    if db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user_id).first():
        return
    db.add(StudyWorkTrial(user_id=user_id, status="available"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def reserve_study_work_trial(db: Session, user_id: int) -> bool:
    """Reserve the registration trial so concurrent requests cannot spend it twice."""
    trial = db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user_id).first()
    if not trial:
        return False

    now = get_current_datetime()
    if trial.status == "processing":
        reservation_expires_at = trial.reserved_at + timedelta(minutes=STUDY_WORK_TRIAL_RESERVATION_MINUTES)
        if reservation_expires_at > now:
            return False
        trial.status = "available"
        trial.reserved_at = None

    if trial.status != "available":
        return False

    trial.status = "processing"
    trial.reserved_at = now
    db.commit()
    return True


def complete_study_work_trial(db: Session, user_id: int) -> None:
    trial = db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user_id).first()
    if not trial or trial.status != "processing":
        return
    trial.status = "used"
    trial.used_at = get_current_datetime()
    db.commit()


def release_study_work_trial(db: Session, user_id: int) -> None:
    """Return the trial if the provider failed before a result was delivered."""
    trial = db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user_id).first()
    if not trial or trial.status != "processing":
        return
    trial.status = "available"
    trial.reserved_at = None
    db.commit()


# Планы подписки: лимит слов за один запрос + общая месячная квота слов
SUBSCRIPTION_PLANS = {
    "free": {
        "max_words_per_request": 500,
        "word_limit": 500,
        "price_monthly": 0
    },
    "premium": {
        "max_words_per_request": 10000,
        "word_limit": 20000,
        "price_monthly": 169
    },
    "pro": {
        "max_words_per_request": 25000,
        "word_limit": 50000,
        "price_monthly": 319
    },
    "unlimited": {
        "max_words_per_request": 30000,
        "word_limit": None,  # None = безлимит по месячной квоте
        "price_monthly": 599
    }
}

# "Study Work" can process larger documents than the standalone tools.
STUDY_WORK_MAX_WORDS_PER_REQUEST = {
    "free": 5_000,
    "premium": 10_000,
    "pro": 15_000,
    "unlimited": 15_000,
}

PURCHASE_PACKAGES = {
    "words_2000": {"words": 2000, "price_rub": 100},
    "words_5000": {"words": 5000, "price_rub": 200},
    "words_10000": {"words": 10000, "price_rub": 300},
}

# Защита безлимитного тарифа от частых тяжёлых запросов. Небольшие запросы
# не ограничиваются этим правилом; остаётся и отдельный потолок 30 000 слов.
UNLIMITED_LARGE_REQUEST_WORDS = 10_000
UNLIMITED_LARGE_REQUEST_MAX = 2
UNLIMITED_LARGE_REQUEST_WINDOW_SECONDS = 5 * 60
_unlimited_large_request_times = defaultdict(deque)
_unlimited_large_request_lock = Lock()


def check_unlimited_large_request_rate(user_id: int, word_count: int) -> None:
    """Allow no more than two requests of 10k+ words per five minutes per user."""
    if word_count < UNLIMITED_LARGE_REQUEST_WORDS:
        return

    now = monotonic()
    with _unlimited_large_request_lock:
        request_times = _unlimited_large_request_times[user_id]
        while request_times and now - request_times[0] >= UNLIMITED_LARGE_REQUEST_WINDOW_SECONDS:
            request_times.popleft()

        if len(request_times) >= UNLIMITED_LARGE_REQUEST_MAX:
            retry_after = max(1, int(UNLIMITED_LARGE_REQUEST_WINDOW_SECONDS - (now - request_times[0])))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Для безлимитного тарифа доступно не более "
                    f"{UNLIMITED_LARGE_REQUEST_MAX} запросов от "
                    f"10 000 слов за 5 минут. "
                    f"Повторите через {retry_after} сек."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        request_times.append(now)


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


def get_study_work_max_words(plan_type: str) -> int:
    return STUDY_WORK_MAX_WORDS_PER_REQUEST.get(plan_type, STUDY_WORK_MAX_WORDS_PER_REQUEST["free"])


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


def check_request_word_limit(db: Session, user_id: int, text: str = "", max_words_override: int | None = None) -> None:
    """Enforce only the plan's per-request size limit, without charging words."""
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id)
    limits = get_plan_limits(subscription.plan_type)
    word_count = count_words(text)
    max_words_per_request = max_words_override or limits["max_words_per_request"]

    if word_count <= max_words_per_request:
        return

    excess_words = word_count - max_words_per_request
    recommendation = (
        "Разделите текст на несколько запросов."
        if subscription.plan_type == "unlimited"
        else "Сократите текст или выберите тариф с большим лимитом за запрос."
    )
    raise HTTPException(
        status_code=400,
        detail=(
            f"Превышен лимит слов за один запрос. Максимум: {max_words_per_request}. "
            f"Сейчас: {word_count}. Превышение: {excess_words} слов. {recommendation}"
        ),
    )


def check_study_work_request_limit(db: Session, user_id: int, text: str = "") -> int:
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id)
    max_words = get_study_work_max_words(subscription.plan_type)
    check_request_word_limit(db, user_id, text, max_words_override=max_words)
    return max_words


def check_usage_limit(db: Session, user_id: int, text: str = "", max_words_override: int | None = None) -> bool:
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
    check_request_word_limit(db, user_id, text, max_words_override=max_words_override)

    # Unlimited means no monthly quota, not unlimited server load.
    if plan_type == "unlimited":
        check_unlimited_large_request_rate(user_id, word_count)

    # 2. Проверка месячной квоты (пропускаем для безлимитного тарифа)
    if word_limit is not None:
        words_used = get_words_used(db, user_id)

        if words_used + word_count > word_limit:
            remaining = max(0, word_limit - words_used)
            word_balance = get_word_balance(db, user_id)
            extra_words = word_balance["bonus_words"] + word_balance["purchased_words"]
            if remaining + extra_words >= word_count:
                return True
            available_words = remaining + extra_words
            missing_words = word_count - available_words
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Недостаточно слов для этого запроса. "
                    f"Доступно: {available_words} слов "
                    f"(по подписке: {remaining}, доп. слова: {extra_words}). "
                    f"Не хватает: {missing_words} слов. "
                    f"Повысьте тариф или докупите пакет слов."
                )
            )

    return True


def increment_usage(db: Session, user_id: int, word_count: int):
    """Увеличить счётчик использованных слов за текущий период"""
    stats = get_or_create_usage_stats(db, user_id)
    subscription = get_user_subscription(db, user_id)
    limit = get_plan_limits(subscription.plan_type)["word_limit"]
    # Use the subscription quota first.
    subscription_remaining = None if limit is None else max(0, limit - (stats.words_used or 0))
    subscription_used = word_count if subscription_remaining is None else min(word_count, subscription_remaining)
    if limit is not None:
        stats.words_used = (stats.words_used or 0) + subscription_used

    credits_left = word_count - subscription_used
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
    print(f"Reset word usage stats for user {user_id}")
