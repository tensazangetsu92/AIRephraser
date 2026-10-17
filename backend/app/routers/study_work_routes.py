import io
import logging
import re
from copy import deepcopy
from time import perf_counter
from urllib.parse import quote

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import User, UserHistory, get_db
from app.models import HumanizeRequest, StudyWorkDownloadRequest
from app.processing_lock import user_processing_guard
from app.rate_limit import enforce_processing_rate_limit
from app.upload_validation import (
    DOCX_MEDIA_TYPE,
    MAX_DOCX_SIZE_BYTES,
    read_upload_limited,
    validate_docx_upload,
)
from app.subscription import (
    check_usage_limit,
    check_study_work_request_limit,
    complete_study_work_trial,
    count_words,
    charge_words,
    release_study_work_trial,
    reserve_study_work_trial,
)
from auth import get_current_user
from llm import (
    LLMProcessingError,
    LLMProviderUnavailableError,
    LLMTimeoutError,
    humanize_docx_paragraphs,
    humanize_study_work_text_pipeline,
    normalize_docx_replacement,
)

router = APIRouter(tags=["study-work"])
logger = logging.getLogger("uvicorn.error")


def processed_docx_filename(source_filename: str | None = None) -> str:
    """Return a safe, user-facing name for a processed Word document."""
    source = re.sub(r"^.*[\\/]", "", source_filename or "").strip()
    source = re.sub(r'[\r\n\\/:*?"<>|]+', "_", source).strip(". ")
    if source.lower().endswith(".docx"):
        source = source[:-5]
    return f"humary-{source or 'учебная-работа'}.docx"


def docx_attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}

def raise_llm_error(error: Exception) -> None:
    if isinstance(error, LLMTimeoutError):
        raise HTTPException(status_code=504, detail="Нейросеть не ответила за 60 секунд. Попробуйте ещё раз.")
    if isinstance(error, LLMProviderUnavailableError):
        raise HTTPException(status_code=502, detail="Нейросеть временно недоступна. Попробуйте ещё раз немного позже.")
    raise HTTPException(status_code=500, detail="Ошибка при обработке.")


def ensure_text_not_empty(text: str) -> None:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="В документе не найден текст для обработки.")


def reserve_study_work_trial_if_available(db: Session, user_id: int) -> bool:
    """Use the one-time registration trial first, otherwise charge the word balance."""
    return reserve_study_work_trial(db, user_id)


def is_editable_docx_paragraph(paragraph) -> bool:
    if not paragraph.text.strip():
        return False
    # Replacing a paragraph clears all of its runs. A drawing may share a
    # paragraph with ordinary text, so clearing it would remove the image or
    # embedded object from the resulting Word file. Keep those paragraphs
    # entirely unchanged.
    paragraph_xml = paragraph._p.xml
    if any(marker in paragraph_xml for marker in ("<w:drawing", "<w:pict", "<w:object")):
        return False
    style_name = (getattr(paragraph.style, "name", "") or "").lower()
    protected_style_parts = ("heading", "title", "заголов", "подзаголов", "название", "toc")
    if any(part in style_name for part in protected_style_parts):
        return False
    if paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER:
        return False

    content_runs = [run for run in paragraph.runs if run.text.strip()]
    if not content_runs:
        return False

    # A single rewritten run cannot safely retain several different character
    # formats. Keep such paragraphs unchanged rather than changing their font,
    # size, colour/theme, boldness, or italics.
    format_signatures = {
        str(run._r.rPr.xml) if run._r.rPr is not None else ""
        for run in content_runs
    }
    if len(format_signatures) > 1:
        return False

    # Manually formatted headings often use the Normal style, so style-name
    # detection alone cannot protect them.
    return not all(run.bold is True for run in content_runs)


def is_bibliography_heading(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip().casefold().rstrip(".:")
    headings = (
        "список использованных источников",
        "список литературы",
        "библиографический список",
        "references",
        "bibliography",
    )
    return normalized in headings


def is_numbered_docx_paragraph(paragraph) -> bool:
    if re.match(r"^\s*(?:\d+|[IVXLCDM]+)[.)]\s+", paragraph.text, flags=re.IGNORECASE):
        return True
    paragraph_properties = getattr(paragraph._p, "pPr", None)
    return bool(paragraph_properties is not None and paragraph_properties.numPr is not None)


def has_bibliography_markers(text: str) -> bool:
    normalized = text.casefold()
    return (
        "http://" in normalized
        or "https://" in normalized
        or "doi:" in normalized
        or "doi.org/" in normalized
        or "дата обращения" in normalized
        or "retrieved" in normalized
        or "accessed" in normalized
    )


def find_bibliography_start(paragraphs: list) -> int | None:
    for index, paragraph in enumerate(paragraphs):
        if is_bibliography_heading(paragraph.text):
            return index
    for index in range(len(paragraphs) - 1):
        current, following = paragraphs[index], paragraphs[index + 1]
        if not (is_numbered_docx_paragraph(current) and is_numbered_docx_paragraph(following)):
            continue
        if has_bibliography_markers(current.text) or has_bibliography_markers(following.text):
            return index
    return None


def get_editable_docx_paragraphs(document) -> list:
    paragraphs = document.paragraphs
    bibliography_start = find_bibliography_start(paragraphs)
    return [
        paragraph
        for index, paragraph in enumerate(paragraphs)
        if (bibliography_start is None or index < bibliography_start)
        and is_editable_docx_paragraph(paragraph)
    ]


def replace_docx_paragraph_text(paragraph, replacement: str) -> None:
    # Some documents simulate a first-line indent with tabs or non-breaking
    # spaces in the text rather than with paragraph formatting. The model does
    # not return those characters, so restore them after rewriting.
    leading_indent_match = re.match(r"^[\t \u00a0]+", paragraph.text)
    leading_indent = leading_indent_match.group(0) if leading_indent_match else ""
    replacement = leading_indent + replacement.lstrip("\t \u00a0")

    # Retain direct character formatting (font, size, color/theme) from the
    # main body run. It is normally the longest run, unlike a short heading
    # fragment that can appear at the start of the same paragraph.
    styled_runs = [
        run for run in paragraph.runs
        if run.text.strip() and run._r.rPr is not None
    ]
    source_properties = None
    if styled_runs:
        source_run = max(styled_runs, key=lambda run: len(run.text.strip()))
        source_properties = deepcopy(source_run._r.rPr)

    # paragraph.clear() preserves paragraph-level formatting such as alignment,
    # indentation, spacing, and paragraph style.
    paragraph.clear()
    new_run = paragraph.add_run(replacement)
    if source_properties is not None:
        new_run._r.insert(0, source_properties)


@router.post("/study-work/process")
async def process_study_work(
        req: HumanizeRequest,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    ensure_text_not_empty(req.text)
    enforce_processing_rate_limit(db, request, user_id=current_user.id, is_study_work=True)
    async with user_processing_guard(db, current_user.id):
        word_count = count_words(req.text)
        study_work_limit = check_study_work_request_limit(db, current_user.id, req.text)
        uses_trial = reserve_study_work_trial_if_available(db, current_user.id)
        if not uses_trial:
            check_usage_limit(db, current_user.id, req.text, max_words_override=study_work_limit)

        started_at = perf_counter()
        try:
            result = await humanize_study_work_text_pipeline(
                req.text, req.target_language,
                req.academic_work_type,
            )
        except (LLMTimeoutError, LLMProcessingError) as error:
            if uses_trial:
                release_study_work_trial(db, current_user.id)
            raise_llm_error(error)
        except Exception:
            if uses_trial:
                release_study_work_trial(db, current_user.id)
            raise

        if uses_trial:
            complete_study_work_trial(db, current_user.id)
        else:
            charge_words(
                db,
                current_user.id,
                word_count,
                reason="processing:study_work",
                max_words_override=study_work_limit,
            )
        logger.info("study_work: %s words processed in %.2f seconds", word_count, perf_counter() - started_at)
        return {"success": True, "result": result, "used_free_trial": uses_trial}


@router.post("/study-work/docx/download")
async def download_study_work_docx(
        req: StudyWorkDownloadRequest,
        current_user: User = Depends(get_current_user),
):
    """Create a DOCX download for text submitted directly in the editor."""
    ensure_text_not_empty(req.text)
    document = Document()
    for paragraph_text in re.split(r"\r?\n", req.text):
        document.add_paragraph(paragraph_text)

    output = io.BytesIO()
    document.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type=DOCX_MEDIA_TYPE,
        headers=docx_attachment_headers(processed_docx_filename()),
    )


@router.post("/study-work/docx/process")
async def process_study_work_docx(
        request: Request,
        file: UploadFile = File(...),
        work_type: str = Form("other"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    filename = file.filename or ""
    content_type = file.content_type
    document_bytes = await read_upload_limited(file, MAX_DOCX_SIZE_BYTES)
    validate_docx_upload(
        filename=filename,
        content_type=content_type,
        document_bytes=document_bytes,
    )
    try:
        document = Document(io.BytesIO(document_bytes))
    except Exception as error:
        logger.warning("Unable to open uploaded DOCX: %s", error)
        raise HTTPException(status_code=400, detail="Не удалось открыть файл Word.")

    output_filename = processed_docx_filename(filename)
    editable_paragraphs = get_editable_docx_paragraphs(document)
    source_text = "\n\n".join(paragraph.text for paragraph in editable_paragraphs)
    ensure_text_not_empty(source_text)
    enforce_processing_rate_limit(db, request, user_id=current_user.id, is_study_work=True)
    async with user_processing_guard(db, current_user.id):
        word_count = count_words(source_text)
        study_work_limit = check_study_work_request_limit(db, current_user.id, source_text)
        uses_trial = reserve_study_work_trial_if_available(db, current_user.id)
        if not uses_trial:
            check_usage_limit(db, current_user.id, source_text, max_words_override=study_work_limit)
        started_at = perf_counter()
        items = [{"id": f"p{index}", "text": paragraph.text} for index, paragraph in enumerate(editable_paragraphs)]
        try:
            replacements = await humanize_docx_paragraphs(items, work_type)
        except (LLMTimeoutError, LLMProcessingError) as error:
            if uses_trial:
                release_study_work_trial(db, current_user.id)
            raise_llm_error(error)
        except Exception:
            if uses_trial:
                release_study_work_trial(db, current_user.id)
            raise

        for item, paragraph in zip(items, editable_paragraphs):
            replacement = normalize_docx_replacement(paragraph.text, replacements[item["id"]])
            replace_docx_paragraph_text(paragraph, replacement)

        output = io.BytesIO()
        document.save(output)
        processed_docx = output.getvalue()
        result_text = "\n\n".join(paragraph.text for paragraph in editable_paragraphs)

        if uses_trial:
            complete_study_work_trial(db, current_user.id)
        else:
            charge_words(
                db,
                current_user.id,
                word_count,
                reason="processing:study_work_docx",
                max_words_override=study_work_limit,
            )

        history = UserHistory(
            user_id=current_user.id,
            tool_type="study_work",
            original_text=source_text,
            result_text=result_text,
            processing_options={"work_type": work_type},
            processed_docx=processed_docx,
            processed_docx_filename=output_filename,
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        logger.info("study_work_docx: %s words processed in %.2f seconds", word_count, perf_counter() - started_at)
        return StreamingResponse(
            io.BytesIO(processed_docx),
            media_type=DOCX_MEDIA_TYPE,
            headers={**docx_attachment_headers(output_filename), "X-History-Id": str(history.id)},
        )


@router.get("/study-work/history/{history_id}/docx/download")
async def download_study_work_history_docx(
        history_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Download the exact formatted DOCX stored for a Study Work history item."""
    history = db.query(UserHistory).filter(
        UserHistory.id == history_id,
        UserHistory.user_id == current_user.id,
        UserHistory.tool_type == "study_work",
    ).first()
    if not history or not history.processed_docx:
        raise HTTPException(status_code=404, detail="Файл Word для этой работы не найден.")

    return StreamingResponse(
        io.BytesIO(history.processed_docx),
        media_type=DOCX_MEDIA_TYPE,
        headers=docx_attachment_headers(history.processed_docx_filename or processed_docx_filename()),
    )
