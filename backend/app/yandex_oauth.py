"""Yandex ID OAuth 2.0 login for the web application."""

import logging
import os
import secrets
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import FRONTEND_URL, YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET, YANDEX_REDIRECT_URI
from app.database import User, get_db
from app.subscription import initialise_new_user_entitlements
from app.legal_consent import persist_legal_consent, require_pending_legal_consent
from auth import (
    create_refresh_session,
    get_hash_password,
    set_refresh_token_cookie,
)


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/auth/yandex", tags=["yandex-auth"])

YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USERINFO_URL = "https://login.yandex.ru/info"
OAUTH_TIMEOUT_SECONDS = 15.0


def _get_yandex_avatar_url(profile: dict) -> str | None:
    """Build a stable Yandex avatar URL only when the user has a real photo."""
    if profile.get("is_avatar_empty"):
        return None
    avatar_id = profile.get("default_avatar_id")
    if not isinstance(avatar_id, (str, int)) or not str(avatar_id).strip():
        return None
    return f"https://avatars.yandex.net/get-yapic/{quote(str(avatar_id), safe='')}/islands-200"


def _get_yandex_display_name(profile: dict) -> str | None:
    """Use the profile name supplied by Yandex, never derive one from email."""
    for field in ("display_name", "real_name", "first_name", "login"):
        value = profile.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return None


def _require_yandex_configuration() -> None:
    if not YANDEX_CLIENT_ID or not YANDEX_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Вход через Яндекс пока не настроен.",
        )


@router.get("/login")
async def yandex_login(request: Request):
    """Start an authorization-code OAuth flow with a CSRF-protected state."""
    _require_yandex_configuration()
    require_pending_legal_consent(request)
    state = secrets.token_urlsafe(32)
    request.session["yandex_oauth_state"] = state
    params = {
        "client_id": YANDEX_CLIENT_ID,
        "redirect_uri": YANDEX_REDIRECT_URI,
        "response_type": "code",
        "scope": "login:email login:avatar login:info",
        "state": state,
        "force_confirm": "yes",
    }
    return RedirectResponse(url=f"{YANDEX_AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
async def yandex_auth_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        db: Session = Depends(get_db),
):
    """Exchange the Yandex authorization code and create or sign in a user."""
    _require_yandex_configuration()
    require_pending_legal_consent(request)
    expected_state = request.session.pop("yandex_oauth_state", None)
    if not (
        isinstance(expected_state, str)
        and isinstance(state, str)
        and secrets.compare_digest(expected_state, state)
    ):
        raise HTTPException(status_code=400, detail="Недействительный запрос авторизации Яндекс ID.")
    if not code:
        raise HTTPException(status_code=400, detail="Яндекс ID не вернул код авторизации.")

    try:
        async with httpx.AsyncClient(timeout=OAUTH_TIMEOUT_SECONDS) as client:
            token_response = await client.post(
                YANDEX_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": YANDEX_CLIENT_ID,
                    "client_secret": YANDEX_CLIENT_SECRET,
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(status_code=502, detail="Яндекс ID вернул неполный ответ.")

            profile_response = await client.get(
                YANDEX_USERINFO_URL,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("Yandex ID OAuth request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Яндекс ID временно недоступен. Попробуйте ещё раз.") from error

    email = profile.get("default_email") if isinstance(profile, dict) else None
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Яндекс ID не передал email. Разрешите доступ к email и повторите вход.",
        )
    email = email.strip().lower()
    avatar_url = _get_yandex_avatar_url(profile)
    display_name = _get_yandex_display_name(profile)
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=get_hash_password(secrets.token_urlsafe(32)),
            is_active=True,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        initialise_new_user_entitlements(db, user.id, user.email)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="Этот аккаунт отключён.")
    else:
        profile_changed = False
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            profile_changed = True
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            profile_changed = True
        if profile_changed:
            db.commit()

    if persist_legal_consent(db, user):
        db.commit()

    refresh_token = create_refresh_session(db, user)
    # Do not put bearer credentials into the redirect URL or browser storage.
    # The front end obtains a short-lived access token from the HttpOnly refresh
    # cookie after this redirect.
    response = RedirectResponse(url=f"{FRONTEND_URL}/")
    set_refresh_token_cookie(response, refresh_token)
    return response
