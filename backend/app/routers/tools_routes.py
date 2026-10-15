import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import User, get_db
from app.models import DetectRequest, HumanizeRequest, ParaphraseRequest
from app.processing_lock import user_processing_guard
from app.rate_limit import enforce_processing_rate_limit
from app.subscription import charge_words, check_usage_limit, count_words
from auth import get_current_user
from llm import (
    LLMProcessingError,
    LLMProviderUnavailableError,
    LLMTimeoutError,
    detect_ai_pipeline,
    humanize_pipeline,
    paraphrase_pipeline,
)

router = APIRouter(tags=["tools"])
logger = logging.getLogger("uvicorn.error")


def log_processing_time(tool_name: str, word_count: int, started_at: float) -> None:
    logger.info("%s: %s words processed in %.2f seconds", tool_name, word_count, perf_counter() - started_at)


def raise_llm_error(error: Exception) -> None:
    if isinstance(error, LLMTimeoutError):
        raise HTTPException(status_code=504, detail="Нейросеть не ответила за 60 секунд. Попробуйте ещё раз.")
    if isinstance(error, LLMProviderUnavailableError):
        raise HTTPException(status_code=502, detail="Нейросеть временно недоступна. Попробуйте ещё раз немного позже.")
    raise HTTPException(status_code=500, detail="Ошибка при обработке.")


def ensure_text_not_empty(text: str) -> None:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Вставьте текст для обработки.")


async def _process_as_user(
        *,
        request: Request,
        db: Session,
        current_user: User,
        text: str,
        tool_name: str,
        pipeline,
):
    word_count = count_words(text)
    started_at = perf_counter()
    enforce_processing_rate_limit(db, request, user_id=current_user.id)
    async with user_processing_guard(db, current_user.id):
        check_usage_limit(db, current_user.id, text)
        result = await pipeline()
        charge_words(db, current_user.id, word_count, reason=f"processing:{tool_name}")
    log_processing_time(tool_name, word_count, started_at)
    return {"success": True, "result": result}


@router.post("/humanize")
async def humanize(
        req: HumanizeRequest,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    ensure_text_not_empty(req.text)
    try:
        return await _process_as_user(
            request=request,
            db=db,
            current_user=current_user,
            text=req.text,
            tool_name="humanize",
            pipeline=lambda: humanize_pipeline(req.text, req.style, req.target_language, req.academic_work_type),
        )
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)


@router.post("/detect")
async def detect(
        req: DetectRequest,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    ensure_text_not_empty(req.text)
    try:
        return await _process_as_user(
            request=request,
            db=db,
            current_user=current_user,
            text=req.text,
            tool_name="detector",
            pipeline=lambda: detect_ai_pipeline(req.text),
        )
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)


@router.post("/paraphrase")
async def paraphrase(
        req: ParaphraseRequest,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    ensure_text_not_empty(req.text)
    try:
        return await _process_as_user(
            request=request,
            db=db,
            current_user=current_user,
            text=req.text,
            tool_name="paraphraser",
            pipeline=lambda: paraphrase_pipeline(req.text, req.style),
        )
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)
