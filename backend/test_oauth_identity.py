"""Regression checks for OAuth-only account identities."""

import unittest

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import SECRET_KEY
from app.database import Base, OAuthIdentity, User
from auth import ALGORITHM, create_user_access_token


class OAuthIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_vk_identity_can_create_an_account_without_email(self) -> None:
        user = User(email=None, password_hash="oauth-only", display_name="VK user", is_active=True)
        self.db.add(user)
        self.db.flush()
        self.db.add(OAuthIdentity(provider="vk", provider_subject="12345", user_id=user.id))
        self.db.commit()

        identity = self.db.query(OAuthIdentity).filter_by(provider="vk", provider_subject="12345").one()
        token = create_user_access_token(identity.user)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        self.assertIsNone(identity.user.email)
        self.assertEqual(payload["sub"], f"user:{user.id}")


if __name__ == "__main__":
    unittest.main()
