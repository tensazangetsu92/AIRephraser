# app/routers/subscription_routes.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db, User
from auth import get_current_user
from app.subscription import (
    get_user_subscription,
    get_effective_plan_limits,
    get_study_work_max_words,
    get_subscription_usage_snapshot,
    check_subscription_expired,
    SUBSCRIPTION_PLANS,
    PURCHASE_PACKAGES,
    get_word_balance,
)

router = APIRouter(tags=["subscription"])

PAYMENTS_NOT_AVAILABLE_DETAIL = "Онлайн-оплата пока не подключена."


def _payments_not_available() -> None:
    """Block browser requests until a verified payment webhook is implemented."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=PAYMENTS_NOT_AVAILABLE_DETAIL,
    )


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получить информацию о подписке пользователя"""
    subscription = get_user_subscription(db, current_user.id)
    check_subscription_expired(db, current_user.id, subscription)
    usage_stats, study_work_trial_status = get_subscription_usage_snapshot(
        db,
        current_user.id,
        subscription,
    )
    limits = get_effective_plan_limits(subscription)
    word_balance = get_word_balance(
        db,
        current_user.id,
        subscription=subscription,
        words_used=usage_stats["words_used"],
    )

    return {
        "success": True,
        "subscription": {
            "id": subscription.id,
            "plan_type": subscription.plan_type,
            "is_active": subscription.is_active,
            "free_entitlement_available": subscription.free_entitlement_available,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "word_limit": limits["word_limit"],
            "max_words_per_request": limits["max_words_per_request"],
            "study_work_max_words_per_request": get_study_work_max_words(subscription.plan_type),
        },
        "study_work_trial": {
            "status": study_work_trial_status,
        },
        "usage": usage_stats,
        "available_plans": SUBSCRIPTION_PLANS,
        "word_balance": word_balance,
        "available_word_packages": PURCHASE_PACKAGES,
    }


@router.post("/subscription/word-packages/purchase")
async def purchase_word_package_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Reserved for a future payment-provider webhook flow.

    A browser request is never proof of payment, so it must not change a
    balance before the provider integration is implemented.
    """
    _ = current_user
    _payments_not_available()


@router.post("/subscription/upgrade")
async def upgrade_subscription_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Reserved for a future payment-provider webhook flow."""
    _ = current_user
    _payments_not_available()


@router.get("/subscription/plans")
async def get_subscription_plans(response: Response):
    """Получить список доступных планов подписки"""
    # Plans are public configuration, unlike a user's balance or active plan.
    response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
    return {
        "success": True,
        "plans": SUBSCRIPTION_PLANS
    }
