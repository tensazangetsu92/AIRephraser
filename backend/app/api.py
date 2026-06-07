# app/api.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, HTMLResponse
from datetime import timedelta, datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from pathlib import Path

from starlette.responses import RedirectResponse

from app.models import UserLogin, UserRegister, Token, HumanizeRequest, SubscriptionCreate
from app.config import FRONTEND_PATH, FRONTEND_DIR
from app.database import get_db, create_tables, User
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_user_by_email, get_hash_password, pending_users
)
from llm import humanize_pipeline
from app.subscription import (
    get_user_subscription,
    upgrade_subscription,
    get_usage_stats,
    check_usage_limit,
    increment_usage,
    SUBSCRIPTION_PLANS
)
from app.email_utils import verify_code
from auth import create_pending_user, verify_and_create_user

router = APIRouter()

create_tables()


templates_dir = Path(__file__).parent.parent.parent / "frontend" / "html"
templates = Jinja2Templates(directory=str(templates_dir))

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="humanizer.html"
    )

@router.get("/humanizer")
async def humanizer_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="humanizer.html"
    )

@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pricing.html"
    )

@router.get("/detector", response_class=HTMLResponse)
async def detector(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="detector.html"
    )

@router.get("/paraphraser", response_class=HTMLResponse)
async def paraphraser(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="paraphraser.html"
    )

@router.get("/grammar", response_class=HTMLResponse)
async def grammar(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="grammar.html"
    )


@router.post("/register", response_model=dict)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        user = create_user(db, user_data.email, user_data.password)
        return {
            "success": True,
            "message": "Пользователь успешно зарегистрирован",
            "user": {"email": user.email}
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при регистрации: {str(e)}")


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    access_token = create_access_token(data={"sub": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"email": user.email, "id": user.id}
    )


@router.post("/humanize")
async def humanize(
        req: HumanizeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем лимиты (передаём текст целиком)
    check_usage_limit(db, current_user.id, req.text)

    # Обработка текста
    result = await humanize_pipeline(
        req.text,
        req.intensity,
        req.tone,
        req.style,
        req.length,
        req.target_language
    )

    # Увеличиваем счётчик (передаём количество слов)
    word_count = len(req.text.strip().split())
    increment_usage(db, current_user.id, word_count)

    return {"success": True, "result": result}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "success": True,
        "user": {
            "email": current_user.email,
            "id": current_user.id
        }
    }


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получить информацию о подписке пользователя"""
    subscription = get_user_subscription(db, current_user.id)
    usage_stats = get_usage_stats(db, current_user.id)

    return {
        "success": True,
        "subscription": {
            "id": subscription.id,
            "plan_type": subscription.plan_type,
            "is_active": subscription.is_active,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "total_requests": subscription.total_requests,
            "max_words": subscription.max_words
        },
        "usage": usage_stats,
        "available_plans": SUBSCRIPTION_PLANS
    }


@router.post("/subscription/upgrade")
async def upgrade_subscription_endpoint(
        plan_data: SubscriptionCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    subscription = upgrade_subscription(
        db,
        current_user.id,
        plan_data.plan_type,
        payment_id=f"test_payment_{datetime.now().timestamp()}"
    )

    return {
        "success": True,
        "message": f"Subscription upgraded to {plan_data.plan_type}",
        "subscription": {
            "plan_type": subscription.plan_type,
            "end_date": subscription.end_date,
            "total_requests": subscription.total_requests,
            "max_words": subscription.max_words
        }
    }


@router.get("/subscription/plans")
async def get_subscription_plans():
    """Получить список доступных планов подписки"""
    return {
        "success": True,
        "plans": SUBSCRIPTION_PLANS
    }


@router.post("/auth/send-verification")
async def send_verification(user_data: UserRegister, db: Session = Depends(get_db)):
    """Отправляет код подтверждения на email"""
    try:
        # Проверяем, не зарегистрирован ли уже пользователь
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        # Хешируем пароль
        hashed_password = get_hash_password(user_data.password)

        # Отправляем код подтверждения
        code = create_pending_user(user_data.email, hashed_password)

        return {
            "success": True,
            "message": f"Код подтверждения отправлен на {user_data.email}",
            "email": user_data.email
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/auth/verify-code")
async def verify_registration_code(data: dict, db: Session = Depends(get_db)):
    """Подтверждает код и завершает регистрацию"""
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        raise HTTPException(status_code=400, detail="Email и код обязательны")

    if email not in pending_users:
        raise HTTPException(status_code=400, detail="Код не найден. Запросите новый код")

    pending = pending_users[email]

    if datetime.now() > pending["expires_at"]:
        del pending_users[email]
        raise HTTPException(status_code=400, detail="Код подтверждения истек. Запросите новый")

    if pending["verification_code"] != code:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже зарегистрирован")

    db_user = User(
        email=email,
        password_hash=pending["password_hash"],
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    del pending_users[email]

    from app.subscription import get_user_subscription
    get_user_subscription(db, db_user.id)

    access_token = create_access_token(data={"sub": db_user.email})

    return {
        "success": True,
        "message": "Регистрация успешно завершена",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": db_user.email, "id": db_user.id}
    }