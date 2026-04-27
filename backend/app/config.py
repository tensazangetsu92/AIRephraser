# app/config.py
from pathlib import Path

# Корневые пути
BACKEND_DIR = Path(__file__).parent.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
FRONTEND_PATH = FRONTEND_DIR / "index.html"

# Настройки CORS
CORS_ORIGINS = ["*"]
CORS_CREDENTIALS = True
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]

# Настройки API
API_TITLE = "Humary API"
API_DESCRIPTION = "AI Text Humanizer API"
API_VERSION = "1.0.0"