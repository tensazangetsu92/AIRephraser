"""Regression checks for credential redaction in application logs."""

import logging
import unittest

from main import SensitiveLogFilter, _redact_sensitive_log_values


class LoggingSecurityTests(unittest.TestCase):
    def test_redacts_passwords_tokens_and_cookies(self) -> None:
        message = (
            'password=very-secret new_password: "another-secret" '
            'access_token=jwt-value cookie=session-secret '
            'Authorization: Bearer jwt.header.signature '
            'X-API-Key=provider-secret'
        )
        sanitized = _redact_sensitive_log_values(message)

        self.assertNotIn("very-secret", sanitized)
        self.assertNotIn("another-secret", sanitized)
        self.assertNotIn("jwt-value", sanitized)
        self.assertNotIn("session-secret", sanitized)
        self.assertNotIn("jwt.header.signature", sanitized)
        self.assertNotIn("provider-secret", sanitized)
        self.assertEqual(sanitized.count("[REDACTED]"), 6)

    def test_filter_redacts_interpolated_log_arguments(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="Login rejected: password=%s",
            args=("very-secret",),
            exc_info=None,
        )

        self.assertTrue(SensitiveLogFilter().filter(record))
        self.assertEqual(record.getMessage(), "Login rejected: password=[REDACTED]")

    def test_redacts_oauth_callback_credentials_from_access_logs(self) -> None:
        message = (
            'GET /auth/vk/callback?code=oauth-one-time-code&state=csrf-state&'
            'device_id=device-identifier&ext_id=external-identifier HTTP/1.1'
        )
        sanitized = _redact_sensitive_log_values(message)

        for sensitive_value in (
            "oauth-one-time-code",
            "csrf-state",
            "device-identifier",
            "external-identifier",
        ):
            self.assertNotIn(sensitive_value, sanitized)
        self.assertEqual(sanitized.count("[REDACTED]"), 4)

    def test_redacts_full_user_text_in_structured_or_interpolated_logs(self) -> None:
        source_text = "Первое предложение пользователя.\nВторое предложение пользователя."
        rendered_payload = repr({"original_text": source_text})
        sanitized = _redact_sensitive_log_values(f"Request payload={rendered_payload}")

        self.assertNotIn("Первое предложение", sanitized)
        self.assertNotIn("Второе предложение", sanitized)
        self.assertEqual(sanitized, "Request payload=[REDACTED]")

        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="Provider rejected: text=%s",
            args=(source_text,),
            exc_info=None,
        )
        SensitiveLogFilter().filter(record)
        self.assertEqual(record.getMessage(), "Provider rejected: text=[REDACTED]")


if __name__ == "__main__":
    unittest.main()
