"""Tests for persisted acceptance of legal documents."""

from datetime import datetime, timezone
import unittest

from app.database import User
from app.legal_consent import LEGAL_DOCUMENTS_VERSION, has_current_legal_consent


class LegalConsentTests(unittest.TestCase):
    def test_requires_the_current_document_version_and_timestamp(self):
        user = User(email="buyer@example.com", password_hash="hash")

        self.assertFalse(has_current_legal_consent(user))

        user.legal_documents_version = LEGAL_DOCUMENTS_VERSION
        self.assertFalse(has_current_legal_consent(user))

        user.legal_accepted_at = datetime.now(timezone.utc)
        self.assertTrue(has_current_legal_consent(user))


if __name__ == "__main__":
    unittest.main()
