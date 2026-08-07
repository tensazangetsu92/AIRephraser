"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

# Local development uses backend/.env. On Render, variables are supplied by the
# platform and take precedence over values in this file.
load_dotenv(BACKEND_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

DATABASE_URL = os.getenv("DATABASE_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured.")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY must be configured.")
if IS_PRODUCTION and (not SECRET_KEY or not SESSION_SECRET_KEY):
    raise RuntimeError("SECRET_KEY and SESSION_SECRET_KEY must be configured in production.")

# Development-only defaults keep local setup convenient. Deployments must set
# the keys explicitly; do not use predictable fallback values in production.
SECRET_KEY = SECRET_KEY or "local-development-secret-change-me"
SESSION_SECRET_KEY = SESSION_SECRET_KEY or "local-development-session-change-me"

CORS_ORIGINS = _as_list(
    os.getenv("CORS_ORIGINS"),
    ["http://localhost:8000", "http://127.0.0.1:8000"],
)
CORS_CREDENTIALS = _as_bool(os.getenv("CORS_CREDENTIALS"), True)
CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_HEADERS = ["Authorization", "Content-Type"]

if CORS_CREDENTIALS and "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentials are enabled.")

API_TITLE = "Humary API"
API_DESCRIPTION = "AI Text Humanizer API"
API_VERSION = "1.0.0"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
RELOAD = _as_bool(os.getenv("RELOAD"), True)
COOKIE_SECURE = _as_bool(os.getenv("COOKIE_SECURE"), IS_PRODUCTION)
ENABLE_IN_APP_SCHEDULER = _as_bool(os.getenv("ENABLE_IN_APP_SCHEDULER"), not IS_PRODUCTION)

FREE_MODEL_NAME = os.getenv("FREE_MODEL_NAME", "meta-llama/llama-3-8b-instruct")
PAID_MODEL_NAME = os.getenv("PAID_MODEL_NAME", FREE_MODEL_NAME)
MODEL_NAME = os.getenv("MODEL_NAME", FREE_MODEL_NAME)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)

SMTP_HOST = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
SMTP_PORT = int(os.getenv("SMTP_PORT", "2525"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@humary.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Humary")
