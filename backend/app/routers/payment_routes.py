"""One-time YooKassa checkout endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Payment, User, get_db
from app.payments import (
    PRODUCT_SUBSCRIPTION,
    PRODUCT_WORD_PACKAGE,
    PaymentProviderError,
    create_payment_order,
    create_provider_payment,
    get_provider_payment,
    public_payment_status,
    reconcile_provider_payment,
    require_payments_enabled,
    save_provider_payment,
)
from auth import get_current_user


router = APIRouter(prefix="/payments/yookassa", tags=["payments"])


class CheckoutRequest(BaseModel):
    product_type: Literal["subscription", "word_package"]
    product_id: str


@router.post("/create")
async def create_checkout(
        payload: CheckoutRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    require_payments_enabled()
    order = create_payment_order(db, current_user.id, payload.product_type, payload.product_id)
    try:
        provider_payment = await create_provider_payment(order)
        order = save_provider_payment(db, order, provider_payment)
        # A redirect payment is normally pending here, but fulfil immediately
        # if YooKassa already returned a verified successful status.
        order = reconcile_provider_payment(db, provider_payment) or order
    except PaymentProviderError as exc:
        order.status = "create_failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось создать платёж. Повторите попытку позже.",
        ) from exc

    return {
        "success": True,
        "payment": public_payment_status(order),
        "confirmation_url": provider_payment["confirmation"]["confirmation_url"],
    }


@router.get("/{payment_id}")
async def get_checkout_status(
        payment_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    order = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == current_user.id).one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден.")

    if order.provider_payment_id and order.fulfilled_at is None:
        try:
            provider_payment = await get_provider_payment(order.provider_payment_id)
            order = reconcile_provider_payment(db, provider_payment) or order
        except PaymentProviderError:
            # The webhook remains the source of delivery if the provider is temporarily unavailable.
            pass
    return {"success": True, "payment": public_payment_status(order)}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def yookassa_webhook(request: Request, db: Session = Depends(get_db)):
    """Accept a notification, then fetch and verify the payment from YooKassa."""
    try:
        payload = await request.json()
    except ValueError:
        return {"success": True}

    provider_id = ((payload or {}).get("object") or {}).get("id") if isinstance(payload, dict) else None
    if not isinstance(provider_id, str):
        return {"success": True}

    try:
        provider_payment = await get_provider_payment(provider_id)
        reconcile_provider_payment(db, provider_payment)
    except PaymentProviderError:
        # Return 200: a transient provider error must not disclose internals.
        # YooKassa will send a new event when the payment changes again, and a
        # signed-in user can also trigger reconciliation on the return page.
        return {"success": True}
    return {"success": True}
