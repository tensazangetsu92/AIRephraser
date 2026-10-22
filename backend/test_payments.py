"""Unit tests for the one-time Robokassa payment boundary."""

from decimal import Decimal
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, Payment, User
from app.payments import (
    PRODUCT_SUBSCRIPTION,
    PRODUCT_WORD_PACKAGE,
    _result_signature_matches,
    _signature,
    create_provider_payment,
    product_details,
    reconcile_provider_payment,
    require_payments_enabled,
)


class PaymentProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider_settings = patch.multiple(
            "app.payments",
            ROBOKASSA_MERCHANT_LOGIN="humary-demo",
            ROBOKASSA_PASSWORD1="password-one",
            ROBOKASSA_PASSWORD2="password-two",
            ROBOKASSA_RETURN_URL="https://humary.ru/pricing",
            ROBOKASSA_HASH_ALGORITHM="md5",
            ROBOKASSA_IS_TEST=True,
        )
        self.provider_settings.start()
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.user = User(email="payment-test@example.com", password_hash="not-used")
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.provider_settings.stop()

    def _order(self, invoice_id: str = "654321") -> Payment:
        order = Payment(
            id="order-verified",
            user_id=self.user.id,
            provider="robokassa",
            provider_payment_id=invoice_id,
            idempotence_key="idempotence-key-verified",
            product_type=PRODUCT_SUBSCRIPTION,
            product_id="premium",
            amount=Decimal("179.00"),
            currency="RUB",
            status="pending",
        )
        self.session.add(order)
        self.session.commit()
        return order

    @staticmethod
    def _result(order: Payment, amount: str = "179.00") -> dict[str, str]:
        values = {
            "OutSum": amount,
            "InvId": order.provider_payment_id,
            "Shp_order": order.id,
        }
        values["SignatureValue"] = _signature(
            [amount, order.provider_payment_id, "password-two", f"Shp_order={order.id}"]
        )
        return values

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

    def test_checkout_url_is_signed_and_uses_server_price(self) -> None:
        order = self._order()
        payment = create_provider_payment(order, self.user.email)
        query = parse_qs(urlsplit(payment["confirmation_url"]).query)
        self.assertEqual(query["OutSum"], ["179.00"])
        self.assertEqual(query["InvId"], ["654321"])
        self.assertEqual(query["Shp_order"], [order.id])
        self.assertEqual(query["IsTest"], ["1"])
        self.assertIn(f"payment={order.id}", query["SuccessUrl2"][0])

    def test_provider_result_signature_must_be_valid(self) -> None:
        order = self._order()
        result = self._result(order)
        self.assertTrue(_result_signature_matches(result))
        result["OutSum"] = "1.00"
        self.assertFalse(_result_signature_matches(result))

    def test_verified_payment_is_fulfilled_once(self) -> None:
        order = self._order()
        result = self._result(order)

        fulfilled = reconcile_provider_payment(self.session, result)
        self.assertIsNotNone(fulfilled)
        self.assertIsNotNone(fulfilled.fulfilled_at)
        self.assertEqual(fulfilled.status, "succeeded")

        # A duplicate ResultURL callback cannot create a second entitlement.
        again = reconcile_provider_payment(self.session, result)
        self.assertEqual(again.id, order.id)
        self.assertEqual(self.session.query(Payment).count(), 1)

    def test_signed_result_with_a_wrong_amount_is_not_fulfilled(self) -> None:
        order = self._order()
        rejected = reconcile_provider_payment(self.session, self._result(order, amount="1.00"))
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.status, "verification_failed")
        self.assertIsNone(rejected.fulfilled_at)


if __name__ == "__main__":
    unittest.main()
