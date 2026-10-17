import unittest
from unittest.mock import patch

from app import email_utils


class AuthenticationEmailTemplateTests(unittest.TestCase):
    def _render_html(self, send_function, subject_fragment: str) -> str:
        with patch.object(email_utils, "_send_message_via_smtp") as send_message:
            self.assertTrue(send_function("reader@example.com", "123456"))

        message = send_message.call_args.args[0]
        self.assertIn(subject_fragment, message["Subject"])
        return message.get_payload()[0].get_payload(decode=True).decode("utf-8")

    def test_login_email_uses_light_humary_palette(self):
        html = self._render_html(email_utils.send_email_login_code, "Humary")

        self.assertIn("background:#f4f6fb", html)
        self.assertIn("background:#ffffff", html)
        self.assertIn("background:#edf2ff", html)
        self.assertNotIn("background:#1f1f1e", html)

    def test_password_reset_email_uses_light_humary_palette(self):
        html = self._render_html(email_utils.send_password_reset_email, "Humary")

        self.assertIn("background:#f4f6fb", html)
        self.assertIn("background:#ffffff", html)
        self.assertIn("background:#edf2ff", html)
        self.assertNotIn("background:#1f1f1e", html)
