"""One-time Robokassa checkout endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Payment, User, get_db
from app.legal_consent import has_current_legal_consent
from app.payments import (
    PRODUCT_SUBSCRIPTION,
    PRODUCT_WORD_PACKAGE,
    PaymentProviderError,
    create_payment_order,
    create_provider_payment,
    public_payment_status,
    reconcile_provider_payment,
    require_payments_enabled,
)
from auth import get_current_user


router = APIRouter(prefix="/payments/robokassa", tags=["payments"])


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
    if not has_current_legal_consent(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Войдите в аккаунт заново и примите актуальные Условия использования.",
        )

    order = create_payment_order(db, current_user.id, payload.product_type, payload.product_id)
    try:
        provider_payment = create_provider_payment(order, current_user.email)
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
        "checkout_url": provider_payment["checkout_url"],
        "checkout_fields": provider_payment["checkout_fields"],
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
    return {"success": True, "payment": public_payment_status(order)}


@router.post("/result", status_code=status.HTTP_200_OK)
async def robokassa_result(request: Request, db: Session = Depends(get_db)):
    """Verify a signed server ResultURL callback before granting paid access."""
    form = await request.form()
    parameters = {key: value for key, value in form.items() if isinstance(value, str)}
    order = reconcile_provider_payment(db, parameters)
    if not order or order.status == "verification_failed":
        return PlainTextResponse("bad request", status_code=status.HTTP_400_BAD_REQUEST)
    return PlainTextResponse(f"OK{order.provider_payment_id}")
