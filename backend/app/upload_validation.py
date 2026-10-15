"""Validation for user-provided document uploads before parsing them."""

from __future__ import annotations

import io
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_DOCX_SIZE_BYTES = 10 * 1024 * 1024
# Multipart adds boundaries and regular form fields, so allow a small overhead
# while still rejecting oversized browser requests before multipart parsing.
MAX_DOCX_REQUEST_SIZE_BYTES = MAX_DOCX_SIZE_BYTES + 1024 * 1024
MAX_DOCX_ARCHIVE_ENTRIES = 5_000
MAX_DOCX_UNCOMPRESSED_SIZE_BYTES = 50 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100

_ALLOWED_DOCX_CONTENT_TYPES = {
    DOCX_MEDIA_TYPE,
    "application/octet-stream",
}
_REQUIRED_DOCX_ENTRIES = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
}


async def read_upload_limited(file: UploadFile, max_size_bytes: int) -> bytes:
    """Read an upload in bounded chunks and stop as soon as it exceeds its limit."""
    chunks: list[bytes] = []
    total_size = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size_bytes:
                raise HTTPException(status_code=413, detail="Файл Word больше 10 МБ.")
            chunks.append(chunk)
    finally:
        await file.close()
    return b"".join(chunks)


def validate_docx_upload(
        *,
        filename: str,
        content_type: str | None,
        document_bytes: bytes,
) -> None:
    """Reject non-DOCX archives, damaged containers, and decompression bombs."""
    safe_name = PurePath(filename).name
    if not safe_name.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Загрузите документ Word в формате .docx.")

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().casefold()
    if normalized_content_type and normalized_content_type not in _ALLOWED_DOCX_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла. Загрузите документ Word .docx.")

    if not document_bytes:
        raise HTTPException(status_code=400, detail="Файл Word пустой.")
    if len(document_bytes) > MAX_DOCX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Файл Word больше 10 МБ.")
    if not document_bytes.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Файл не является корректным документом Word .docx.")

    try:
        with ZipFile(io.BytesIO(document_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ARCHIVE_ENTRIES:
                raise HTTPException(status_code=400, detail="В документе Word слишком много внутренних файлов.")

            names = {entry.filename for entry in entries}
            if not _REQUIRED_DOCX_ENTRIES.issubset(names):
                raise HTTPException(status_code=400, detail="Файл не является корректным документом Word .docx.")

            uncompressed_size = 0
            for entry in entries:
                path = PurePath(entry.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise HTTPException(status_code=400, detail="Документ Word содержит недопустимые внутренние пути.")
                uncompressed_size += entry.file_size
                if uncompressed_size > MAX_DOCX_UNCOMPRESSED_SIZE_BYTES:
                    raise HTTPException(status_code=400, detail="Документ Word слишком велик после распаковки.")
                if entry.file_size and entry.file_size > max(1, entry.compress_size) * MAX_DOCX_COMPRESSION_RATIO:
                    raise HTTPException(status_code=400, detail="Документ Word имеет недопустимое сжатие.")
    except HTTPException:
        raise
    except (BadZipFile, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Не удалось открыть файл Word.")
