# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл (на уровень выше)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# print(f"Loading .env from: {env_path}")
# print(f"File exists: {env_path.exists()}")
# print(f"API Key loaded: {os.getenv('OPENROUTER_API_KEY')}")
# ===== ПУТИ =====
BACKEND_DIR = Path(__file__).parent.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
FRONTEND_PATH = FRONTEND_DIR / "index.html"

# ===== НАСТРОЙКИ CORS =====
CORS_ORIGINS = ["*"]
CORS_CREDENTIALS = True
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]

# ===== НАСТРОЙКИ API =====
API_TITLE = "Humary API"
API_DESCRIPTION = "AI Text Humanizer API"
API_VERSION = "1.0.0"

# ===== СЕКРЕТНЫЕ КЛЮЧИ ИЗ .env =====
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-for-development")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "fallback-session-key-12345")

# ===== НАСТРОЙКИ СЕРВЕРА =====
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
RELOAD = os.getenv("RELOAD", "true").lower() == "true"

# ===== НАСТРОЙКИ МОДЕЛИ =====
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/llama-3-8b-instruct")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# Проверка для Google (опционально, можно не проверять при запуске)
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("⚠️ Google OAuth не настроен. Вход через Google не будет работать.")

# Проверка обязательных переменных
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не задан в .env файле!")