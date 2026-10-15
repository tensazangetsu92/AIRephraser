"""Regression checks for password hashing and online brute-force protection."""

import hashlib
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import ApiRateLimit, Base, User
from app.rate_limit import (
    LOGIN_FAILURE_LIMIT,
    clear_failed_login_attempts,
    enforce_login_failure_lock,
    record_failed_login,
)
from auth import authenticate_user, get_hash_password, verify_password


class AuthenticationSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_new_hash_is_salted_bcrypt_and_legacy_hash_is_upgraded(self) -> None:
        password = "correct-horse-battery-staple"
        new_hash = get_hash_password(password)
        self.assertTrue(new_hash.startswith("$2"))
        self.assertNotEqual(new_hash, get_hash_password(password))
        self.assertTrue(verify_password(password, new_hash))
        self.assertFalse(verify_password("wrong-password", new_hash))

        legacy_hash = hashlib.sha256((password + "humary_salt_2024").encode("utf-8")).hexdigest()
        user = User(email="legacy@example.test", password_hash=legacy_hash, is_active=True)
        self.session.add(user)
        self.session.commit()

        authenticated = authenticate_user(self.session, user.email, password)
        self.assertIsNotNone(authenticated)
        self.session.refresh(user)
        self.assertTrue(user.password_hash.startswith("$2"))
        self.assertTrue(verify_password(password, user.password_hash))

    def test_five_failed_attempts_lock_email_and_success_clears_counter(self) -> None:
        email = "bruteforce@example.test"
        for _ in range(LOGIN_FAILURE_LIMIT):
            record_failed_login(self.session, email)

        with self.assertRaises(HTTPException) as raised:
            enforce_login_failure_lock(self.session, email)
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("Retry-After", raised.exception.headers)

        clear_failed_login_attempts(self.session, email)
        enforce_login_failure_lock(self.session, email)
        self.assertEqual(self.session.query(ApiRateLimit).count(), 0)


if __name__ == "__main__":
    unittest.main()
