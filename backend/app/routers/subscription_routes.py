# app/routers/subscription_routes.py
from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import SubscriptionCreate
from app.database import get_db, User
from auth import get_current_user
from app.subscription import (
    get_user_subscription,
    upgrade_subscription,
    get_usage_stats,
    get_plan_limits,
    check_subscription_expired,
    SUBSCRIPTION_PLANS,
)

router = APIRouter(tags=["subscription"])


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получить информацию о подписке пользователя"""
    check_subscription_expired(db, current_user.id)

    subscription = get_user_subscription(db, current_user.id)
    usage_stats = get_usage_stats(db, current_user.id)
    limits = get_plan_limits(subscription.plan_type)

    return {
        "success": True,
        "subscription": {
            "id": subscription.id,
            "plan_type": subscription.plan_type,
            "is_active": subscription.is_active,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "total_requests": limits["total_requests"],
            "max_words": limits["max_words"]
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
    limits = get_plan_limits(subscription.plan_type)

    return {
        "success": True,
        "message": f"Subscription upgraded to {plan_data.plan_type}",
        "subscription": {
            "plan_type": subscription.plan_type,
            "end_date": subscription.end_date,
            "total_requests": limits["total_requests"],
            "max_words": limits["max_words"]
        }
    }


@router.get("/subscription/plans")
async def get_subscription_plans():
    """Получить список доступных планов подписки"""
    return {
        "success": True,
        "plans": SUBSCRIPTION_PLANS
    }