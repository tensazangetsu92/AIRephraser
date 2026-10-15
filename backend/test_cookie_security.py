"""Regression checks for authentication cookie security flags."""

import unittest
from unittest.mock import patch

from starlette.responses import Response

from auth import REFRESH_COOKIE_NAME, clear_refresh_token_cookie, set_refresh_token_cookie


class CookieSecurityTests(unittest.TestCase):
    def test_refresh_cookie_is_httponly_lax_and_scoped_to_root(self) -> None:
        response = Response()
        set_refresh_token_cookie(response, "opaque-token")
        header = response.headers["set-cookie"].lower()

        self.assertIn(f"{REFRESH_COOKIE_NAME}=opaque-token", header)
        self.assertIn("httponly", header)
        self.assertIn("samesite=lax", header)
        self.assertIn("path=/", header)
        self.assertIn("max-age=2592000", header)

    def test_secure_flag_is_enabled_for_https_deployments_and_logout(self) -> None:
        with patch("auth.COOKIE_SECURE", True):
            issued = Response()
            set_refresh_token_cookie(issued, "opaque-token")
            self.assertIn("secure", issued.headers["set-cookie"].lower())

            deleted = Response()
            clear_refresh_token_cookie(deleted)
            header = deleted.headers["set-cookie"].lower()
            self.assertIn("httponly", header)
            self.assertIn("samesite=lax", header)
            self.assertIn("secure", header)
            self.assertIn("max-age=0", header)


if __name__ == "__main__":
    unittest.main()
