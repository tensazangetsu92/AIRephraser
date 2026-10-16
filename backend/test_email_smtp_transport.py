"""Tests for encrypted SMTP connection modes."""

import unittest
from unittest.mock import MagicMock, patch

from app import email_utils


class SmtpTransportTests(unittest.TestCase):
    def setUp(self):
        self.original_use_ssl = email_utils.SMTP_USE_SSL

    def tearDown(self):
        email_utils.SMTP_USE_SSL = self.original_use_ssl

    def test_implicit_ssl_uses_smtp_ssl_without_starttls(self):
        email_utils.SMTP_USE_SSL = True
        server = MagicMock()

        with patch.object(email_utils.smtplib, "SMTP_SSL", return_value=server) as smtp_ssl, patch.object(email_utils.smtplib, "SMTP") as smtp:
            result = email_utils._open_smtp_connection()

        self.assertIs(result, server)
        smtp_ssl.assert_called_once()
        smtp.assert_not_called()
        server.starttls.assert_not_called()

    def test_starttls_uses_plain_smtp_then_upgrades_connection(self):
        email_utils.SMTP_USE_SSL = False
        server = MagicMock()

        with patch.object(email_utils.smtplib, "SMTP", return_value=server) as smtp, patch.object(email_utils.smtplib, "SMTP_SSL") as smtp_ssl:
            result = email_utils._open_smtp_connection()

        self.assertIs(result, server)
        smtp.assert_called_once()
        smtp_ssl.assert_not_called()
        self.assertEqual(server.ehlo.call_count, 2)
        server.starttls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
