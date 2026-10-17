"""Regression tests for deletion and one-time free entitlement handling."""

import asyncio
from datetime import datetime, timezone
import unittest

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.account_deletion import email_deletion_hmac, has_consumed_free_entitlement
from app.database import Base, DeletedAccountMarker, EmailLoginCode, StudyWorkTrial, Subscription, User
from app.routers.user_routes import delete_user_account
from app.subscription import (
    check_usage_limit,
    get_word_balance,
    get_user_subscription,
    grant_words,
    initialise_new_user_entitlements,
)


class AccountDeletionEntitlementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_deletion_removes_account_data_but_blocks_a_second_free_grant(self) -> None:
        email = "student@example.test"
        user = User(email=email, password_hash="not-used", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        initialise_new_user_entitlements(self.db, user.id, user.email)
        self.db.add(EmailLoginCode(
            email=email,
            code_hash="hash",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        ))
        self.db.commit()

        result = asyncio.run(delete_user_account(
            {"confirmation": "DELETE"}, Response(), user, self.db,
        ))

        self.assertEqual(result, {"success": True})
        self.assertIsNone(self.db.query(User).filter(User.email == email).first())
        self.assertIsNone(self.db.query(EmailLoginCode).filter(EmailLoginCode.email == email).first())
        marker = self.db.get(DeletedAccountMarker, email_deletion_hmac(email))
        self.assertIsNotNone(marker)
        self.assertNotIn(email, marker.email_hmac)
        self.assertTrue(has_consumed_free_entitlement(self.db, email))

        self.db.expunge(user)
        recreated = User(email=email, password_hash="not-used", is_active=True)
        self.db.add(recreated)
        self.db.commit()
        self.db.refresh(recreated)
        self.assertFalse(initialise_new_user_entitlements(self.db, recreated.id, recreated.email))

        subscription = get_user_subscription(self.db, recreated.id)
        self.assertFalse(subscription.free_entitlement_available)
        self.assertIsNone(self.db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == recreated.id).first())
        self.assertEqual(get_word_balance(self.db, recreated.id)["subscription_words"], 0)
        with self.assertRaises(HTTPException) as raised:
            check_usage_limit(self.db, recreated.id, "one two")
        self.assertEqual(raised.exception.status_code, 429)

        grant_words(self.db, recreated.id, "purchased", 10, "test:purchase")
        self.assertTrue(check_usage_limit(self.db, recreated.id, "one two"))


if __name__ == "__main__":
    unittest.main()
