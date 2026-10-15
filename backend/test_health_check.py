"""Regression checks for the public availability endpoint."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from main import health_check


class HealthCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_ready_only_when_database_is_available(self) -> None:
        db = MagicMock()
        with patch("main.SessionLocal", return_value=db):
            response = await health_check()

        self.assertEqual(response, {"status": "ok", "checks": {"database": "ok"}})
        db.execute.assert_called_once()
        db.close.assert_called_once()

    async def test_returns_503_without_database_error_details(self) -> None:
        db = MagicMock()
        db.execute.side_effect = SQLAlchemyError("database password must not be exposed")

        with patch("main.SessionLocal", return_value=db):
            with self.assertRaises(HTTPException) as raised:
                await health_check()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "Service temporarily unavailable.")
        self.assertNotIn("password", raised.exception.detail.lower())
        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
