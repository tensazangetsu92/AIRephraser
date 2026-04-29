# backend/app/oauth.py (альтернативная версия - без CSRF)
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets
import os
import httpx
from sqlalchemy import func

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from app.database import get_db, User
from auth import create_access_token, hash_password

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/login")
async def google_login(request: Request):
    """Простой редирект без state (упрощенный метод)"""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }

    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    redirect_url = f"{GOOGLE_AUTH_URL}?{query_string}"

    return RedirectResponse(url=redirect_url)


@router.get("/callback")
async def google_auth_callback(request: Request, code: str = None, db: Session = Depends(get_db)):
    """Обработка callback с code (без state)"""
    try:
        # Получаем code из URL
        if not code:
            raise HTTPException(status_code=400, detail="No code provided")

        # Обмениваем code на токен
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data=token_data)
            token_json = token_resp.json()

        if "error" in token_json:
            raise HTTPException(status_code=400, detail=f"Token error: {token_json.get('error')}")

        access_token = token_json.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="No access token")

        # Получаем информацию о пользователе
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_info = user_resp.json()

        if "error" in user_info:
            raise HTTPException(status_code=400, detail=f"Userinfo error: {user_info.get('error')}")

        # ПРИВОДИМ EMAIL К НИЖНЕМУ РЕГИСТРУ
        email = user_info.get("email", "").lower()
        username = user_info.get("name", email.split("@")[0] if email else "user")

        if not email:
            raise HTTPException(status_code=400, detail="No email from Google")

        print(f"Google auth: email={email}, username={username}")

        # Ищем пользователя с регистронезависимым поиском
        db_user = db.query(User).filter(func.lower(User.email) == email).first()

        if not db_user:
            random_password = secrets.token_urlsafe(16)
            hashed_pw = hash_password(random_password)

            db_user = User(
                email=email,  # сохраняем в нижнем регистре
                username=username,
                password_hash=hashed_pw,
                is_active=True
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            print(f"Создан пользователь: {email}")

        # Создаем JWT
        jwt_token = create_access_token(data={"sub": db_user.email})

        # Редирект на фронт
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
        redirect_url = f"{frontend_url}/?token={jwt_token}"

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print(f"Google auth error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка: {str(e)}")