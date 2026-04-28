# main.py - точка входа
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from app.api import router
from app.config import CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS, SECRET_KEY
from app.oauth import router as google_router

# Создаем приложение
app = FastAPI(
    title="Humary API",
    description="AI Text Humanizer API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,  # используй свой SECRET_KEY
    session_cookie="humary_session",
    max_age=3600,  # сессия живет 1 час
    same_site="lax",  # для разработки
    https_only=False  # для разработки (HTTP)
)

app.include_router(router)
app.include_router(google_router)

# Монтируем статические файлы (CSS, JS)
frontend_path = Path(__file__).parent.parent / "frontend"

if (frontend_path / "css").exists():
    app.mount("/css", StaticFiles(directory=str(frontend_path / "css")), name="css")

if (frontend_path / "js").exists():
    app.mount("/js", StaticFiles(directory=str(frontend_path / "js")), name="js")

# Подключаем все роуты
app.include_router(router)

# Корневой эндпоинт для проверки
@app.get("/api", tags=["info"])
async def api_info():
    """Информация об API"""
    return {
        "name": "Humary API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }