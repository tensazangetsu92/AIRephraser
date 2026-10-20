"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from urllib.parse import urlparse

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
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise RuntimeError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
DEV_LOG_VERIFICATION_CODE = (
    _as_bool(os.getenv("DEV_LOG_VERIFICATION_CODE"), False)
    and not IS_PRODUCTION
)

DATABASE_URL = os.getenv("DATABASE_URL")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gigachat").strip().lower()
GPT_AUTH_KEY = os.getenv("GPT_AUTH_KEY")
GPT_API_BASE_URL = os.getenv(
    "GPT_API_BASE_URL", "https://foundation-models.api.cloud.ru/v1"
).rstrip("/")
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_API_BASE_URL = os.getenv("GIGACHAT_API_BASE_URL", "https://api.giga.chat/v1").rstrip("/")
GIGACHAT_AUTH_URL = os.getenv(
    "GIGACHAT_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
)
GIGACHAT_VERIFY_SSL = _as_bool(os.getenv("GIGACHAT_VERIFY_SSL"), True)
SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured.")
if LLM_PROVIDER not in {"gigachat", "cloud_gpt"}:
    raise RuntimeError("LLM_PROVIDER must be 'gigachat' or 'cloud_gpt'.")
if LLM_PROVIDER == "gigachat" and not GIGACHAT_AUTH_KEY:
    raise RuntimeError("GIGACHAT_AUTH_KEY must be configured for the gigachat provider.")
if LLM_PROVIDER == "cloud_gpt" and not GPT_AUTH_KEY:
    raise RuntimeError("GPT_AUTH_KEY must be configured for the cloud_gpt provider.")
def _is_safe_production_secret(value: str | None) -> bool:
    if not value or len(value) < 32:
        return False
    return value not in {
        "local-development-secret-change-me",
        "local-development-session-change-me",
        "generate-a-long-random-secret",
        "generate-a-second-long-random-secret",
    }


if IS_PRODUCTION and not (
    _is_safe_production_secret(SECRET_KEY)
    and _is_safe_production_secret(SESSION_SECRET_KEY)
):
    raise RuntimeError(
        "SECRET_KEY and SESSION_SECRET_KEY must each be unique random values of at least 32 characters in production."
    )

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

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").strip().rstrip("/")

API_TITLE = "Humary API"
API_DESCRIPTION = "AI Text Humanizer API"
API_VERSION = "1.0.0"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
RELOAD = _as_bool(os.getenv("RELOAD"), True)
COOKIE_SECURE = _as_bool(os.getenv("COOKIE_SECURE"), IS_PRODUCTION)


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


# Secure authentication cookies must never be disabled on the public site.
# Local HTTP development remains supported when APP_ENV is not production.
if IS_PRODUCTION:
    if not COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE must be true when APP_ENV=production.")
    if not _is_https_url(FRONTEND_URL):
        raise RuntimeError("FRONTEND_URL must use HTTPS when APP_ENV=production.")
    if any(not _is_https_url(origin) for origin in CORS_ORIGINS):
        raise RuntimeError("Every CORS_ORIGINS value must use HTTPS when APP_ENV=production.")

ENABLE_IN_APP_SCHEDULER = _as_bool(os.getenv("ENABLE_IN_APP_SCHEDULER"), not IS_PRODUCTION)
API_RATE_LIMIT_ENABLED = _as_bool(os.getenv("API_RATE_LIMIT_ENABLED"), True)

# User login session settings. The refresh session remains server-revocable,
# while the short-lived access token is used for individual API calls.
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = max(5, int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30")))
AUTH_REFRESH_TOKEN_IDLE_DAYS = max(1, int(os.getenv("AUTH_REFRESH_TOKEN_IDLE_DAYS", "14")))
AUTH_REFRESH_TOKEN_ABSOLUTE_DAYS = max(
    AUTH_REFRESH_TOKEN_IDLE_DAYS,
    int(os.getenv("AUTH_REFRESH_TOKEN_ABSOLUTE_DAYS", "30")),
)

MODEL_NAME = os.getenv("MODEL_NAME", "GigaChat-2")
DETECTOR_MODEL_NAME = os.getenv("DETECTOR_MODEL_NAME", MODEL_NAME)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
LLM_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
LLM_MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "3")))
USER_PROCESSING_LOCK_TTL_SECONDS = int(os.getenv("USER_PROCESSING_LOCK_TTL_SECONDS", "7200"))

YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID")
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET")
YANDEX_REDIRECT_URI = os.getenv(
    "YANDEX_REDIRECT_URI", "http://localhost:8000/auth/yandex/callback"
)
VK_ID_APP_ID = os.getenv("VK_ID_APP_ID")
VK_ID_REDIRECT_URI = os.getenv(
    "VK_ID_REDIRECT_URI", "http://localhost:8000/auth/vk/callback"
)

SMTP_HOST = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
SMTP_PORT = int(os.getenv("SMTP_PORT", "2525"))
SMTP_USE_SSL = _as_bool(os.getenv("SMTP_USE_SSL"), False)
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@humary.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Humary")

# Payments remain disabled until a real or test YooKassa shop is configured.
# Keeping this explicit prevents a copied credential from enabling checkout by
# accident before the public legal/payment information is ready.
PAYMENTS_ENABLED = _as_bool(os.getenv("PAYMENTS_ENABLED"), False)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
YOOKASSA_RETURN_URL = os.getenv(
    "YOOKASSA_RETURN_URL", f"{FRONTEND_URL}/pricing"
).strip().rstrip("/")
YOOKASSA_API_BASE_URL = "https://api.yookassa.ru/v3"

if PAYMENTS_ENABLED and not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
    raise RuntimeError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are required when PAYMENTS_ENABLED=true.")
if bool(YOOKASSA_SHOP_ID) != bool(YOOKASSA_SECRET_KEY):
    raise RuntimeError("Configure both YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY, or neither.")
if PAYMENTS_ENABLED and IS_PRODUCTION and not _is_https_url(YOOKASSA_RETURN_URL):
    raise RuntimeError("YOOKASSA_RETURN_URL must use HTTPS when payments are enabled in production.")
