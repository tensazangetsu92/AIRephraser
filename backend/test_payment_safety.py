"""Regression tests: browser requests must never grant paid access."""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException, status

from app.routers.subscription_routes import (
    PAYMENTS_NOT_AVAILABLE_DETAIL,
    purchase_word_package_endpoint,
    upgrade_subscription_endpoint,
)


class PaymentSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_endpoint_never_activates_a_paid_plan(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upgrade_subscription_endpoint(current_user=MagicMock())

        self.assertEqual(raised.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(raised.exception.detail, PAYMENTS_NOT_AVAILABLE_DETAIL)

    async def test_word_package_endpoint_never_credits_words(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await purchase_word_package_endpoint(current_user=MagicMock())

        self.assertEqual(raised.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(raised.exception.detail, PAYMENTS_NOT_AVAILABLE_DETAIL)


if __name__ == "__main__":
    unittest.main()
