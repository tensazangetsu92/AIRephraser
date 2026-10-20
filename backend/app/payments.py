"""Safe one-time YooKassa checkout and fulfilment helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging
import re
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import (
    PAYMENTS_ENABLED,
    YOOKASSA_API_BASE_URL,
    YOOKASSA_RETURN_URL,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
)
from app.database import Payment
from app.subscription import (
    PURCHASE_PACKAGES,
    SUBSCRIPTION_PLANS,
    get_current_datetime,
    purchase_word_package,
    upgrade_subscription,
)


logger = logging.getLogger("uvicorn.error")

PRODUCT_SUBSCRIPTION = "subscription"
PRODUCT_WORD_PACKAGE = "word_package"
PAYMENT_PROVIDER = "yookassa"
PAYMENT_CURRENCY = "RUB"
_PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,255}$")


class PaymentProviderError(RuntimeError):
    """A provider request failed without exposing sensitive response details."""


def require_payments_enabled() -> None:
    if not PAYMENTS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Онлайн-оплата пока не подключена.",
        )


def _money(value: int | Decimal | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def product_details(product_type: str, product_id: str) -> tuple[Decimal, str]:
    """Return only server-owned prices and descriptions for checkout."""
    if product_type == PRODUCT_SUBSCRIPTION:
        plan = SUBSCRIPTION_PLANS.get(product_id)
        if not plan or product_id == "free":
            raise HTTPException(status_code=400, detail="Некорректный тариф.")
        return _money(plan["price_monthly"]), f"Humary: тариф {product_id} на 30 дней"

    if product_type == PRODUCT_WORD_PACKAGE:
        package = PURCHASE_PACKAGES.get(product_id)
        if not package:
            raise HTTPException(status_code=400, detail="Некорректный пакет слов.")
        return _money(package["price_rub"]), f"Humary: пакет {package['words']} слов"

    raise HTTPException(status_code=400, detail="Некорректный товар.")


def create_payment_order(db: Session, user_id: int, product_type: str, product_id: str) -> Payment:
    amount, _ = product_details(product_type, product_id)
    order = Payment(
        id=str(uuid4()),
        user_id=user_id,
        provider=PAYMENT_PROVIDER,
        idempotence_key=str(uuid4()),
        product_type=product_type,
        product_id=product_id,
        amount=amount,
        currency=PAYMENT_CURRENCY,
        status="created",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


async def _provider_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    require_payments_enabled()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method,
                f"{YOOKASSA_API_BASE_URL}{path}",
                auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
                **kwargs,
            )
    except httpx.HTTPError as exc:
        raise PaymentProviderError("YooKassa is unavailable") from exc

    if response.status_code >= 400:
        raise PaymentProviderError(f"YooKassa returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise PaymentProviderError("YooKassa returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise PaymentProviderError("YooKassa returned an invalid response")
    return data


async def create_provider_payment(order: Payment) -> dict[str, Any]:
    _, description = product_details(order.product_type, order.product_id)
    payload = {
        "amount": {"value": f"{Decimal(order.amount):.2f}", "currency": order.currency},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"{YOOKASSA_RETURN_URL}?payment={order.id}",
        },
        "description": description,
        "metadata": {
            "humary_payment_id": order.id,
            "humary_user_id": str(order.user_id),
            "humary_product_type": order.product_type,
            "humary_product_id": order.product_id,
        },
    }
    return await _provider_request(
        "POST",
        "/payments",
        headers={"Idempotence-Key": order.idempotence_key},
        json=payload,
    )


async def get_provider_payment(provider_payment_id: str) -> dict[str, Any]:
    if not _PROVIDER_ID_PATTERN.fullmatch(provider_payment_id):
        raise PaymentProviderError("Invalid provider payment id")
    return await _provider_request("GET", f"/payments/{provider_payment_id}")


def save_provider_payment(db: Session, order: Payment, provider_payment: dict[str, Any]) -> Payment:
    provider_id = provider_payment.get("id")
    confirmation_url = (provider_payment.get("confirmation") or {}).get("confirmation_url")
    if not isinstance(provider_id, str) or not _PROVIDER_ID_PATTERN.fullmatch(provider_id):
        raise PaymentProviderError("YooKassa did not return a valid payment id")
    if not isinstance(confirmation_url, str) or not confirmation_url.startswith("https://"):
        raise PaymentProviderError("YooKassa did not return a checkout URL")

    order.provider_payment_id = provider_id
    order.status = str(provider_payment.get("status") or "pending")[:32]
    db.commit()
    db.refresh(order)
    return order


def public_payment_status(order: Payment) -> dict[str, Any]:
    return {
        "id": order.id,
        "status": order.status,
        "fulfilled": order.fulfilled_at is not None,
        "product_type": order.product_type,
        "product_id": order.product_id,
        "amount": f"{Decimal(order.amount):.2f}",
        "currency": order.currency,
    }


def _provider_amount_matches(order: Payment, provider_payment: dict[str, Any]) -> bool:
    amount = provider_payment.get("amount") or {}
    try:
        provider_amount = _money(amount.get("value"))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return provider_amount == Decimal(order.amount) and amount.get("currency") == order.currency


def _provider_metadata_matches(order: Payment, provider_payment: dict[str, Any]) -> bool:
    metadata = provider_payment.get("metadata") or {}
    return (
        metadata.get("humary_payment_id") == order.id
        and metadata.get("humary_user_id") == str(order.user_id)
        and metadata.get("humary_product_type") == order.product_type
        and metadata.get("humary_product_id") == order.product_id
    )


def reconcile_provider_payment(db: Session, provider_payment: dict[str, Any]) -> Payment | None:
    """Persist a provider status and fulfil exactly once after full verification."""
    provider_id = provider_payment.get("id")
    metadata = provider_payment.get("metadata") or {}
    order_id = metadata.get("humary_payment_id")
    if not isinstance(provider_id, str) or not isinstance(order_id, str):
        return None

    order = db.query(Payment).filter(Payment.id == order_id).with_for_update().one_or_none()
    if not order or order.provider != PAYMENT_PROVIDER:
        return None
    if order.provider_payment_id and order.provider_payment_id != provider_id:
        logger.warning("Rejected mismatched provider payment for order_id=%s", order.id)
        return None

    order.provider_payment_id = provider_id
    provider_status = str(provider_payment.get("status") or "unknown")[:32]
    order.status = provider_status

    if provider_status != "succeeded":
        db.commit()
        db.refresh(order)
        return order

    if order.fulfilled_at is not None:
        db.commit()
        db.refresh(order)
        return order

    if (
        provider_payment.get("paid") is not True
        or not _provider_amount_matches(order, provider_payment)
        or not _provider_metadata_matches(order, provider_payment)
    ):
        order.status = "verification_failed"
        db.commit()
        logger.error("Rejected unverified successful payment for order_id=%s", order.id)
        return order

    if order.product_type == PRODUCT_SUBSCRIPTION:
        upgrade_subscription(
            db,
            order.user_id,
            order.product_id,
            payment_id=provider_id,
            duration_days=30,
            commit=False,
        )
    elif order.product_type == PRODUCT_WORD_PACKAGE:
        purchase_word_package(
            db,
            order.user_id,
            order.product_id,
            payment_id=provider_id,
            commit=False,
        )
    else:
        order.status = "verification_failed"
        db.commit()
        logger.error("Rejected payment with unknown product for order_id=%s", order.id)
        return order

    order.status = "succeeded"
    order.fulfilled_at = get_current_datetime()
    db.commit()
    db.refresh(order)
    logger.info("Fulfilled YooKassa payment order_id=%s provider_payment_id=%s", order.id, provider_id)
    return order
