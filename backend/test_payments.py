"""Unit tests for the one-time YooKassa payment boundary."""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, Payment, User
from app.payments import (
    PRODUCT_SUBSCRIPTION,
    PRODUCT_WORD_PACKAGE,
    _provider_amount_matches,
    _provider_metadata_matches,
    product_details,
    reconcile_provider_payment,
    require_payments_enabled,
)


class PaymentProductTests(unittest.TestCase):
    def test_product_prices_are_server_owned(self) -> None:
        self.assertEqual(product_details(PRODUCT_SUBSCRIPTION, "premium")[0], Decimal("179.00"))
        self.assertEqual(product_details(PRODUCT_WORD_PACKAGE, "words_2000")[0], Decimal("60.00"))

    def test_free_or_unknown_product_cannot_be_paid_for(self) -> None:
        for product_type, product_id in ((PRODUCT_SUBSCRIPTION, "free"), (PRODUCT_WORD_PACKAGE, "nope")):
            with self.assertRaises(HTTPException) as raised:
                product_details(product_type, product_id)
            self.assertEqual(raised.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_stays_disabled_without_explicit_enablement(self) -> None:
        with patch("app.payments.PAYMENTS_ENABLED", False):
            with self.assertRaises(HTTPException) as raised:
                require_payments_enabled()
        self.assertEqual(raised.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_provider_result_must_match_order_amount_and_metadata(self) -> None:
        order = MagicMock(
            id="order-1",
            user_id=42,
            product_type=PRODUCT_SUBSCRIPTION,
            product_id="premium",
            amount=Decimal("179.00"),
            currency="RUB",
        )
        provider_payment = {
            "amount": {"value": "179.00", "currency": "RUB"},
            "metadata": {
                "humary_payment_id": "order-1",
                "humary_user_id": "42",
                "humary_product_type": PRODUCT_SUBSCRIPTION,
                "humary_product_id": "premium",
            },
        }
        self.assertTrue(_provider_amount_matches(order, provider_payment))
        self.assertTrue(_provider_metadata_matches(order, provider_payment))
        provider_payment["amount"]["value"] = "1.00"
        self.assertFalse(_provider_amount_matches(order, provider_payment))

    def test_verified_payment_is_fulfilled_once(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        user = User(email="payment-test@example.com", password_hash="not-used")
        session.add(user)
        session.commit()
        order = Payment(
            id="order-verified",
            user_id=user.id,
            provider="yookassa",
            idempotence_key="idempotence-key-verified",
            product_type=PRODUCT_SUBSCRIPTION,
            product_id="premium",
            amount=Decimal("179.00"),
            currency="RUB",
            status="pending",
        )
        session.add(order)
        session.commit()
        provider_payment = {
            "id": "provider-payment-verified",
            "status": "succeeded",
            "paid": True,
            "amount": {"value": "179.00", "currency": "RUB"},
            "metadata": {
                "humary_payment_id": order.id,
                "humary_user_id": str(user.id),
                "humary_product_type": PRODUCT_SUBSCRIPTION,
                "humary_product_id": "premium",
            },
        }

        fulfilled = reconcile_provider_payment(session, provider_payment)
        self.assertIsNotNone(fulfilled)
        self.assertIsNotNone(fulfilled.fulfilled_at)
        self.assertEqual(fulfilled.status, "succeeded")

        # A duplicate webhook cannot reset the entitlement or create a new order.
        again = reconcile_provider_payment(session, provider_payment)
        self.assertEqual(again.id, order.id)
        self.assertEqual(session.query(Payment).count(), 1)


if __name__ == "__main__":
    unittest.main()
