# app/routers/user_routes.py
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import (
    EmailLoginCode,
    get_db,
    PasswordResetCode,
    StudyWorkTrial,
    Subscription,
    UsageStats,
    User,
    UserHistory,
    UserProcessingLock,
    UserRefreshSession,
    WordTransaction,
)
from app.account_deletion import record_deleted_account_marker
from auth import (
    clear_refresh_token_cookie,
    create_access_token,
    create_refresh_session,
    get_current_user,
    get_hash_password,
    revoke_all_refresh_sessions,
    set_refresh_token_cookie,
    verify_password,
)
from app.subscription import check_subscription_expired

router = APIRouter(tags=["user"])
logger = logging.getLogger("uvicorn.error")
AVAILABLE_HISTORY_TOOL_TYPES = ("study_work", "humanizer", "detector", "paraphraser")
HISTORY_PREVIEW_CHARS = 300
HISTORY_PROCESSING_OPTION_VALUES = {
    "humanizer": {
        "style": {"human", "literary", "academic"},
        "target_language": {"ru", "en"},
    },
    "paraphraser": {
        "style": {"synonyms", "simple", "academic"},
    },
    "study_work": {
        "work_type": {"report", "essay", "presentation", "coursework", "other"},
    },
    "detector": {},
}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class DeleteHistoryRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=32)


def normalize_history_processing_options(tool_type: str, raw_options: object) -> dict[str, str]:
    """Keep only known, valid UI options in history metadata."""
    if not isinstance(raw_options, dict):
        return {}

    allowed_options = HISTORY_PROCESSING_OPTION_VALUES.get(tool_type, {})
    return {
        key: value
        for key, allowed_values in allowed_options.items()
        if isinstance((value := raw_options.get(key)), str) and value in allowed_values
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получение информации о текущем пользователе"""
    check_subscription_expired(db, current_user.id)

    return {
        "success": True,
        "user": {
            "email": current_user.email,
            "id": current_user.id,
            "display_name": current_user.display_name,
            "avatar_url": current_user.avatar_url,
        }
    }


@router.get("/user/history")
async def get_user_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=50),
        type: Literal["all", "humanizer", "detector", "paraphraser", "study_work"] = "all",
        date: Literal["all", "today", "week", "month"] = "all",
):
    query = db.query(UserHistory).filter(
        UserHistory.user_id == current_user.id,
        UserHistory.tool_type.in_(AVAILABLE_HISTORY_TOOL_TYPES),
    )

    # Фильтр по типу
    if type != "all":
        query = query.filter(UserHistory.tool_type == type)

    # Фильтр по дате
    if date == "today":
        today = func.current_date()
        query = query.filter(
            UserHistory.created_at >= today,
            UserHistory.created_at < today + timedelta(days=1),
        )
    elif date == "week":
        query = query.filter(UserHistory.created_at >= func.now() - timedelta(days=7))
    elif date == "month":
        query = query.filter(UserHistory.created_at >= func.now() - timedelta(days=30))

    total = query.count()
    total_pages = (total + limit - 1) // limit
    offset = (page - 1) * limit

    history = (
        query.with_entities(
            UserHistory.id,
            UserHistory.tool_type,
            UserHistory.created_at,
            func.substr(UserHistory.original_text, 1, HISTORY_PREVIEW_CHARS).label("original_preview"),
            func.substr(UserHistory.result_text, 1, HISTORY_PREVIEW_CHARS).label("result_preview"),
            (func.length(UserHistory.original_text) > HISTORY_PREVIEW_CHARS).label("original_is_truncated"),
            (func.length(UserHistory.result_text) > HISTORY_PREVIEW_CHARS).label("result_is_truncated"),
        )
        .order_by(UserHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "tool_type": h.tool_type,
                "original_preview": h.original_preview,
                "result_preview": h.result_preview,
                "original_is_truncated": bool(h.original_is_truncated),
                "result_is_truncated": bool(h.result_is_truncated),
                "created_at": h.created_at.isoformat()
            } for h in history
        ],
        "total": total,
        "page": page,
        "total_pages": total_pages
    }


async def change_password(
        data: ChangePasswordRequest,
        response: Response,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="Новый пароль должен отличаться от текущего")
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")

    current_user.password_hash = get_hash_password(data.new_password)
    revoke_all_refresh_sessions(db, current_user.id)
    set_refresh_token_cookie(response, create_refresh_session(db, current_user))
    return {
        "success": True,
        "access_token": create_access_token(data={"sub": current_user.email}),
        "token_type": "bearer",
    }


@router.delete("/user/delete")
async def delete_user_account(
        data: dict,
        response: Response,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Delete account data and retain only a finite anti-abuse email HMAC."""
    if data.get("confirmation") != "DELETE":
        raise HTTPException(status_code=400, detail="Введите DELETE для подтверждения удаления.")

    active_processing = db.query(UserProcessingLock.user_id).filter(
        UserProcessingLock.user_id == current_user.id,
        UserProcessingLock.expires_at > datetime.now(timezone.utc),
    ).first()
    if active_processing:
        raise HTTPException(
            status_code=409,
            detail="Дождитесь завершения обработки текста, затем удалите аккаунт.",
        )

    user_id = current_user.id
    email = current_user.email
    try:
        # Remove dependent records explicitly: existing database tables do not
        # use ON DELETE CASCADE, and account deletion must not leave text,
        # documents, sessions, reset codes, or word-accounting records behind.
        db.query(PasswordResetCode).filter(PasswordResetCode.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailLoginCode).filter(EmailLoginCode.email == email).delete(synchronize_session=False)
        db.query(UserRefreshSession).filter(UserRefreshSession.user_id == user_id).delete(synchronize_session=False)
        db.query(UserProcessingLock).filter(UserProcessingLock.user_id == user_id).delete(synchronize_session=False)
        db.query(StudyWorkTrial).filter(StudyWorkTrial.user_id == user_id).delete(synchronize_session=False)
        db.query(WordTransaction).filter(WordTransaction.user_id == user_id).delete(synchronize_session=False)
        db.query(UsageStats).filter(UsageStats.user_id == user_id).delete(synchronize_session=False)
        db.query(Subscription).filter(Subscription.user_id == user_id).delete(synchronize_session=False)
        db.query(UserHistory).filter(UserHistory.user_id == user_id).delete(synchronize_session=False)
        record_deleted_account_marker(db, email)
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    except Exception as error:
        db.rollback()
        logger.exception("Unable to delete account id=%s", user_id)
        raise HTTPException(status_code=500, detail="Не удалось удалить аккаунт. Попробуйте позже.") from error

    clear_refresh_token_cookie(response)
    return {"success": True}


@router.get("/user/history/{history_id}")
async def get_user_history_item(
        history_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Return one history item only when it belongs to the current user."""
    history = db.query(
        UserHistory.id,
        UserHistory.tool_type,
        UserHistory.original_text,
        UserHistory.result_text,
        UserHistory.processing_options,
        UserHistory.processed_docx_filename,
        UserHistory.created_at,
        UserHistory.processed_docx.isnot(None).label("has_processed_docx"),
    ).filter(
        UserHistory.id == history_id,
        UserHistory.user_id == current_user.id,
        UserHistory.tool_type.in_(AVAILABLE_HISTORY_TOOL_TYPES),
    ).first()
    if not history:
        raise HTTPException(status_code=404, detail="Работа не найдена")

    return {
        "success": True,
        "history": {
            "id": history.id,
            "tool_type": history.tool_type,
            "original_text": history.original_text,
            "result_text": history.result_text,
            "processing_options": history.processing_options or {},
            "has_processed_docx": history.has_processed_docx,
            "processed_docx_filename": history.processed_docx_filename,
            "created_at": history.created_at.isoformat(),
        },
    }


@router.post("/user/history/save")
async def save_to_history(
        data: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Сохраняет результат обработки в историю пользователя"""
    try:
        tool_type = data.get("tool_type", "humanizer")
        if tool_type not in AVAILABLE_HISTORY_TOOL_TYPES:
            raise HTTPException(status_code=400, detail="Неизвестный инструмент истории")
        processing_options = normalize_history_processing_options(
            tool_type,
            data.get("processing_options"),
        )
        history = UserHistory(
            user_id=current_user.id,
            tool_type=tool_type,
            original_text=data.get("original_text", ""),
            result_text=data.get("result_text", ""),
            processing_options=processing_options,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return {"success": True, "message": "Сохранено в историю", "history_id": history.id}
    except Exception:
        logger.exception("Unable to save history entry")
        raise HTTPException(status_code=500, detail="Ошибка сохранения в историю")


@router.delete("/user/history/clear")
async def clear_user_history(
        data: DeleteHistoryRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if data.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="Введите DELETE для подтверждения очистки истории.")
    db.query(UserHistory).filter(UserHistory.user_id == current_user.id).delete()
    db.commit()
    return {"success": True, "message": "История очищена"}


@router.delete("/user/history/cleanup-old")
async def cleanup_old_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        days: int = 90
):
    """Удаляет историю пользователя старше N дней (доступно только админу)"""
    from app.database import delete_old_history

    if current_user.email != "admin@humary.com":
        raise HTTPException(status_code=403, detail="Доступ только для администратора")

    deleted = delete_old_history(db, days)
    return {"success": True, "deleted": deleted, "days": days}

