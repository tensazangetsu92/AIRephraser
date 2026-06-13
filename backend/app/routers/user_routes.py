# app/routers/user_routes.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db, User, UserHistory
from auth import get_current_user, verify_password, get_hash_password
from app.subscription import check_subscription_expired

router = APIRouter(tags=["user"])


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Получение информации о текущем пользователе"""
    check_subscription_expired(db, current_user.id)

    return {
        "success": True,
        "user": {
            "email": current_user.email,
            "id": current_user.id
        }
    }


@router.get("/user/history")
async def get_user_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        page: int = 1,
        limit: int = 20,
        type: str = "all",
        date: str = "all"
):
    query = db.query(UserHistory).filter(UserHistory.user_id == current_user.id)

    # Фильтр по типу
    if type != "all" and type != "humanizer":
        query = query.filter(UserHistory.tool_type == type)

    # Фильтр по дате
    if date == "today":
        query = query.filter(func.date(UserHistory.created_at) == func.current_date())
    elif date == "week":
        query = query.filter(UserHistory.created_at >= func.now() - timedelta(days=7))
    elif date == "month":
        query = query.filter(UserHistory.created_at >= func.now() - timedelta(days=30))

    total = query.count()
    total_pages = (total + limit - 1) // limit
    offset = (page - 1) * limit

    history = query.order_by(UserHistory.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "tool_type": h.tool_type,
                "original_text": h.original_text,
                "result_text": h.result_text,
                "created_at": h.created_at.isoformat()
            } for h in history
        ],
        "total": total,
        "page": page,
        "total_pages": total_pages
    }


@router.post("/user/history/save")
async def save_to_history(
        data: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Сохраняет результат обработки в историю пользователя"""
    try:
        history = UserHistory(
            user_id=current_user.id,
            tool_type=data.get("tool_type", "humanizer"),
            original_text=data.get("original_text", ""),
            result_text=data.get("result_text", "")
        )
        db.add(history)
        db.commit()
        return {"success": True, "message": "Сохранено в историю"}
    except Exception as e:
        print(f"Error saving to history: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения в историю")


@router.delete("/user/history/clear")
async def clear_user_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
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


@router.post("/user/change-password")
async def change_password(
        data: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный старый пароль")

    current_user.password_hash = get_hash_password(new_password)
    db.commit()

    return {"success": True, "message": "Пароль изменён"}