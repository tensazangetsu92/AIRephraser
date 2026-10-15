"""Regression checks for persistent refresh sessions."""

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, User, UserRefreshSession
from auth import create_refresh_session, refresh_active_session


class RefreshSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.user = User(email="session@example.test", password_hash="hash", is_active=True)
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_same_cookie_remains_valid_after_repeated_access_token_refreshes(self) -> None:
        token = create_refresh_session(self.session, self.user)
        original_hash = self.session.query(UserRefreshSession.token_hash).scalar()

        first_user = refresh_active_session(self.session, token)
        second_user = refresh_active_session(self.session, token)

        self.assertEqual(first_user.id, self.user.id)
        self.assertEqual(second_user.id, self.user.id)
        self.assertEqual(self.session.query(UserRefreshSession.token_hash).scalar(), original_hash)
        last_used_at = self.session.query(UserRefreshSession.last_used_at).scalar()
        if last_used_at.tzinfo is None:
            # SQLite used in this test does not preserve timezone metadata.
            last_used_at = last_used_at.replace(tzinfo=timezone.utc)
        self.assertLessEqual(last_used_at, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
