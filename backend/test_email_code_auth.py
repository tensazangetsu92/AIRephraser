"""Regression test for the passwordless email-code authentication flow."""

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import Request, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, EmailLoginCode, StudyWorkTrial, Subscription, User
from app.models import EmailCodeConfirm, EmailCodeRequest
from app.routers import auth_routes
from app.legal_consent import LEGAL_DOCUMENTS_VERSION


def _request(consented: bool = True) -> Request:
    session = {}
    if consented:
        session = {
            "legal_documents_version": LEGAL_DOCUMENTS_VERSION,
            "legal_documents_accepted_at": datetime.now(timezone.utc).isoformat(),
        }
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 12345), "session": session})


class EmailCodeAuthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.codes: list[str] = []
        self.original_sender = auth_routes.send_email_login_code
        self.original_dev_code_setting = auth_routes.DEV_LOG_VERIFICATION_CODE
        auth_routes.send_email_login_code = self._capture_code
        auth_routes.DEV_LOG_VERIFICATION_CODE = False

    def tearDown(self):
        auth_routes.send_email_login_code = self.original_sender
        auth_routes.DEV_LOG_VERIFICATION_CODE = self.original_dev_code_setting
        self.db.close()
        self.engine.dispose()

    def _capture_code(self, _email: str, code: str) -> bool:
        self.codes.append(code)
        return True

    def test_new_user_is_created_only_after_valid_code_and_receives_session(self):
        email = "new-user@humary-test.dev"
        asyncio.run(auth_routes.request_email_code(EmailCodeRequest(email=email, registration=True), _request(), self.db))

        self.assertEqual(len(self.codes), 1)
        self.assertIsNone(self.db.query(User).filter(User.email == email).first())
        self.assertIsNotNone(self.db.query(EmailLoginCode).filter(EmailLoginCode.email == email).first())

        response = Response()
        token = asyncio.run(auth_routes.confirm_email_code(
            EmailCodeConfirm(email=email, code=self.codes[0], registration=True), response, _request(), self.db,
        ))

        user = self.db.query(User).filter(User.email == email).one()
        self.assertEqual(token.user["id"], user.id)
        self.assertIn("humary_refresh_token", response.headers["set-cookie"])
        self.assertIsNotNone(self.db.query(Subscription).filter(Subscription.user_id == user.id).first())
        self.assertIsNotNone(self.db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user.id).first())
        self.assertIsNotNone(self.db.query(EmailLoginCode).filter(EmailLoginCode.email == email, EmailLoginCode.used_at.is_not(None)).first())

    def test_existing_code_is_reused_without_a_second_email_or_rate_limit_error(self):
        email = "reuse-code@humary-test.dev"
        asyncio.run(auth_routes.request_email_code(EmailCodeRequest(email=email, registration=True), _request(), self.db))

        result = asyncio.run(auth_routes.request_email_code(EmailCodeRequest(email=email, registration=True), _request(), self.db))

        self.assertTrue(result["success"])
        self.assertTrue(result["already_sent"])
        self.assertEqual(result["email"], email)
        self.assertEqual(len(self.codes), 1)

    def test_registration_requires_legal_consent(self):
        with self.assertRaises(Exception) as raised:
            asyncio.run(auth_routes.request_email_code(
                EmailCodeRequest(email="no-consent@humary-test.dev", registration=True), _request(consented=False), self.db,
            ))
        self.assertEqual(getattr(raised.exception, "status_code", None), 403)

    def test_existing_user_can_sign_in_without_accepting_documents_again(self):
        email = "existing-user@humary-test.dev"
        self.db.add(User(email=email, password_hash="hash", is_active=True))
        self.db.commit()

        result = asyncio.run(auth_routes.request_email_code(
            EmailCodeRequest(email=email), _request(consented=False), self.db,
        ))

        self.assertTrue(result["success"])
        self.assertEqual(len(self.codes), 1)
