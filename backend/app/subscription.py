# app/subscription.py
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import User, Subscription, UsageStats, WordTransaction, StudyWorkTrial
from app.account_deletion import has_consumed_free_entitlement
from uuid import uuid4
import pytz

# Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
logger = logging.getLogger("uvicorn.error")


def get_current_datetime():
    """Получить текущую дату/время с часовым поясом"""
    return datetime.now(MOSCOW_TZ)


def _as_moscow_datetime(value: datetime) -> datetime:
    """Normalize database datetimes from PostgreSQL and SQLite before comparison."""
    if value.tzinfo is None:
        return MOSCOW_TZ.localize(value)
    return value.astimezone(MOSCOW_TZ)


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


def initialise_new_user_entitlements(db: Session, user_id: int, entitlement_subject: str) -> bool:
    """Create the free plan and grant its one-time onboarding benefits once.

    A user who has deleted an account for the same verified email or OAuth
    identity can still create a new account and purchase words, but does not
    receive a second free quota or a second Study Work trial.
    """
    subscription = get_user_subscription(db, user_id)
    if has_consumed_free_entitlement(db, entitlement_subject):
        subscription.free_entitlement_available = False
        db.commit()
        return False

    subscription.free_entitlement_available = True
    db.commit()
    grant_study_work_trial(db, user_id)
    return True


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
        "word_limit": 1000,
        "price_monthly": 0
    },
    "premium": {
        "max_words_per_request": 6000,
        "word_limit": 10000,
        "price_monthly": 179
    },
    "pro": {
        "max_words_per_request": 10000,
        "word_limit": 35000,
        "price_monthly": 277
    },
    "unlimited": {
        "max_words_per_request": 30000,
        "word_limit": 130000,
        "price_monthly": 699
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
    "words_2000": {"words": 2000, "price_rub": 60},
    "words_5000": {"words": 5000, "price_rub": 120},
    "words_10000": {"words": 10000, "price_rub": 200},
    "words_30000": {"words": 30000, "price_rub": 400},
}

# Защита безлимитного тарифа от частых тяжёлых запросов. Небольшие запросы
# не ограничиваются этим правилом; остаётся и отдельный потолок 30 000 слов.
def get_word_balance(
        db: Session,
        user_id: int,
        subscription: Subscription | None = None,
        words_used: int | None = None,
) -> dict:
    """Return available word balance without loading every credit row into Python."""
    subscription = subscription or get_user_subscription(db, user_id)
    limits = get_effective_plan_limits(subscription)
    if words_used is None:
        words_used = get_words_used(db, user_id)
    subscription_words = None if limits["word_limit"] is None else max(0, limits["word_limit"] - words_used)

    available = {"bonus": 0, "purchased": 0}
    totals = {"bonus": 0, "purchased": 0}
    credit_totals = db.query(
        WordTransaction.bucket,
        func.coalesce(func.sum(WordTransaction.remaining_words), 0),
        func.coalesce(func.sum(WordTransaction.words), 0),
    ).filter(
        WordTransaction.user_id == user_id,
        WordTransaction.kind == "credit",
        WordTransaction.bucket.in_(("bonus", "purchased")),
        WordTransaction.status == "confirmed",
    ).group_by(WordTransaction.bucket).all()
    for bucket, remaining_words, total_words in credit_totals:
        available[bucket] = int(remaining_words or 0)
        totals[bucket] = int(total_words or 0)
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


def get_effective_plan_limits(subscription: Subscription) -> dict:
    """Return limits after applying the one-time free-entitlement state."""
    limits = dict(get_plan_limits(subscription.plan_type))
    if subscription.plan_type == "free" and not subscription.free_entitlement_available:
        limits["word_limit"] = 0
    return limits


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


def downgrade_to_free(db: Session, user_id: int, subscription: Subscription | None = None):
    """Понизить подписку до бесплатной после истечения"""
    subscription = subscription or get_user_subscription(db, user_id)

    subscription.plan_type = "free"
    subscription.end_date = None
    subscription.last_reset_date = None

    db.commit()

    reset_usage_stats(db, user_id)

    return subscription


def check_subscription_expired(
        db: Session,
        user_id: int,
        subscription: Subscription | None = None,
):
    """Проверить срок подписки и ежемесячный сброс статистики слов"""
    subscription = subscription or get_user_subscription(db, user_id)
    now = get_current_datetime()

    if subscription.plan_type != "free" and subscription.end_date:
        if now > _as_moscow_datetime(subscription.end_date):
            downgrade_to_free(db, user_id, subscription)
            return True

        if subscription.last_reset_date:
            next_reset = _as_moscow_datetime(subscription.last_reset_date) + timedelta(days=30)
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


def get_words_used(db: Session, user_id: int) -> int:
    """Return the current usage without writing a zero-value row on reads."""
    words_used = db.query(UsageStats.words_used).filter(
        UsageStats.user_id == user_id,
    ).scalar()
    return int(words_used or 0)


def get_subscription_usage_snapshot(
        db: Session,
        user_id: int,
        subscription: Subscription,
) -> tuple[dict, str]:
    """Read usage and the Study Work trial in one query for the sidebar/API."""
    snapshot = (
        db.query(UsageStats.words_used, StudyWorkTrial.status)
        .select_from(Subscription)
        .outerjoin(UsageStats, UsageStats.user_id == Subscription.user_id)
        .outerjoin(StudyWorkTrial, StudyWorkTrial.user_id == Subscription.user_id)
        .filter(Subscription.id == subscription.id)
        .first()
    )
    words_used = int(snapshot.words_used or 0) if snapshot else 0
    trial_status = snapshot.status if snapshot and snapshot.status else "unavailable"
    limits = get_effective_plan_limits(subscription)
    word_limit = limits["word_limit"]

    return {
        "plan_type": subscription.plan_type,
        "words_used": words_used,
        "word_limit": word_limit,
        "remaining_words": None if word_limit is None else max(0, word_limit - words_used),
        "is_unlimited": word_limit is None,
        "max_words_per_request": limits["max_words_per_request"],
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
    }, trial_status


def check_request_word_limit(
        db: Session,
        user_id: int,
        text: str = "",
        max_words_override: int | None = None,
        subscription: Subscription | None = None,
        check_expiration: bool = True,
) -> None:
    """Enforce only the plan's per-request size limit, without charging words."""
    subscription = subscription or get_user_subscription(db, user_id)
    if check_expiration:
        check_subscription_expired(db, user_id, subscription)
    limits = get_effective_plan_limits(subscription)
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
    check_subscription_expired(db, user_id, subscription)
    max_words = get_study_work_max_words(subscription.plan_type)
    check_request_word_limit(
        db,
        user_id,
        text,
        max_words_override=max_words,
        subscription=subscription,
        check_expiration=False,
    )
    return max_words


def check_usage_limit(db: Session, user_id: int, text: str = "", max_words_override: int | None = None) -> bool:
    """
    Проверяет два ограничения:
    1. Лимит слов на один запрос (max_words_per_request) — фиксированный потолок для тарифа
    2. Месячную квоту слов (word_limit) — суммарно за расчётный период
    """
    subscription = get_user_subscription(db, user_id)
    check_subscription_expired(db, user_id, subscription)

    limits = get_effective_plan_limits(subscription)
    max_words_per_request = limits["max_words_per_request"]
    word_limit = limits["word_limit"]
    word_count = count_words(text)

    # 1. Проверка лимита на один запрос
    check_request_word_limit(
        db,
        user_id,
        text,
        max_words_override=max_words_override,
        subscription=subscription,
        check_expiration=False,
    )

    # 2. Проверка месячной квоты (пропускаем для безлимитного тарифа)
    if word_limit is not None:
        words_used = get_words_used(db, user_id)

        if words_used + word_count > word_limit:
            remaining = max(0, word_limit - words_used)
            word_balance = get_word_balance(
                db,
                user_id,
                subscription=subscription,
                words_used=words_used,
            )
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


def _locked_subscription(db: Session, user_id: int) -> Subscription:
    """Load a user's subscription while the parent User row is locked."""
    subscription = db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if subscription:
        return subscription

    subscription = Subscription(user_id=user_id, plan_type="free", is_active=True)
    db.add(subscription)
    db.flush()
    return subscription


def _locked_usage_stats(db: Session, user_id: int) -> UsageStats:
    """Load the single usage row while the parent User row is locked."""
    stats = db.execute(
        select(UsageStats)
        .where(UsageStats.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if stats:
        return stats

    stats = UsageStats(user_id=user_id, words_used=0)
    db.add(stats)
    db.flush()
    return stats


def _refresh_subscription_period_locked(subscription: Subscription, stats: UsageStats) -> None:
    """Apply expiration and monthly reset without committing a transaction."""
    now = get_current_datetime()
    if subscription.plan_type != "free" and subscription.end_date:
        if now > _as_moscow_datetime(subscription.end_date):
            subscription.plan_type = "free"
            subscription.end_date = None
            subscription.last_reset_date = None
            stats.words_used = 0
            return

        if subscription.last_reset_date:
            last_reset = _as_moscow_datetime(subscription.last_reset_date)
            next_reset = last_reset + timedelta(days=30)
            if now >= next_reset:
                while next_reset <= now:
                    next_reset += timedelta(days=30)
                subscription.last_reset_date = next_reset - timedelta(days=30)
                stats.words_used = 0


def _raise_insufficient_word_balance(
        word_count: int,
        subscription_remaining: int,
        extra_words: int,
) -> None:
    available_words = subscription_remaining + extra_words
    missing_words = word_count - available_words
    raise HTTPException(
        status_code=429,
        detail=(
            f"Недостаточно слов для этого запроса. "
            f"Доступно: {available_words} слов "
            f"(по подписке: {subscription_remaining}, доп. слова: {extra_words}). "
            f"Не хватает: {missing_words} слов. "
            f"Повысьте тариф или докупите пакет слов."
        ),
    )


def charge_words(
        db: Session,
        user_id: int,
        word_count: int,
        *,
        reason: str,
        max_words_override: int | None = None,
) -> dict:
    """Atomically charge a completed AI request and record every debit.

    The user row is locked first. This serializes a user's balance changes
    across web workers; usage statistics, subscription quota and purchased
    credits are then locked and updated in the same database transaction.
    Call this only after the provider has returned a usable result.
    """
    if word_count <= 0:
        return {"operation_id": None, "subscription_words": 0, "credit_words": 0}

    operation_id = str(uuid4())
    try:
        # FastAPI dependencies may already have a read transaction open.
        # A savepoint works in both that case and a fresh Session; the final
        # commit below releases PostgreSQL row locks immediately.
        with db.begin_nested():
            user = db.execute(
                select(User).where(User.id == user_id).with_for_update()
            ).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="Пользователь не найден.")

            subscription = _locked_subscription(db, user_id)
            stats = _locked_usage_stats(db, user_id)
            _refresh_subscription_period_locked(subscription, stats)

            limits = get_effective_plan_limits(subscription)
            max_words_per_request = max_words_override or limits["max_words_per_request"]
            if word_count > max_words_per_request:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Превышен лимит слов за один запрос. Максимум: {max_words_per_request}. "
                        f"Сейчас: {word_count}. Разделите текст на несколько запросов."
                    ),
                )

            word_limit = limits["word_limit"]
            subscription_remaining = (
                word_count
                if word_limit is None
                else max(0, word_limit - (stats.words_used or 0))
            )
            subscription_used = min(word_count, subscription_remaining)
            credits_left = word_count - subscription_used

            credits: list[WordTransaction] = []
            if credits_left:
                credits = db.execute(
                    select(WordTransaction)
                    .where(
                        WordTransaction.user_id == user_id,
                        WordTransaction.kind == "credit",
                        WordTransaction.bucket.in_(("bonus", "purchased")),
                        WordTransaction.status == "confirmed",
                        WordTransaction.remaining_words > 0,
                    )
                    .order_by(WordTransaction.id.asc())
                    .with_for_update()
                ).scalars().all()
                available_credits = sum(credit.remaining_words for credit in credits)
                if available_credits < credits_left:
                    _raise_insufficient_word_balance(
                        word_count,
                        0 if word_limit is None else subscription_remaining,
                        available_credits,
                    )

            if word_limit is not None:
                stats.words_used = (stats.words_used or 0) + subscription_used

            if subscription_used:
                db.add(WordTransaction(
                    user_id=user_id,
                    operation_id=operation_id,
                    kind="debit",
                    bucket="subscription",
                    reason=reason,
                    words=subscription_used,
                    remaining_words=0,
                    status="confirmed",
                ))

            credit_used = 0
            for credit in credits:
                if not credits_left:
                    break
                used = min(credits_left, credit.remaining_words)
                credit.remaining_words -= used
                credits_left -= used
                credit_used += used
                db.add(WordTransaction(
                    user_id=user_id,
                    operation_id=operation_id,
                    kind="debit",
                    bucket=credit.bucket,
                    reason=reason,
                    words=used,
                    remaining_words=0,
                    status="confirmed",
                    source_transaction_id=credit.id,
                ))

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "operation_id": operation_id,
        "subscription_words": subscription_used,
        "credit_words": credit_used,
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
    logger.info("Reset word-usage statistics for user_id=%s", user_id)
