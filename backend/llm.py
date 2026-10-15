# llm.py - оптимизированная версия с одним запросом

import ast
import asyncio
import json
import logging
import re
import time
import uuid
from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import (
    DETECTOR_MODEL_NAME,
    GIGACHAT_API_BASE_URL,
    GIGACHAT_AUTH_KEY,
    GIGACHAT_AUTH_URL,
    GIGACHAT_SCOPE,
    GIGACHAT_VERIFY_SSL,
    GPT_API_BASE_URL,
    GPT_AUTH_KEY,
    LLM_MAX_CONCURRENT_REQUESTS,
    LLM_REQUEST_TIMEOUT_SECONDS,
    MODEL_NAME,
    TEMPERATURE,
)
from prompt_templates.detector import (
    DETECTOR_LABEL_SYSTEM_PROMPT,
    format_detector_label_prompt,
)
from prompt_templates.humanizer import (
    format_humanize_prompt,
    get_humanize_system_prompt,
    split_humanize_paragraphs,
)
from prompt_templates.study_work import (
    STUDY_WORK_DOCX_SYSTEM_PROMPT,
    format_study_work_docx_batch_prompt,
    format_study_work_humanize_prompt,
)
from prompt_templates.paraphraser import (
    format_paraphraser_prompt,
    get_paraphraser_system_prompt,
)

logger = logging.getLogger("uvicorn.error")

GIGACHAT_CONFIG = {
    "base_url": GIGACHAT_API_BASE_URL,
    "model": MODEL_NAME,
    "temperature": TEMPERATURE
}

# Temporary Cloud.ru / OpenAI-compatible provider. GigaChat configuration and
# OAuth implementation below are intentionally retained for the rollback.
CLOUD_GPT_CONFIG = {
    "base_url": GPT_API_BASE_URL,
    "model": MODEL_NAME,
    "temperature": TEMPERATURE,
}


class LLMTimeoutError(Exception):
    """The LLM provider did not respond within the configured timeout."""


class LLMProcessingError(Exception):
    """The LLM provider returned an invalid response or failed to process the text."""


class LLMProviderUnavailableError(LLMProcessingError):
    """The provider, its authentication endpoint, or its transport is unavailable."""


class LLMContentRestrictedError(LLMProcessingError):
    """The provider declined to analyze a text because of its content policy."""


class LLMInvalidResponseError(LLMProcessingError):
    """The provider replied but did not follow the response contract."""


class DetectorUnmarkedResponseError(LLMProcessingError):
    """The provider replied, but did not return usable labels for a detector batch."""


class DetectorProcessingError(LLMProcessingError):
    """An unexpected local error occurred while assembling a detector result."""


class GigaChatTokenManager:
    """Fetch and refresh GigaChat OAuth access tokens without exposing them."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    @staticmethod
    def _expires_at_seconds(value: object) -> float:
        try:
            expires_at = float(value)
        except (TypeError, ValueError):
            return time.time() + 25 * 60
        return expires_at / 1000 if expires_at > 10_000_000_000 else expires_at

    async def get_access_token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        async with self._lock:
            if self._access_token and time.time() < self._expires_at - 60:
                return self._access_token

            auth_header = GIGACHAT_AUTH_KEY
            if not auth_header.lower().startswith("basic "):
                auth_header = f"Basic {auth_header}"

            try:
                async with httpx.AsyncClient(
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    verify=GIGACHAT_VERIFY_SSL,
                ) as http_client:
                    response = await http_client.post(
                        GIGACHAT_AUTH_URL,
                        data={"scope": GIGACHAT_SCOPE},
                        headers={
                            "Accept": "application/json",
                            "Authorization": auth_header,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "RqUID": str(uuid.uuid4()),
                        },
                    )
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError from exc
            except httpx.HTTPError as exc:
                raise LLMProviderUnavailableError("GigaChat token request failed") from exc

            if response.status_code != 200:
                raise LLMProviderUnavailableError(
                    f"GigaChat token request failed with HTTP {response.status_code}"
                )

            try:
                payload = response.json()
                access_token = payload["access_token"]
            except (TypeError, ValueError, KeyError) as exc:
                raise LLMProviderUnavailableError("GigaChat returned an invalid token response") from exc

            if not isinstance(access_token, str) or not access_token:
                raise LLMProviderUnavailableError("GigaChat returned an invalid access token")

            self._access_token = access_token
            self._expires_at = self._expires_at_seconds(payload.get("expires_at"))
            return access_token

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at = 0.0


token_manager = GigaChatTokenManager()
completion_semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENT_REQUESTS)


async def create_completion(**kwargs):
    """Queue provider calls so concurrent users do not overload one API key."""
    async with completion_semaphore:
        return await _create_gigachat_completion(**kwargs)


async def _create_gigachat_completion(**kwargs):
    """Call GigaChat's OpenAI-compatible chat-completions endpoint."""
    for attempt in range(2):
        access_token = await token_manager.get_access_token()
        try:
            async with httpx.AsyncClient(
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                verify=GIGACHAT_VERIFY_SSL,
            ) as http_client:
                response = await http_client.post(
                    f"{GIGACHAT_CONFIG['base_url']}/chat/completions",
                    json=kwargs,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError from exc
        except httpx.HTTPError as exc:
            # A transport error has no HTTP response/status code. Log only its
            # type: exception text can contain proxy details and must not expose
            # connection credentials or request data.
            logger.warning("GigaChat completion transport error: %s", type(exc).__name__)
            raise LLMProviderUnavailableError(
                f"GigaChat completion transport error ({type(exc).__name__})"
            ) from exc

        if response.status_code == 401 and attempt == 0:
            token_manager.invalidate()
            continue
        if response.status_code < 200 or response.status_code >= 300:
            raise LLMProviderUnavailableError(
                f"GigaChat completion request failed with HTTP {response.status_code}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise LLMInvalidResponseError("GigaChat returned an invalid completion response") from exc

        if not isinstance(content, str):
            raise LLMInvalidResponseError("GigaChat returned an empty completion")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    raise LLMProviderUnavailableError("GigaChat rejected the refreshed access token")


async def _create_cloud_gpt_completion(**kwargs):
    """Inactive temporary fallback: call Cloud.ru Foundation Models API."""
    try:
        async with AsyncOpenAI(
            api_key=GPT_AUTH_KEY,
            base_url=CLOUD_GPT_CONFIG["base_url"],
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.chat.completions.create(**kwargs)
    except APITimeoutError as exc:
        raise LLMTimeoutError from exc
    except APIStatusError as exc:
        if exc.status_code == 402:
            raise LLMProviderUnavailableError("Cloud.ru API balance is insufficient") from exc
        raise LLMProviderUnavailableError(
            f"Cloud.ru completion request failed with HTTP {exc.status_code}"
        ) from exc
    except APIConnectionError as exc:
        raise LLMProviderUnavailableError("Cloud.ru completion request failed") from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMInvalidResponseError("Cloud.ru returned an invalid completion response") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMInvalidResponseError("Cloud.ru returned an empty completion")
    return response


def humanize_max_tokens(text_length: int) -> int:
    """Reserve enough output for a rewritten text without unbounded generation."""
    return min(4096, (text_length + 1) // 2)


DETECTOR_CHUNK_WORDS = 900
HUMANIZE_CHUNK_WORDS = 900
DOCX_BATCH_WORDS = 900
DOCX_MIN_REWRITE_WORDS = 12
DOCX_MIN_REWRITE_CHARS = 80

# In pasted Study Work text there is no Word style information. Protect only
# unambiguous structural headings before the model receives the body text.
_STUDY_WORK_SUBSECTION_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+){1,6}\.?|(?:глава|раздел|chapter|section)\s+\d+\.?)\s+\S",
    flags=re.IGNORECASE,
)
_STUDY_WORK_STANDARD_HEADING_RE = re.compile(
    r"^\s*(?:введение|заключение|содержание|оглавление|"
    r"список использованных источников|список литературы|"
    r"библиографический список|references|bibliography)\s*$",
    flags=re.IGNORECASE,
)
_STUDY_WORK_TOP_LEVEL_HEADING_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_STUDY_WORK_CONTENTS_RE = re.compile(r"^\s*(?:содержание|оглавление|contents)\s*$", flags=re.IGNORECASE)
_STUDY_WORK_BIBLIOGRAPHY_RE = re.compile(
    r"^\s*(?:список использованных источников|список литературы|"
    r"библиографический список|references|bibliography)\s*$",
    flags=re.IGNORECASE,
)
_STUDY_WORK_INTRODUCTION_RE = re.compile(r"^\s*(?:введение|introduction)\s*$", flags=re.IGNORECASE)
_MODEL_META_COMMENTARY_RE = re.compile(
    r"(?:обратите внимание,?\s*что текст выше|"
    r"текст выше полностью соответствует заданному брифу|"
    r"к сожалению,?\s*иногда генеративные языковые модели могут создавать некорректные ответы|"
    r"как и любая языковая модель,?\s*gigachat\b|"
    r"разговоры на некоторые темы временно ограничены)",
    flags=re.IGNORECASE,
)
_MODEL_REFUSAL_RE = re.compile(
    r"^(?:к сожалению|извините|я не могу|не могу|ответы .*временно ограничены)",
    flags=re.IGNORECASE | re.DOTALL,
)


_STUDY_WORK_BIBLIOGRAPHY_ALIAS_RE = re.compile(
    r"^\s*(?:"
    r"\u0441\u043f\u0438\u0441\u043e\u043a \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432|"
    r"\u0441\u043f\u0438\u0441\u043e\u043a \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u043d\u043e\u0439 \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b|"
    r"\u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u043d\u044b\u0435 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438|"
    r"\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438 \u0438 \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430|"
    r"\u043f\u0435\u0440\u0435\u0447\u0435\u043d\u044c \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u043d\u044b\u0445 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432|"
    r"\u0431\u0438\u0431\u043b\u0438\u043e\u0433\u0440\u0430\u0444\u0438\u044f|"
    r"\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430|"
    r"\u043d\u043e\u0440\u043c\u0430\u0442\u0438\u0432\u043d\u044b\u0435 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438"
    r")\s*$",
    flags=re.IGNORECASE,
)
_BIBLIOGRAPHY_ENTRY_RE = re.compile(
    r"^\s*(?:\[?\d+\]?|[IVXLCDM]+)[.)]?\s+.*(?:"
    r"https?://|www\.|doi(?:\.org)?|"
    r"\u0434\u0430\u0442\u0430\s+\u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u044f|"
    r"\u044d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u043d\w*\s+(?:\u0440\u0435\u0441\u0443\u0440\u0441|\u0431\u0438\u0431\u043b\u0438\u043e\u0442\u0435\u043a)|"
    r"retrieved|accessed)",
    flags=re.IGNORECASE,
)
_BIBLIOGRAPHY_HEADING_HINT_RE = re.compile(
    r"(?:\u0438\u0441\u0442\u043e\u0447\u043d|\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440|"
    r"\u0431\u0438\u0431\u043b\u0438\u043e\u0433\u0440\u0430\u0444|\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b)",
    flags=re.IGNORECASE,
)


def is_protected_study_work_text_heading(text: str) -> bool:
    """Recognize headings in pasted text without mistaking ordinary list items for them."""
    normalized = text.strip()
    if not normalized:
        return False
    if normalized.startswith("#"):
        return True
    if _STUDY_WORK_SUBSECTION_HEADING_RE.match(normalized):
        return True
    if _STUDY_WORK_STANDARD_HEADING_RE.match(normalized):
        return True

    # A top-level heading such as ``1. Теоретические основы`` is ambiguous
    # without DOCX formatting. Preserve only short, title-like lines; numbered
    # list items with a definition (usually containing a colon or dash) remain
    # editable as normal paragraphs.
    top_level_match = _STUDY_WORK_TOP_LEVEL_HEADING_RE.match(normalized)
    if not top_level_match:
        return False
    title = top_level_match.group(1).strip()
    return (
        len(title) <= 160
        and not re.search(r"[:;—–]", title)
        and not title.endswith((".", "!", "?"))
    )


def is_bibliography_heading(text: str) -> bool:
    """Recognize common bibliography headings without requiring one exact name."""
    return bool(
        _STUDY_WORK_BIBLIOGRAPHY_RE.match(text)
        or _STUDY_WORK_BIBLIOGRAPHY_ALIAS_RE.match(text)
    )


def find_bibliography_start_in_pasted_text(lines: list[str], start_index: int) -> int:
    """Find bibliography blocks even when their title is non-standard or omitted."""
    line_texts = [line.strip() for line in lines]
    for index in range(start_index, len(lines)):
        if is_bibliography_heading(line_texts[index]):
            return index

    # A non-standard heading is accepted only when it is followed by at least
    # two numbered bibliography entries with reliable citation markers.
    for index in range(start_index, len(lines)):
        candidate = line_texts[index]
        if (
            not candidate
            or len(candidate) > 180
            or not _BIBLIOGRAPHY_HEADING_HINT_RE.search(candidate)
            or re.match(r"^\s*(?:\[?\d+\]?|[IVXLCDM]+)[.)]", candidate)
        ):
            continue
        following = [line for line in line_texts[index + 1:index + 13] if line]
        if (
            following
            and _BIBLIOGRAPHY_ENTRY_RE.match(following[0])
            and sum(bool(_BIBLIOGRAPHY_ENTRY_RE.match(line)) for line in following) >= 2
        ):
            return index

    # Some pasted documents omit the heading entirely. Keep a trailing run of
    # at least two recognisable bibliography entries unchanged in that case.
    for index in range(start_index, len(lines)):
        if not _BIBLIOGRAPHY_ENTRY_RE.match(line_texts[index]):
            continue
        following = [line for line in line_texts[index + 1:index + 10] if line]
        if any(_BIBLIOGRAPHY_ENTRY_RE.match(line) for line in following):
            return index
    return len(lines)


def split_study_work_pasted_document(text: str) -> tuple[str, str, str]:
    """Keep title/contents and bibliography out of pasted Study Work requests."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    line_texts = [line.strip() for line in lines]

    contents_index = next(
        (index for index, line in enumerate(line_texts) if _STUDY_WORK_CONTENTS_RE.match(line)),
        None,
    )
    body_start = 0
    if contents_index is not None:
        body_start = next(
            (
                index
                for index in range(contents_index + 1, len(lines))
                if _STUDY_WORK_INTRODUCTION_RE.match(line_texts[index])
            ),
            len(lines),
        )

    bibliography_index = find_bibliography_start_in_pasted_text(lines, body_start)
    # Keep the blank spacing before the bibliography exactly as the user pasted it.
    bibliography_start = bibliography_index
    while bibliography_start > body_start and not line_texts[bibliography_start - 1]:
        bibliography_start -= 1

    return (
        "".join(lines[:body_start]),
        "".join(lines[body_start:bibliography_start]),
        "".join(lines[bibliography_start:]),
    )


def is_model_meta_commentary(text: str) -> bool:
    """Reject provider commentary and refusal boilerplate instead of showing it as coursework."""
    return bool(_MODEL_META_COMMENTARY_RE.search(text))


def is_model_refusal(text: str) -> bool:
    """Recognize a provider refusal before it can replace a source paragraph."""
    return is_model_meta_commentary(text) or bool(_MODEL_REFUSAL_RE.search(text.strip()))


def should_rewrite_docx_item(text: str) -> bool:
    """Skip titles, list markers, and other fragments too short to rewrite safely."""
    normalized = text.strip()
    return (
        len(normalized) >= DOCX_MIN_REWRITE_CHARS
        and len(normalized.split()) >= DOCX_MIN_REWRITE_WORDS
    )


def split_docx_batches(items: list[dict], max_words: int = DOCX_BATCH_WORDS) -> list[list[dict]]:
    """Split DOCX paragraphs into near-even batches without splitting a paragraph."""
    total_words = sum(len(item["text"].split()) for item in items)
    desired_batch_count = max(1, -(-total_words // max_words))
    target_words = max(1, -(-total_words // desired_batch_count))

    batches, current, current_words = [], [], 0
    for item in items:
        item_words = len(item["text"].split())
        exceeds_maximum = current and current_words + item_words > max_words
        reached_target = (
            current
            and current_words >= target_words
            and len(batches) < desired_batch_count - 1
        )
        if exceeds_maximum or reached_target:
            batches.append(current)
            current, current_words = [], 0
        current.append(item)
        current_words += item_words
    if current:
        batches.append(current)
    return batches


def _load_batch_json_candidates(raw_response: str):
    """Yield JSON values embedded in a provider response without exposing its text."""
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
    candidates = []
    array_start, array_end = cleaned.find("["), cleaned.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(cleaned[array_start:array_end + 1])
    object_start, object_end = cleaned.find("{"), cleaned.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(cleaned[object_start:object_end + 1])

    for candidate in candidates:
        try:
            # GigaChat sometimes puts literal line breaks inside JSON strings.
            # ``strict=False`` accepts those characters without relaxing the
            # required JSON shape, ids, or one-to-one paragraph mapping.
            parsed = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            try:
                parsed = json.loads(
                    re.sub(r",\s*([}\]])", r"\1", candidate), strict=False
                )
            except json.JSONDecodeError:
                continue
        yield parsed


def _parse_docx_batch_response(raw_response: str, expected_ids: list[str]) -> dict[str, str] | None:
    for parsed in _load_batch_json_candidates(raw_response):

        if isinstance(parsed, dict):
            nested_items = parsed.get("items", parsed.get("paragraphs"))
            if isinstance(nested_items, list):
                parsed = nested_items
            elif all(isinstance(parsed.get(item_id), str) for item_id in expected_ids):
                return {item_id: parsed[item_id].strip() for item_id in expected_ids}
            elif all(
                isinstance(parsed.get(item_id), dict)
                and isinstance(parsed[item_id].get("text"), str)
                for item_id in expected_ids
            ):
                return {item_id: parsed[item_id]["text"].strip() for item_id in expected_ids}

        if not isinstance(parsed, list):
            continue
        if all(isinstance(item, str) and item.strip() for item in parsed):
            if len(parsed) == len(expected_ids):
                return dict(zip(expected_ids, (item.strip() for item in parsed)))
            continue
        if [item.get("id") for item in parsed if isinstance(item, dict)] != expected_ids:
            continue
        if any(not isinstance(item.get("text"), str) or not item["text"].strip() for item in parsed):
            continue
        return {item["id"]: item["text"].strip() for item in parsed}
    return None


def strip_docx_markdown_headings(text: str) -> str:
    """Never write model-generated Markdown heading markers into a Word document."""
    return re.sub(r"(?m)^(\s*)#{1,6}[ \t]+", r"\1", text).strip()


def normalize_docx_replacement(source_text: str, replacement: str) -> str:
    """Restore an inline ``label: explanation`` form when the model made it a heading."""
    source_label = re.match(r"^[\t \u00a0]*([^:\n]{2,120}):[ \t\u00a0]+", source_text)
    # Models sometimes put one or more blank lines before a Markdown heading.
    # Accept them here; otherwise the marker is stripped later but the original
    # inline ``label:`` structure cannot be restored.
    generated_heading = re.match(r"^[\s\u00a0]*#{1,6}[ \t]+([^\r\n]+?)[ \t\u00a0]*(?:\r?\n)+", replacement)
    if source_label and generated_heading:
        original = re.sub(r"\s+", " ", source_label.group(1)).casefold()
        generated = re.sub(r"\s+", " ", generated_heading.group(1)).casefold()
        if original == generated:
            continuation = replacement[generated_heading.end():].lstrip()
            return f"{source_label.group(1)}: {continuation}".strip()
    return strip_docx_markdown_headings(replacement)


def normalize_humanize_replacement(source_text: str, replacement: str) -> str:
    """Keep inline labels, list markers, and indentation intact in Humanize."""
    leading_indent_match = re.match(r"^[\t \u00a0]*", source_text)
    leading_indent = leading_indent_match.group(0) if leading_indent_match else ""
    source = source_text.strip()
    cleaned = strip_docx_markdown_headings(replacement).strip()

    marker_pattern = r"(?P<marker>[-*+\u2022\u2013\u2014]|\d+[.)])(?P<space>\s+)"
    source_marker = re.match(rf"^{marker_pattern}", source)
    generated_marker = re.match(rf"^{marker_pattern}", cleaned)
    if source_marker:
        if (
            generated_marker is None
            or source_marker.group("marker") != generated_marker.group("marker")
        ):
            return source_text
        source_for_label = source[source_marker.end():]
        cleaned_for_label = cleaned[generated_marker.end():]
        marker_prefix = source[:source_marker.end()]
    else:
        if generated_marker is not None:
            return source_text
        source_for_label = source
        cleaned_for_label = cleaned
        marker_prefix = ""

    source_label = re.match(r"^([^:\n]{2,120}):\s+", source_for_label)
    if source_label:
        generated_label = re.match(
            r"^([^:\n]{2,120}):\s+(.+)$", cleaned_for_label, flags=re.DOTALL
        )
        if (
            generated_label is None
            or re.sub(r"\s+", " ", source_label.group(1)).casefold()
            != re.sub(r"\s+", " ", generated_label.group(1)).casefold()
        ):
            return source_text
        cleaned = f"{marker_prefix}{source_label.group(1)}: {generated_label.group(2)}"

    if "\n" not in source_text and "\r" not in source_text:
        cleaned = re.sub(r"\s*(?:\r?\n)+\s*", " ", cleaned)
    return f"{leading_indent}{cleaned.strip()}"


def restore_paraphraser_layout(source_text: str, replacement: str) -> str:
    """Restore source paragraph spacing and leading indentation after paraphrasing."""
    newline = "\r\n" if "\r\n" in source_text else "\n"
    source_lines = source_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result_lines = replacement.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    source_content_indexes = [index for index, line in enumerate(source_lines) if line.strip()]
    result_content = [line.strip() for line in result_lines if line.strip()]

    # The paraphraser must not merge or split paragraphs. If it does, preserve
    # its response unchanged instead of assigning an indent to the wrong text.
    if len(source_content_indexes) != len(result_content):
        return replacement

    restored_lines = list(source_lines)
    for index, rewritten_line in zip(source_content_indexes, result_content):
        leading_indent = re.match(r"^[\t \u00a0]*", source_lines[index]).group(0)
        restored_lines[index] = f"{leading_indent}{rewritten_line}"

    restored = newline.join(restored_lines)
    if source_text.endswith(("\r", "\n")) and not restored.endswith(newline):
        restored += newline
    return restored


async def humanize_docx_paragraphs(
        items: list[dict],
        academic_work_type: str = "coursework",
        target_language: str = "ru",
        log_label: str = "DOCX",
) -> dict[str, str]:
    """Rewrite body paragraphs while retaining an exact one-to-one paragraph mapping."""
    result = {
        item["id"]: item["text"]
        for item in items
        if not should_rewrite_docx_item(item["text"])
    }
    rewrite_items = [item for item in items if should_rewrite_docx_item(item["text"])]
    skipped_count = len(items) - len(rewrite_items)
    if skipped_count:
        logger.info("%s: skipped %s short elements without LLM requests", log_label, skipped_count)

    for batch_index, batch in enumerate(split_docx_batches(rewrite_items), start=1):
        prompt = format_study_work_docx_batch_prompt(
            batch, academic_work_type, target_language
        )
        try:
            response = await create_completion(
                model=GIGACHAT_CONFIG["model"],
                temperature=0.55,
                max_tokens=humanize_max_tokens(sum(len(item["text"]) for item in batch)),
                messages=[
                    {"role": "system", "content": STUDY_WORK_DOCX_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        except (LLMTimeoutError, LLMProcessingError):
            raise
        except Exception as error:
            logger.exception("Unexpected %s batch processing error", log_label)
            raise LLMProcessingError("DOCX batch processing failed") from error

        expected_ids = [item["id"] for item in batch]
        parsed = _parse_docx_batch_response(response.choices[0].message.content or "", expected_ids)
        if parsed is not None:
            rejected_count = sum(is_model_meta_commentary(value) for value in parsed.values())
            normalized_parsed = {}
            for item in batch:
                source_text = item["text"]
                model_text = parsed[item["id"]]
                replacement = (
                    source_text
                    if is_model_meta_commentary(model_text)
                    else normalize_docx_replacement(source_text, model_text)
                )
                normalized_parsed[item["id"]] = replacement
            if rejected_count:
                logger.warning(
                    "%s batch %s: kept %s source paragraph(s) after model commentary",
                    log_label,
                    batch_index,
                    rejected_count,
                )
            result.update(normalized_parsed)
            continue

        # A malformed batch response can be caused by a single sensitive
        # paragraph. Retry paragraphs independently so the other text still
        # receives a result.
        logger.warning(
            "%s batch %s: invalid structured response; using paragraph fallback",
            log_label,
            batch_index,
        )
        for item in batch:
            replacement = await _humanize_chunk(
                item["text"], "academic", target_language, academic_work_type
            )
            normalized_replacement = (
                item["text"]
                if is_model_meta_commentary(replacement)
                else normalize_docx_replacement(item["text"], replacement)
            )
            result[item["id"]] = normalized_replacement
    return result


async def humanize_study_work_text_pipeline(
        text: str,
        target_language: str = "ru",
        academic_work_type: str = "coursework",
) -> str:
    """Rewrite pasted Study Work body paragraphs without sending headings to the LLM."""
    protected_prefix, body_text, protected_suffix = split_study_work_pasted_document(text)
    paragraphs = split_humanize_paragraphs(body_text)
    result = paragraphs.copy()
    editable_items = [
        {"id": f"p{index}", "text": paragraph}
        for index, paragraph in enumerate(paragraphs)
        if not is_protected_study_work_text_heading(paragraph)
    ]
    protected_count = len(paragraphs) - len(editable_items)
    if protected_prefix or protected_suffix or protected_count:
        logger.info(
            "Study Work text: preserved title/contents=%s, bibliography=%s, headings=%s without LLM requests",
            bool(protected_prefix),
            bool(protected_suffix),
            protected_count,
        )
    if not editable_items:
        assembled_body = "\n\n".join(result)
        return f"{protected_prefix}{assembled_body}{protected_suffix}"

    # The JSON mapping keeps each editable paragraph in place while batches stay
    # close to 900 words.
    replacements = await humanize_docx_paragraphs(
        editable_items,
        academic_work_type,
        target_language,
        log_label="Study Work text",
    )
    for item in editable_items:
        index = int(item["id"][1:])
        result[index] = replacements[item["id"]]
    assembled_body = "\n\n".join(result)
    return f"{protected_prefix}{assembled_body}{protected_suffix}"


def split_detector_chunks(text: str, max_words: int = DETECTOR_CHUNK_WORDS) -> list[str]:
    """Split a long text at sentence boundaries to keep detector replies small."""
    sentences = [part.strip() for part in re.split(r'(?<=[.!?…])\s+', text) if part.strip()]
    if not sentences:
        return [text]

    chunks, current, current_words = [], [], 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words + sentence_words > max_words:
            chunks.append(" ".join(current))
            current, current_words = [], 0

        # Extremely long sentences are rare, but must not recreate the original timeout.
        if sentence_words > max_words:
            words = sentence.split()
            for start in range(0, len(words), max_words):
                if current:
                    chunks.append(" ".join(current))
                    current, current_words = [], 0
                chunks.append(" ".join(words[start:start + max_words]))
            continue

        current.append(sentence)
        current_words += sentence_words

    if current:
        chunks.append(" ".join(current))
    return chunks


def split_humanize_chunks(text: str, max_words: int = HUMANIZE_CHUNK_WORDS) -> list[str]:
    """Split long text into balanced chunks while preferring paragraph boundaries."""
    paragraphs = split_humanize_paragraphs(text)
    if not paragraphs:
        return [text]

    total_words = sum(len(paragraph.split()) for paragraph in paragraphs)
    desired_chunk_count = max(1, -(-total_words // max_words))
    target_words = max(1, -(-total_words // desired_chunk_count))

    segments = []
    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if paragraph_words > max_words:
            segments.extend(split_detector_chunks(paragraph, target_words))
        else:
            segments.append(paragraph)

    separator = "\n" if not re.search(r"\n\s*\n", text) else "\n\n"
    chunks, current, current_words = [], [], 0
    for segment in segments:
        segment_words = len(segment.split())
        exceeds_maximum = current and current_words + segment_words > max_words
        reached_target = (
            current
            and current_words >= target_words
            and len(chunks) < desired_chunk_count - 1
        )
        if exceeds_maximum or reached_target:
            chunks.append(separator.join(current))
            current, current_words = [], 0
        current.append(segment)
        current_words += segment_words

    if current:
        chunks.append(separator.join(current))
    return chunks


def combine_detector_results(results: list[dict]) -> dict:
    """Combine sentence labels from independent chunks into the public detector format."""
    sentences = [sentence for result in results for sentence in result.get("sentences", [])]
    total = len(sentences)
    if not total:
        return {
            "ai_probability": 0,
            "human_probability": 0,
            "mixed_probability": 0,
            "verdict": "Не удалось выделить предложения для анализа",
            "explanation": "Попробуйте проверить текст ещё раз.",
            "sentences": [],
        }

    analyzed_sentences = [
        sentence for sentence in sentences
        if sentence.get("label") in {"human", "mixed", "ai"}
    ]
    analyzed_total = len(analyzed_sentences)
    unmarked_count = total - analyzed_total
    if not analyzed_total:
        return {
            "ai_probability": 0,
            "human_probability": 0,
            "mixed_probability": 0,
            "unmarked_count": unmarked_count,
            "verdict": "Провайдер не смог проанализировать текст.",
            "explanation": "Текст оставлен без подсветки и не учтён в процентах.",
            "sentences": sentences,
        }

    ai_count = sum(sentence["label"] == "ai" for sentence in analyzed_sentences)
    human_count = sum(sentence["label"] == "human" for sentence in analyzed_sentences)
    mixed_count = analyzed_total - ai_count - human_count
    risky_count = ai_count + mixed_count
    ai_probability = round(ai_count / analyzed_total * 100)
    human_probability = round(human_count / analyzed_total * 100)
    mixed_probability = 100 - ai_probability - human_probability
    return {
        "ai_probability": ai_probability,
        "human_probability": human_probability,
        "mixed_probability": mixed_probability,
        "unmarked_count": unmarked_count,
        "verdict": (
            "Шаблонных формулировок не найдено."
            if not risky_count
            else f"Найдено фрагментов, которые могут звучать шаблонно: {risky_count}."
        ),
        "explanation": "Для точной оценки сверяйте выделенные фрагменты с контекстом работы.",
        "sentences": sentences,
    }

# Словарь для разных моделей (можно выбрать лучшую)
MODELS = {
    "gigachat-2": MODEL_NAME,
}


async def ask_llm(text: str, style: str, target_language: str,
                  temperature: float = 0.7):
    """Универсальный запрос к LLM с корректным промптом"""

    # Форматируем промпт с текстом
    prompt = format_humanize_prompt(text, style, target_language)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=temperature,
            messages=[
                {"role": "system", "content": get_humanize_system_prompt(style, target_language)},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        logger.exception("LLM request failed in ask_llm")
        return text  # Возвращаем исходный текст при ошибке


async def _humanize_chunk(text: str, style: str, target_language: str = "ru",
                          academic_work_type: str | None = None):
    """Основной пайплайн обработки текста с проверкой длины"""

    original_length = len(text)
    logger.info("Humanize source length: %s characters", original_length)

    # Один запрос
    prompt = format_humanize_prompt(text, style, target_language)
    if academic_work_type:
        prompt = format_study_work_humanize_prompt(prompt, academic_work_type)
    max_tokens = humanize_max_tokens(original_length)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.5,  # Низкая температура для точности
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": get_humanize_system_prompt(style, target_language)},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()

        # Проверка длины
        result_length = len(result)
        logger.info("Humanize result length: %s characters", result_length)
        if is_model_refusal(result):
            logger.warning("Humanize: provider returned a content restriction")
            return result

        should_retry_for_length = result_length < original_length * 0.7
        should_retry_for_similarity = False

        # One retry only: protect length and prevent a superficial rewrite.
        if should_retry_for_length:
            retry_reason = (
                "Результат слишком близок к исходнику: ты изменил слишком мало формулировок."
                if should_retry_for_similarity
                else "Результат слишком короткий."
            )
            logger.info("Humanize retry requested: %s", retry_reason)

            rewrite_instruction = (
                "Перепиши большинство предложений, меняя синтаксис и порядок слов, "
                "а не отдельные слова."
            )

            fallback_prompt = format_humanize_prompt(text, style, target_language)
            if academic_work_type:
                fallback_prompt = format_study_work_humanize_prompt(
                    fallback_prompt, academic_work_type
                )
            fallback_prompt += f"""

【ОБЯЗАТЕЛЬНАЯ ПОВТОРНАЯ ПРОВЕРКА】
{retry_reason}
Исходная длина: {original_length} символов. Предыдущая длина: {result_length} символов.
Перепиши текст заново. {rewrite_instruction}"""

            response2 = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.5,
            max_tokens=max_tokens,
            messages=[
                    {"role": "system", "content": get_humanize_system_prompt(style, target_language)},
                    {"role": "user", "content": fallback_prompt}
                ]
            )
            result = response2.choices[0].message.content.strip()
            logger.info("Humanize retry result length: %s characters", len(result))
            if len(result) < original_length * 0.7 and not is_model_refusal(result):
                logger.warning("Humanize: repeated short result; kept source batch unchanged")
                return text

        return result

    except LLMTimeoutError:
        logger.warning("GigaChat timed out after %s seconds", LLM_REQUEST_TIMEOUT_SECONDS)
        raise
    except LLMProcessingError:
        raise
    except Exception as e:
        logger.exception("Unexpected Humanize processing error")
        # Never pass the original text off as a successful humanization: it would
        # look like a weak result and could incorrectly consume the user's words.
        raise LLMProcessingError("GigaChat failed to process the text") from e


async def _humanize_text_chunk_with_refusal_fallback(
        text: str, style: str, target_language: str,
        academic_work_type: str | None = None,
) -> str:
    """Keep the complete source batch when the provider explicitly declines it."""
    result = await _humanize_chunk(text, style, target_language, academic_work_type)
    if is_model_refusal(result):
        logger.warning("Humanize: kept the source batch after a provider refusal")
        return text
    return result


async def humanize_pipeline(text: str, style: str, target_language: str = "ru",
                            academic_work_type: str | None = None):
    """Rewrite long texts chunk-by-chunk so the provider cannot truncate the output."""
    chunks = split_humanize_chunks(text)
    if len(chunks) == 1:
        return await _humanize_text_chunk_with_refusal_fallback(
            text, style, target_language, academic_work_type
        )

    logger.info("Humanize: processing %s text batch(es)", len(chunks))
    results = [
        await _humanize_text_chunk_with_refusal_fallback(
            chunk, style, target_language, academic_work_type
        )
        for chunk in chunks
    ]
    separator = "\n" if not re.search(r"\n\s*\n", text) else "\n\n"
    return separator.join(results)


def split_detector_items(text: str) -> list[dict]:
    """Create stable local detector units without losing line-level structure."""
    items: list[dict] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraph_index = 0
    for line in normalized.split("\n"):
        if not line.strip():
            continue
        for fragment in re.split(r"(?<=[.!?\u2026])(?=\s+)", line):
            fragment = fragment.strip()
            if fragment:
                items.append({
                    "id": f"s{len(items)}",
                    "text": fragment,
                    "paragraph": paragraph_index,
                })
        paragraph_index += 1
    return items or [{"id": "s0", "text": text.strip()}]


def split_detector_batch_by_paragraph(batch: list[dict]) -> list[list[dict]]:
    """Restore source paragraph groups when a broad detector batch is declined."""
    paragraphs: list[list[dict]] = []
    current_paragraph: list[dict] = []
    current_index: int | None = None
    for item in batch:
        paragraph_index = item.get("paragraph")
        if current_paragraph and paragraph_index != current_index:
            paragraphs.append(current_paragraph)
            current_paragraph = []
        current_paragraph.append(item)
        current_index = paragraph_index
    if current_paragraph:
        paragraphs.append(current_paragraph)
    return paragraphs


async def _detect_ai_item_batch(items: list[dict]) -> dict[str, str]:
    """Ask the provider for labels of server-defined text fragments only."""
    prompt = format_detector_label_prompt(items)
    try:
        response = await create_completion(
            model=DETECTOR_MODEL_NAME,
            temperature=0.3,
            max_tokens=8000,
            messages=[
                {"role": "system", "content": DETECTOR_LABEL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except (LLMTimeoutError, LLMProcessingError):
        raise
    except Exception as error:
        logger.exception("Unexpected detector batch processing error")
        raise DetectorProcessingError("Detector processing failed") from error

    raw_response = response.choices[0].message.content or ""
    if _MODEL_META_COMMENTARY_RE.search(raw_response):
        raise LLMContentRestrictedError("GigaChat declined to analyze this text")
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
    parsed = None
    for opening, closing in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opening), cleaned.rfind(closing)
        if start < 0 or end <= start:
            continue
        candidate = cleaned[start:end + 1]
        try:
            parsed = json.loads(candidate)
            break
        except json.JSONDecodeError:
            try:
                parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
                break
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(candidate)
                    break
                except (SyntaxError, ValueError):
                    continue

    if parsed is None:
        recovered_labels = []
        for object_match in re.finditer(r"\{[^{}]{1,300}\}", cleaned, flags=re.DOTALL):
            item_text = object_match.group(0)
            id_match = re.search(r"[\"']?id[\"']?\s*:\s*[\"']?(s\d+)", item_text, flags=re.IGNORECASE)
            label_match = re.search(
                r"[\"']?label[\"']?\s*:\s*[\"']?(human|mixed|ai)\b",
                item_text,
                flags=re.IGNORECASE,
            )
            if id_match and label_match:
                recovered_labels.append({"id": id_match.group(1), "label": label_match.group(1).lower()})
        if not recovered_labels:
            for item_id, label in re.findall(
                r"\b(s\d+)\b\s*(?::|=|\||[-–—])\s*[\"'`*]*(human|mixed|ai)\b",
                cleaned,
                flags=re.IGNORECASE,
            ):
                recovered_labels.append({"id": item_id, "label": label.lower()})
        if recovered_labels:
            parsed = {"items": recovered_labels}

    if parsed is None:
        logger.warning("Detector returned labels in an unreadable JSON format (%s characters)", len(raw_response))
        raise DetectorUnmarkedResponseError("Detector returned an invalid label response")

    if isinstance(parsed, dict):
        labels = parsed.get("items", parsed.get("labels"))
        if isinstance(labels, dict):
            labels = [{"id": item_id, "label": label} for item_id, label in labels.items()]
    else:
        labels = parsed

    expected_ids = [item["id"] for item in items]
    if not isinstance(labels, list):
        logger.warning("Detector response does not contain a label list")
        raise DetectorUnmarkedResponseError("Detector returned incomplete labels")

    valid_labels = {"human", "mixed", "ai"}
    if all(isinstance(label, str) for label in labels):
        normalized_labels = [label.lower().strip() for label in labels]
        if len(normalized_labels) != len(expected_ids) or any(label not in valid_labels for label in normalized_labels):
            logger.warning("Detector response contains an incomplete or invalid compact label list")
            raise DetectorUnmarkedResponseError("Detector returned incomplete labels")
        return dict(zip(expected_ids, normalized_labels))

    label_by_id: dict[str, str] = {}
    for item in labels:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        label = item.get("label")
        if isinstance(label, str):
            label = label.lower().strip()
        if item_id in label_by_id or item_id not in expected_ids or label not in valid_labels:
            logger.warning("Detector response contains an invalid item label")
            raise DetectorUnmarkedResponseError("Detector returned invalid labels")
        label_by_id[item_id] = label

    if set(label_by_id) != set(expected_ids):
        logger.warning("Detector response is missing one or more item labels")
        raise DetectorUnmarkedResponseError("Detector returned incomplete labels")
    return {item_id: label_by_id[item_id] for item_id in expected_ids}


async def detect_ai_pipeline(text: str) -> dict:
    """Analyze long texts in sentence-boundary chunks and return one combined report."""
    items = split_detector_items(text)
    batches = split_docx_batches(items, DETECTOR_CHUNK_WORDS)
    if len(batches) > 1:
        logger.info("Detector: split %s words into %s batches", len(text.split()), len(batches))

    results = []
    timed_out_chunks = 0
    for index, batch in enumerate(batches, start=1):
        try:
            labels = await _detect_ai_item_batch(batch)
            results.append({
                "sentences": [
                    {"text": item["text"], "label": labels[item["id"]]}
                    for item in batch
                ]
            })
        except (LLMContentRestrictedError, DetectorUnmarkedResponseError):
            paragraph_batches = split_detector_batch_by_paragraph(batch)
            logger.warning(
                "Detector: batch %s/%s returned no usable labels; retrying %s paragraph(s) separately",
                index,
                len(batches),
                len(paragraph_batches),
            )
            for paragraph_index, paragraph_batch in enumerate(paragraph_batches, start=1):
                if len(paragraph_batches) == 1:
                    results.append({
                        "sentences": [
                            {"text": item["text"], "label": "unmarked"}
                            for item in paragraph_batch
                        ]
                    })
                    continue
                try:
                    labels = await _detect_ai_item_batch(paragraph_batch)
                    results.append({
                        "sentences": [
                            {"text": item["text"], "label": labels[item["id"]]}
                            for item in paragraph_batch
                        ]
                    })
                except (LLMContentRestrictedError, DetectorUnmarkedResponseError):
                    logger.warning(
                        "Detector: paragraph %s/%s in batch %s/%s returned no usable labels",
                        paragraph_index,
                        len(paragraph_batches),
                        index,
                        len(batches),
                    )
                    results.append({
                        "sentences": [
                            {"text": item["text"], "label": "unmarked"}
                            for item in paragraph_batch
                        ]
                    })
                except LLMTimeoutError:
                    timed_out_chunks += 1
                    logger.warning(
                        "Detector: paragraph %s/%s in batch %s/%s timed out",
                        paragraph_index,
                        len(paragraph_batches),
                        index,
                        len(batches),
                    )
                    results.append({
                        "sentences": [
                            {"text": item["text"], "label": "mixed"}
                            for item in paragraph_batch
                        ]
                    })
        except LLMTimeoutError:
            timed_out_chunks += 1
            logger.warning("Detector: batch %s/%s timed out", index, len(batches))
            results.append({
                "sentences": [
                    {"text": item["text"], "label": "mixed"}
                    for item in batch
                ]
            })

    if timed_out_chunks == len(batches):
        raise LLMTimeoutError

    combined = combine_detector_results(results)
    notes = []
    if timed_out_chunks:
        notes.append(
            f"{timed_out_chunks} из {len(batches)} частей не успела ответить и помечены для ручной проверки."
        )
    if notes:
        combined["explanation"] = " ".join(notes)
    return combined


async def detect_template_patterns_pipeline(text: str) -> dict:
    """Lightweight academic-editor check: return only the most templated paragraphs."""
    chunks = split_humanize_chunks(text, max_words=1200)
    paragraphs = []
    successful_chunks = 0
    for index, chunk in enumerate(chunks, start=1):
        prompt = (
            "Выбери только самые шаблонные абзацы: те, где сильнее всего заметны AI-штампы, "
            "канцелярит или однотипные формулировки. Не оценивай, кто написал текст, и не анализируй предложения по отдельности. "
            "Верни строгий JSON вида {\"paragraphs\":[\"полный точный абзац из текста\"]}. "
            "Включай не больше 3 абзацев и располагай их от наиболее шаблонного к менее шаблонному. "
            "Каждый абзац копируй дословно целиком; если подходящих нет, верни пустой массив.\n\n"
            f"Текст:\n{chunk}"
        )
        try:
            response = await create_completion(
                model=DETECTOR_MODEL_NAME,
                temperature=0.2,
                max_tokens=1200,
                messages=[
                    {"role": "system", "content": "Ты редактор учебных текстов. Отвечай только JSON."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            start, end = raw.find("{"), raw.rfind("}")
            parsed = json.loads(raw[start:end + 1] if start >= 0 and end > start else raw)
            items = parsed.get("paragraphs", []) if isinstance(parsed, dict) else []
            if isinstance(items, list):
                paragraphs.extend(item.strip() for item in items if isinstance(item, str) and item.strip())
            successful_chunks += 1
        except LLMTimeoutError:
            logger.warning("Template patterns: chunk %s/%s timed out", index, len(chunks))
        except (json.JSONDecodeError, AttributeError, IndexError) as error:
            logger.warning(
                "Template patterns: invalid response in chunk %s/%s: %s",
                index,
                len(chunks),
                error,
            )

    if not successful_chunks:
        raise LLMTimeoutError
    return {"paragraphs": list(dict.fromkeys(paragraphs))[:8]}


async def paraphrase_pipeline(text: str, style: str) -> str:
    """Пайплайн перефразирования текста"""

    original_length = len(text)
    logger.info("Paraphraser source length: %s characters", original_length)

    prompt = format_paraphraser_prompt(text, style)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.2,
            messages=[
                {"role": "system", "content": get_paraphraser_system_prompt(style)},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()

        result_length = len(result)
        logger.info("Paraphraser result length: %s characters", result_length)

        # Если результат слишком короткий — повторная попытка
        if result_length < original_length * 0.6:
            logger.warning("Paraphraser result is too short; retrying")
            fallback_prompt = format_paraphraser_prompt(text, style) + f"""

【ПОВТОРНАЯ ПРОВЕРКА】
Предыдущий результат был слишком коротким: исходник — {original_length} символов, результат — {result_length}.
Выполни обработку заново, сохранив все идеи и детали. Длина результата должна быть примерно {original_length} символов (±20%)."""

            response2 = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.2,
                messages=[
                    {"role": "system", "content": get_paraphraser_system_prompt(style)},
                    {"role": "user", "content": fallback_prompt}
                ]
            )
            result = response2.choices[0].message.content.strip()
            logger.info("Paraphraser retry result length: %s characters", len(result))

        return restore_paraphraser_layout(text, result)

    except (LLMTimeoutError, LLMProcessingError):
        raise
    except Exception as e:
        logger.exception("Unexpected paraphrase processing error")
        raise LLMProcessingError("Paraphrase processing failed") from e


def get_available_models():
    """Получить список доступных моделей"""
    return MODELS


def set_model(model_key: str):
    """Сменить модель"""
    if model_key in MODELS:
        GIGACHAT_CONFIG["model"] = MODELS[model_key]
        logger.info("Model changed to: %s", MODELS[model_key])
        return True
    return False


async def test():
    """Тестовая функция"""
    test_text = """В глубинах океана скрывается мир, который человечество изучило хуже, чем поверхность Марса. 
    Температура там близка к нулю, а давление способно раздавить привычный батискаф, словно консервную банку. 
    Despite this, life in the abyss not only exists but thrives in the most unexpected forms."""

    logger.info("Running manual one-request text processing test")

    result = await humanize_pipeline(
        text=test_text,
        style="human",
        target_language="ru"
    )

    logger.info(
        "Manual text processing test completed: source_length=%s result_length=%s",
        len(test_text),
        len(result),
    )


if __name__ == "__main__":
    asyncio.run(test())
