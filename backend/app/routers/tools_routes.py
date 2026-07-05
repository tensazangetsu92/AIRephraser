# app/routers/tools_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import HumanizeRequest, DetectRequest, ParaphraseRequest
from app.database import get_db, User
from auth import get_current_user
from llm import humanize_pipeline, detect_ai_pipeline, paraphrase_pipeline
from app.subscription import check_usage_limit, increment_usage

router = APIRouter(tags=["tools"])


@router.post("/humanize")
async def humanize(
        req: HumanizeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    check_usage_limit(db, current_user.id, req.text)

    result = await humanize_pipeline(
        req.text,
        req.intensity,
        req.tone,
        req.style,
        req.length,
        req.target_language
    )

    word_count = len(req.text.strip().split())
    increment_usage(db, current_user.id, word_count)

    return {"success": True, "result": result}


@router.post("/detect")
async def detect(
        req: DetectRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    check_usage_limit(db, current_user.id, req.text)

    result = await detect_ai_pipeline(req.text)

    word_count = len(req.text.strip().split())
    increment_usage(db, current_user.id, word_count)

    return {"success": True, "result": result}


@router.post("/paraphrase")
async def paraphrase(
        req: ParaphraseRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    check_usage_limit(db, current_user.id, req.text)

    result = await paraphrase_pipeline(req.text, req.style, req.tone)

    word_count = len(req.text.strip().split())
    increment_usage(db, current_user.id, word_count)

    return {"success": True, "result": result}