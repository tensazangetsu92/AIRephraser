"""Regression checks for browser security headers."""

import unittest

from starlette.responses import Response

from main import add_security_headers


class SecurityHeadersTests(unittest.IsolatedAsyncioTestCase):
    async def test_csp_allows_yandex_metrica_script_and_requests(self) -> None:
        async def next_handler(_request):
            return Response()

        response = await add_security_headers(object(), next_handler)
        csp = response.headers["Content-Security-Policy"]

        self.assertIn("script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://mc.yandex.ru", csp)
        self.assertIn("connect-src 'self' https://mc.yandex.ru", csp)
        self.assertIn("form-action 'self' https://robokassa.ru https://*.robokassa.ru", csp)


if __name__ == "__main__":
    unittest.main()
