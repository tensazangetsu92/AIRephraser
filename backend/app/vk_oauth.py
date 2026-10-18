"""VK ID OAuth 2.1 login with PKCE for the web application."""

import base64
import hashlib
import logging
import os
import secrets
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import FRONTEND_URL, VK_ID_APP_ID, VK_ID_REDIRECT_URI
from app.database import OAuthIdentity, User, get_db
from app.subscription import initialise_new_user_entitlements
from app.legal_consent import persist_legal_consent, require_pending_legal_consent
from auth import (
    create_refresh_session,
    get_hash_password,
    set_refresh_token_cookie,
)


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/auth/vk", tags=["vk-id-auth"])

VK_ID_BASE_URL = "https://id.vk.ru"
VK_ID_AUTHORIZE_URL = f"{VK_ID_BASE_URL}/authorize"
VK_ID_TOKEN_URL = f"{VK_ID_BASE_URL}/oauth2/auth"
VK_ID_USERINFO_URL = f"{VK_ID_BASE_URL}/oauth2/user_info"
OAUTH_TIMEOUT_SECONDS = 15.0


def _get_vk_avatar_url(profile: dict) -> str | None:
    """Read a VK ID profile image without accepting non-HTTPS URLs."""
    for field in ("avatar", "photo_200", "photo_100", "photo"):
        value = profile.get(field)
        if isinstance(value, dict):
            value = value.get("url")
        if not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if parsed.scheme == "https" and parsed.netloc:
            return value
    return None


def _get_vk_display_name(profile: dict) -> str | None:
    """Use the display name supplied by VK ID, never derive one from email."""
    for field in ("name", "display_name", "nickname", "screen_name"):
        value = profile.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]

    name_parts = []
    for field in ("first_name", "last_name"):
        value = profile.get(field)
        if isinstance(value, str) and value.strip():
            name_parts.append(value.strip())
    return " ".join(name_parts)[:255] or None


def _require_vk_configuration() -> None:
    if not VK_ID_APP_ID:
        raise HTTPException(status_code=503, detail="Вход через VK ID пока не настроен.")


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@router.get("/login")
async def vk_login(request: Request):
    """Start VK ID OAuth 2.1 authorization code flow with PKCE."""
    _require_vk_configuration()
    require_pending_legal_consent(request)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    request.session["vk_oauth_state"] = state
    request.session["vk_oauth_verifier"] = verifier
    params = {
        "client_id": VK_ID_APP_ID,
        "redirect_uri": VK_ID_REDIRECT_URI,
        "response_type": "code",
        # VK ID's current web SDK requests both basic contact scopes.  Some
        # accounts do not return the email field when only `email` is passed.
        "scope": "phone email",
        "state": state,
        "code_challenge": _code_challenge(verifier),
        # VK ID expects the lowercase literal used by its OAuth 2.1 SDK.
        "code_challenge_method": "s256",
        # Require VK ID to show the consent screen for contact data.  Without
        # it an already-authorized account may return a partial profile.
        "prompt": "login consent",
    }
    return RedirectResponse(url=f"{VK_ID_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
async def vk_auth_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        device_id: str | None = None,
        db: Session = Depends(get_db),
):
    """Exchange a VK ID code for a token and sign the user in by verified email."""
    _require_vk_configuration()
    require_pending_legal_consent(request)
    expected_state = request.session.pop("vk_oauth_state", None)
    verifier = request.session.pop("vk_oauth_verifier", None)
    if not (
        isinstance(expected_state, str)
        and isinstance(state, str)
        and secrets.compare_digest(expected_state, state)
        and isinstance(verifier, str)
    ):
        raise HTTPException(status_code=400, detail="Недействительный запрос авторизации VK ID.")
    if not code or not device_id:
        raise HTTPException(status_code=400, detail="VK ID вернул неполный ответ авторизации.")

    token_params = {
        "grant_type": "authorization_code",
        "redirect_uri": VK_ID_REDIRECT_URI,
        "client_id": VK_ID_APP_ID,
        "code_verifier": verifier,
        "state": state,
        "device_id": device_id,
    }
    try:
        async with httpx.AsyncClient(timeout=OAUTH_TIMEOUT_SECONDS) as client:
            token_response = await client.post(
                VK_ID_TOKEN_URL,
                params=token_params,
                data={"code": code},
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get("access_token") if isinstance(token_data, dict) else None
            returned_state = token_data.get("state") if isinstance(token_data, dict) else None
            if not (
                isinstance(access_token, str)
                and access_token
                and isinstance(returned_state, str)
                and secrets.compare_digest(state, returned_state)
            ):
                raise HTTPException(status_code=502, detail="VK ID вернул неполный ответ.")

            profile_response = await client.post(
                VK_ID_USERINFO_URL,
                params={"client_id": VK_ID_APP_ID},
                data={"access_token": access_token},
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("VK ID OAuth request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="VK ID временно недоступен. Попробуйте ещё раз.") from error

    profile = profile_data.get("user") if isinstance(profile_data, dict) else None
    provider_user_id = profile.get("user_id") if isinstance(profile, dict) else None
    if isinstance(provider_user_id, int):
        provider_user_id = str(provider_user_id)
    if not isinstance(provider_user_id, str) or not provider_user_id.strip():
        raise HTTPException(status_code=502, detail="VK ID не вернул идентификатор аккаунта. Попробуйте ещё раз.")
    provider_user_id = provider_user_id.strip()

    email = profile.get("email") if isinstance(profile, dict) else None
    email = email.strip().lower() if isinstance(email, str) and email.strip() else None
    avatar_url = _get_vk_avatar_url(profile)
    display_name = _get_vk_display_name(profile)

    identity = db.query(OAuthIdentity).filter(
        OAuthIdentity.provider == "vk",
        OAuthIdentity.provider_subject == provider_user_id,
    ).first()
    created_user = False
    if identity:
        user = identity.user
    else:
        user = db.query(User).filter(func.lower(User.email) == email).first() if email else None
        if user is None:
            user = User(
                email=email,
                password_hash=get_hash_password(secrets.token_urlsafe(32)),
                is_active=True,
                display_name=display_name,
                avatar_url=avatar_url,
            )
            db.add(user)
            db.flush()
            created_user = True
        db.add(OAuthIdentity(provider="vk", provider_subject=provider_user_id, user_id=user.id))
        db.commit()
        db.refresh(user)
        if created_user:
            initialise_new_user_entitlements(db, user.id, email or f"vk:{provider_user_id}")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Этот аккаунт отключён.")

    profile_changed = False
    if email and not user.email:
        email_owner = db.query(User).filter(func.lower(User.email) == email).first()
        if email_owner is None:
            user.email = email
            profile_changed = True
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
