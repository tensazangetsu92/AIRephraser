"""Safe one-time Robokassa checkout and fulfilment helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import logging
import secrets
from typing import Mapping
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import (
    PAYMENTS_ENABLED,
    ROBOKASSA_HASH_ALGORITHM,
    ROBOKASSA_IS_TEST,
    ROBOKASSA_MERCHANT_LOGIN,
    ROBOKASSA_PASSWORD1,
    ROBOKASSA_PASSWORD2,
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
PAYMENT_PROVIDER = "robokassa"
PAYMENT_CURRENCY = "RUB"
ROBOKASSA_CHECKOUT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"
_MAX_INVOICE_ID = 9_223_372_036_854_775_807
_CUSTOM_ORDER_PARAMETER = "Shp_order"


class PaymentProviderError(RuntimeError):
    """A provider interaction failed without exposing configuration details."""


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


def _fiscal_receipt(order: Payment) -> str:
    """Return the URL-encoded one-item receipt required by Robocheki SMZ.

    Humary sells a single digital service per checkout. The price is always
    calculated server-side from the product configuration, so the fiscal item
    cannot be substituted by the browser.
    """
    amount, _ = product_details(order.product_type, order.product_id)
    if order.product_type == PRODUCT_SUBSCRIPTION:
        item_name = f"Humary: тариф {order.product_id} на 30 дней"
    elif order.product_type == PRODUCT_WORD_PACKAGE:
        package = PURCHASE_PACKAGES[order.product_id]
        item_name = f"Humary: пакет {package['words']} слов"
    else:
        raise PaymentProviderError("Unknown product for fiscal receipt")

    receipt = {
        "items": [{
            "name": item_name,
            "quantity": 1,
            "sum": float(amount),
            "payment_method": "full_payment",
            "payment_object": "service",
            "tax": "none",
        }],
    }
    # Robokassa's HTML-form example uses application/x-www-form-urlencoded
    # encoding for Receipt (not encodeURIComponent): spaces become "+" and
    # non-ASCII characters are represented by JSON \u escapes.  The exact
    # encoded value is included in SignatureValue, so it must use that same
    # canonical representation.
    return quote_plus(
        json.dumps(receipt, ensure_ascii=True, separators=(",", ":")),
        safe="",
    )


def _new_invoice_id(db: Session) -> str:
    """Return an unused positive 64-bit invoice number required by Robokassa."""
    for _ in range(20):
        invoice_id = str(secrets.randbelow(_MAX_INVOICE_ID - 1) + 1)
        exists = db.query(Payment.id).filter(Payment.provider_payment_id == invoice_id).first()
        if not exists:
            return invoice_id
    raise PaymentProviderError("Could not allocate a payment invoice number")


def create_payment_order(db: Session, user_id: int, product_type: str, product_id: str) -> Payment:
    amount, _ = product_details(product_type, product_id)
    order = Payment(
        id=str(uuid4()),
        user_id=user_id,
        provider=PAYMENT_PROVIDER,
        provider_payment_id=_new_invoice_id(db),
        idempotence_key=str(uuid4()),
        product_type=product_type,
        product_id=product_id,
        amount=amount,
        currency=PAYMENT_CURRENCY,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _signature(parts: list[str]) -> str:
    source = ":".join(parts).encode("utf-8")
    return hashlib.new(ROBOKASSA_HASH_ALGORITHM, source).hexdigest().lower()


def create_provider_payment(order: Payment, customer_email: str) -> dict[str, object]:
    """Build a signed POST checkout form; prices never come from the browser."""
    if not order.provider_payment_id:
        raise PaymentProviderError("Payment invoice number is missing")

    _, description = product_details(order.product_type, order.product_id)
    amount = f"{Decimal(order.amount):.2f}"
    invoice_id = order.provider_payment_id
    custom_parameters = {_CUSTOM_ORDER_PARAMETER: order.id}
    receipt = _fiscal_receipt(order)
    signature_parts = [
        ROBOKASSA_MERCHANT_LOGIN,
        amount,
        invoice_id,
        receipt,
        ROBOKASSA_PASSWORD1,
        *[f"{key}={value}" for key, value in sorted(custom_parameters.items())],
    ]
    params = {
        "MerchantLogin": ROBOKASSA_MERCHANT_LOGIN,
        "OutSum": amount,
        "InvId": invoice_id,
        "Description": description[:100],
        "Receipt": receipt,
        "SignatureValue": _signature(signature_parts),
        "Email": customer_email,
        "Culture": "ru",
        **custom_parameters,
    }
    if ROBOKASSA_IS_TEST:
        params["IsTest"] = "1"
    return {
        "id": invoice_id,
        "checkout_url": ROBOKASSA_CHECKOUT_URL,
        "checkout_fields": params,
    }


def public_payment_status(order: Payment) -> dict[str, str | bool]:
    return {
        "id": order.id,
        "status": order.status,
        "fulfilled": order.fulfilled_at is not None,
        "product_type": order.product_type,
        "product_id": order.product_id,
        "amount": f"{Decimal(order.amount):.2f}",
        "currency": order.currency,
    }


def _result_signature_matches(parameters: Mapping[str, str]) -> bool:
    amount = parameters.get("OutSum", "")
    invoice_id = parameters.get("InvId", "")
    received_signature = parameters.get("SignatureValue", "")
    order_id = parameters.get(_CUSTOM_ORDER_PARAMETER, "")
    if not (amount and invoice_id and received_signature and order_id):
        return False
    expected_signature = _signature(
        [amount, invoice_id, ROBOKASSA_PASSWORD2, f"{_CUSTOM_ORDER_PARAMETER}={order_id}"]
    )
    return hmac.compare_digest(expected_signature, received_signature.lower())


def _result_amount_matches(order: Payment, raw_amount: str) -> bool:
    try:
        return Decimal(raw_amount) == Decimal(order.amount)
    except (InvalidOperation, TypeError, ValueError):
        return False


def reconcile_provider_payment(db: Session, parameters: Mapping[str, str]) -> Payment | None:
    """Verify a signed ResultURL notification and fulfil exactly once."""
    if not _result_signature_matches(parameters):
        logger.warning("Rejected Robokassa ResultURL notification with an invalid signature")
        return None

    invoice_id = parameters["InvId"]
    order_id = parameters[_CUSTOM_ORDER_PARAMETER]
    order = (
        db.query(Payment)
        .filter(Payment.provider_payment_id == invoice_id)
        .with_for_update()
        .one_or_none()
    )
    if not order or order.provider != PAYMENT_PROVIDER or order.id != order_id:
        logger.warning("Rejected Robokassa ResultURL notification for an unknown payment")
        return None

    if not _result_amount_matches(order, parameters["OutSum"]):
        order.status = "verification_failed"
        db.commit()
        logger.error("Rejected Robokassa payment with an unexpected amount for order_id=%s", order.id)
        return order

    if order.fulfilled_at is not None:
        return order

    if order.product_type == PRODUCT_SUBSCRIPTION:
        upgrade_subscription(
            db,
            order.user_id,
            order.product_id,
            payment_id=invoice_id,
            duration_days=30,
            commit=False,
        )
    elif order.product_type == PRODUCT_WORD_PACKAGE:
        purchase_word_package(
            db,
            order.user_id,
            order.product_id,
            payment_id=invoice_id,
            commit=False,
        )
    else:
        order.status = "verification_failed"
        db.commit()
        logger.error("Rejected Robokassa payment with an unknown product for order_id=%s", order.id)
        return order

    order.status = "succeeded"
    order.fulfilled_at = get_current_datetime()
    db.commit()
    db.refresh(order)
    logger.info("Fulfilled Robokassa payment order_id=%s invoice_id=%s", order.id, invoice_id)
    return order
