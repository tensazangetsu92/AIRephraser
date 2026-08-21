import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import User, get_db
from app.models import DetectRequest, GrammarRequest, HumanizeRequest, ParaphraseRequest
from app.subscription import check_usage_limit, count_words, increment_usage
from auth import get_current_user
from llm import LLMProcessingError, LLMTimeoutError, detect_ai_pipeline, grammar_pipeline, humanize_pipeline, paraphrase_pipeline

router = APIRouter(tags=["tools"])
logger = logging.getLogger("uvicorn.error")


def log_processing_time(tool_name: str, word_count: int, started_at: float) -> None:
    logger.info("%s: %s words processed in %.2f seconds", tool_name, word_count, perf_counter() - started_at)


def raise_llm_error(error: Exception) -> None:
    if isinstance(error, LLMTimeoutError):
        raise HTTPException(status_code=504, detail="Нейросеть не ответила за 60 секунд. Попробуйте ещё раз.")
    raise HTTPException(status_code=502, detail="Нейросеть временно недоступна. Попробуйте ещё раз немного позже.")


def ensure_text_not_empty(text: str) -> None:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Вставьте текст для обработки.")


@router.post("/humanize")
async def humanize(req: HumanizeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_text_not_empty(req.text)
    word_count = count_words(req.text)
    check_usage_limit(db, current_user.id, req.text)
    started_at = perf_counter()
    try:
        result = await humanize_pipeline(req.text, req.tone, req.style, req.target_language,
                                         req.academic_work_type, req.preserve_options)
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)
    increment_usage(db, current_user.id, word_count)
    log_processing_time("humanize", word_count, started_at)
    return {"success": True, "result": result}


@router.post("/detect")
async def detect(req: DetectRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_text_not_empty(req.text)
    word_count = count_words(req.text)
    check_usage_limit(db, current_user.id, req.text)
    started_at = perf_counter()
    try:
        result = await detect_ai_pipeline(req.text)
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)
    increment_usage(db, current_user.id, word_count)
    log_processing_time("detect", word_count, started_at)
    return {"success": True, "result": result}


@router.post("/paraphrase")
async def paraphrase(req: ParaphraseRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_text_not_empty(req.text)
    word_count = count_words(req.text)
    check_usage_limit(db, current_user.id, req.text)
    started_at = perf_counter()
    try:
        result = await paraphrase_pipeline(req.text, req.style, req.tone)
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)
    increment_usage(db, current_user.id, word_count)
    log_processing_time("paraphrase", word_count, started_at)
    return {"success": True, "result": result}


@router.post("/grammar")
async def grammar(req: GrammarRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_text_not_empty(req.text)
    word_count = count_words(req.text)
    check_usage_limit(db, current_user.id, req.text)
    started_at = perf_counter()
    try:
        result = await grammar_pipeline(req.text)
    except (LLMTimeoutError, LLMProcessingError) as error:
        raise_llm_error(error)
    increment_usage(db, current_user.id, word_count)
    log_processing_time("grammar", word_count, started_at)
    return {"success": True, "result": result}
