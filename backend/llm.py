# llm.py - оптимизированная версия с одним запросом

import asyncio
import json
import re
import time
import uuid
from difflib import SequenceMatcher
from types import SimpleNamespace

import httpx

from app.config import (
    DETECTOR_MODEL_NAME,
    GIGACHAT_API_BASE_URL,
    GIGACHAT_AUTH_KEY,
    GIGACHAT_AUTH_URL,
    GIGACHAT_SCOPE,
    GIGACHAT_VERIFY_SSL,
    LLM_REQUEST_TIMEOUT_SECONDS,
    MODEL_NAME,
    TEMPERATURE,
)
from prompt_templates.detector import DETECTOR_SYSTEM_PROMPT, format_detector_prompt
from prompt_templates.humanizer import SYSTEM_PROMPT, format_humanize_prompt, split_humanize_paragraphs
from prompt_templates.humanize_review import (
    HUMANIZE_REVIEW_SYSTEM_PROMPT,
    format_humanize_review_prompt,
)
from prompt_templates.paraphraser import PARAPHRASER_SYSTEM_PROMPT, format_paraphraser_prompt

GIGACHAT_CONFIG = {
    "base_url": GIGACHAT_API_BASE_URL,
    "model": MODEL_NAME,
    "temperature": TEMPERATURE
}


class LLMTimeoutError(Exception):
    """The LLM provider did not respond within the configured timeout."""


class LLMProcessingError(Exception):
    """The LLM provider returned an invalid response or failed to process the text."""


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
                raise LLMProcessingError("GigaChat token request failed") from exc

            if response.status_code != 200:
                raise LLMProcessingError(
                    f"GigaChat token request failed with HTTP {response.status_code}"
                )

            try:
                payload = response.json()
                access_token = payload["access_token"]
            except (TypeError, ValueError, KeyError) as exc:
                raise LLMProcessingError("GigaChat returned an invalid token response") from exc

            if not isinstance(access_token, str) or not access_token:
                raise LLMProcessingError("GigaChat returned an invalid access token")

            self._access_token = access_token
            self._expires_at = self._expires_at_seconds(payload.get("expires_at"))
            return access_token

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at = 0.0


token_manager = GigaChatTokenManager()


async def create_completion(**kwargs):
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
            raise LLMProcessingError("GigaChat completion request failed") from exc

        if response.status_code == 401 and attempt == 0:
            token_manager.invalidate()
            continue
        if response.status_code < 200 or response.status_code >= 300:
            raise LLMProcessingError(
                f"GigaChat completion request failed with HTTP {response.status_code}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise LLMProcessingError("GigaChat returned an invalid completion response") from exc

        if not isinstance(content, str):
            raise LLMProcessingError("GigaChat returned an empty completion")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    raise LLMProcessingError("GigaChat rejected the refreshed access token")


def humanize_max_tokens(text_length: int) -> int:
    """Reserve enough output for a rewritten text without unbounded generation."""
    return min(4096, max(1024, (text_length + 1) // 2))


def needs_stronger_rewrite(original: str, result: str) -> bool:
    """Detect a superficial rewrite and request one retry when needed."""
    threshold = 0.92
    if not result.strip():
        return False

    similarity = SequenceMatcher(None, original.split(), result.split()).ratio()
    print(f"Humanize word similarity: {similarity:.1%}")
    return similarity > threshold


async def quality_review_humanized_text(source_text: str, rewritten_text: str) -> str:
    """Run one second-pass review that corrects only clear wording issues."""
    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.1,
            max_tokens=humanize_max_tokens(len(rewritten_text)),
            messages=[
                {"role": "system", "content": HUMANIZE_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": format_humanize_review_prompt(source_text, rewritten_text)},
            ],
        )
        reviewed = response.choices[0].message.content.strip()
        source_paragraph_count = len(split_humanize_paragraphs(source_text))
        reviewed_paragraph_count = len(split_humanize_paragraphs(reviewed))
        if (
            reviewed
            and len(reviewed) >= len(rewritten_text) * 0.7
            and reviewed_paragraph_count == source_paragraph_count
        ):
            print("Humanize quality review completed")
            return reviewed
        print("Humanize quality review skipped: invalid length or paragraph structure")
    except Exception as error:
        print(f"Humanize quality review skipped: {error.__class__.__name__}")
    return rewritten_text


DETECTOR_CHUNK_WORDS = 900
HUMANIZE_CHUNK_WORDS = 900
DOCX_BATCH_WORDS = 250


def split_docx_batches(items: list[dict], max_words: int = DOCX_BATCH_WORDS) -> list[list[dict]]:
    batches, current, current_words = [], [], 0
    for item in items:
        item_words = len(item["text"].split())
        if current and current_words + item_words > max_words:
            batches.append(current)
            current, current_words = [], 0
        current.append(item)
        current_words += item_words
    if current:
        batches.append(current)
    return batches


def _parse_docx_batch_response(raw_response: str, expected_ids: list[str]) -> dict[str, str] | None:
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        items = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or [item.get("id") for item in items if isinstance(item, dict)] != expected_ids:
        return None
    if any(not isinstance(item.get("text"), str) or not item["text"].strip() for item in items):
        return None
    return {item["id"]: item["text"].strip() for item in items}


async def humanize_docx_paragraphs(
        items: list[dict],
        preserve_options: list[str] | None = None,
        academic_work_type: str = "coursework",
) -> dict[str, str]:
    """Rewrite body paragraphs while retaining an exact one-to-one paragraph mapping."""
    protected = {
        "numbers": "числа и даты",
        "terms": "термины",
        "sources": "ссылки и цитаты",
        "formulas": "формулы и обозначения",
    }
    protected_text = ", ".join(protected[item] for item in (preserve_options or []) if item in protected)
    work_type_labels = {
        "report": "реферата",
        "essay": "эссе",
        "presentation": "доклада",
        "coursework": "курсовой работы",
        "other": "учебной работы",
    }
    work_type_label = work_type_labels.get(academic_work_type, "учебной работы")
    result = {}
    for batch_index, batch in enumerate(split_docx_batches(items), start=1):
        payload = json.dumps(batch, ensure_ascii=False)
        prompt = (
            f"Отредактируй абзацы {work_type_label}. Нужен ясный академический стиль, понятный студенту. "
            "ЗАМЕТНО перепиши каждое обычное предложение, а не меняй отдельные слова. "
            "Используй короткие и средние предложения с прямым порядком слов. Длинные предложения с несколькими "
            "оборотами и придаточными при необходимости разделяй на два. Убирай канцелярит, пустые вводные фразы "
            "и шаблоны вроде «следует отметить», «в рамках данного», «осуществляется». Заменяй слишком сложные "
            "нетерминологические слова на более простые и точные.\n\n"
            "Не переходи в разговорный стиль, не упрощай научные термины, не добавляй новые факты и не сокращай "
            "смысл. Сохраняй логику, аргументы и объём каждого абзаца. "
            f"Не меняй: {protected_text or 'точные данные и терминологию'}.\n\n"
            "КРИТИЧЕСКОЕ ПРАВИЛО: верни только JSON-массив. В нём должны быть все исходные id "
            "строго по порядку и ровно по одному разу. Не добавляй, не удаляй и не объединяй элементы. "
            "Изменяй только поле text.\n\n"
            f"Входной JSON:\n{payload}"
        )
        try:
            response = await create_completion(
                model=GIGACHAT_CONFIG["model"],
                temperature=0.55,
                max_tokens=humanize_max_tokens(sum(len(item["text"]) for item in batch)),
                messages=[
                    {"role": "system", "content": "Ты редактор учебных текстов. Возвращай только корректный JSON без пояснений."},
                    {"role": "user", "content": prompt},
                ],
            )
        except LLMTimeoutError:
            raise
        except Exception as error:
            print(f"DOCX batch {batch_index}: provider request failed: {error}")
            raise LLMProcessingError("GigaChat failed to process DOCX paragraphs") from error

        expected_ids = [item["id"] for item in batch]
        parsed = _parse_docx_batch_response(response.choices[0].message.content or "", expected_ids)
        if parsed is not None:
            weak_items = [
                item for item in batch
                if needs_stronger_rewrite(item["text"], parsed[item["id"]])
            ]
            for item in weak_items:
                print(f"DOCX paragraph {item['id']}: rewrite was too close to the original; retrying")
                parsed[item["id"]] = await _humanize_chunk(
                    item["text"],
                    "academic",
                    "professional",
                    "ru",
                    academic_work_type,
                    preserve_options,
                )
            result.update(parsed)
            continue

        # Some providers occasionally add prose around JSON or return an
        # incomplete array. Preserve document integrity by falling back to one
        # request per paragraph rather than trying to guess paragraph borders.
        print(f"DOCX batch {batch_index}: invalid structured response; using paragraph fallback")
        for item in batch:
            result[item["id"]] = await _humanize_chunk(
                item["text"],
                "academic",
                "professional",
                "ru",
                academic_work_type,
                preserve_options,
            )
    return result


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
            chunks.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(segment)
        current_words += segment_words

    if current:
        chunks.append("\n\n".join(current))
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

    ai_count = sum(sentence["label"] == "ai" for sentence in sentences)
    human_count = sum(sentence["label"] == "human" for sentence in sentences)
    mixed_count = total - ai_count - human_count
    risky_count = ai_count + mixed_count
    ai_probability = round(ai_count / total * 100)
    human_probability = round(human_count / total * 100)
    mixed_probability = 100 - ai_probability - human_probability
    return {
        "ai_probability": ai_probability,
        "human_probability": human_probability,
        "mixed_probability": mixed_probability,
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


async def ask_llm(text: str, tone: str, style: str, target_language: str,
                  temperature: float = 0.7):
    """Универсальный запрос к LLM с корректным промптом"""

    # Форматируем промпт с текстом
    prompt = format_humanize_prompt(text, tone, style, target_language)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        print(f"Error in ask_llm: {e}")
        return text  # Возвращаем исходный текст при ошибке


async def _humanize_chunk(text: str, tone: str, style: str, target_language: str = "ru",
                          academic_work_type: str | None = None, preserve_options: list[str] | None = None):
    """Основной пайплайн обработки текста с проверкой длины"""

    original_length = len(text)
    print(f"Оригинал: {original_length} символов")

    # Один запрос
    prompt = format_humanize_prompt(text, tone, style, target_language,
                                    academic_work_type, preserve_options)
    max_tokens = humanize_max_tokens(original_length)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.5,  # Низкая температура для точности
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()

        # Проверка длины
        result_length = len(result)
        print(f"Результат: {result_length} символов")

        should_retry_for_length = result_length < original_length * 0.7
        should_retry_for_similarity = needs_stronger_rewrite(text, result)

        # One retry only: protect length and prevent a superficial rewrite.
        if should_retry_for_length or should_retry_for_similarity:
            retry_reason = (
                "Результат слишком близок к исходнику: ты изменил слишком мало формулировок."
                if should_retry_for_similarity
                else "Результат слишком короткий."
            )
            print(f"Повторная попытка: {retry_reason}")

            rewrite_instruction = (
                "Перепиши большинство предложений, меняя синтаксис и порядок слов, "
                "а не отдельные слова."
            )

            fallback_prompt = format_humanize_prompt(
                text, tone, style, target_language, academic_work_type, preserve_options
            ) + f"""

【ОБЯЗАТЕЛЬНАЯ ПОВТОРНАЯ ПРОВЕРКА】
{retry_reason}
Исходная длина: {original_length} символов. Предыдущая длина: {result_length} символов.
Перепиши текст заново. {rewrite_instruction}"""

            response2 = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.5,
            max_tokens=max_tokens,
            messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": fallback_prompt}
                ]
            )
            result = response2.choices[0].message.content.strip()
            print(f"Результат после повторной попытки: {len(result)} символов")

        result = await quality_review_humanized_text(text, result)
        return result

    except LLMTimeoutError:
        print(f"GigaChat timeout after {LLM_REQUEST_TIMEOUT_SECONDS} seconds")
        raise
    except Exception as e:
        print(f"Error: {e}")
        # Never pass the original text off as a successful humanization: it would
        # look like a weak result and could incorrectly consume the user's words.
        raise LLMProcessingError("GigaChat failed to process the text") from e


async def humanize_pipeline(text: str, tone: str, style: str, target_language: str = "ru",
                            academic_work_type: str | None = None, preserve_options: list[str] | None = None):
    """Rewrite long texts chunk-by-chunk so the provider cannot truncate the output."""
    chunks = split_humanize_chunks(text)
    if len(chunks) == 1:
        return await _humanize_chunk(
            text, tone, style, target_language, academic_work_type, preserve_options
        )

    print(f"Humanize: split {len(text.split())} words into {len(chunks)} chunks")
    results = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"Humanize: processing chunk {index}/{len(chunks)} ({len(chunk.split())} words)")
        results.append(await _humanize_chunk(
            chunk, tone, style, target_language, academic_work_type, preserve_options
        ))
    return "\n\n".join(results)


async def _detect_ai_chunk(text: str) -> dict:
    """Анализирует текст и возвращает вероятность того, что он написан ИИ, с разметкой по предложениям"""

    prompt = format_detector_prompt(text)
    raw_result = None

    try:
        response = await create_completion(
            model=DETECTOR_MODEL_NAME,
            temperature=0.3,
            max_tokens=8000,
            messages=[
                {"role": "system", "content": DETECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        raw_result = response.choices[0].message.content.strip()

        # Убираем markdown-обёртки
        cleaned = raw_result.replace("```json", "").replace("```", "").strip()

        # Some models still add text around JSON. Keep only the outer object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]

        # Удаляем строки-заглушки "..." которые ломают JSON
        import re
        cleaned = re.sub(r',?\s*\n\s*\.\.\.\s*\n', '\n', cleaned)
        cleaned = re.sub(r',\s*\.\.\.\s*]', ']', cleaned)

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Detector response is not an object", cleaned, 0)

        # Валидация меток предложений
        sentences = parsed.get("sentences", [])
        if not isinstance(sentences, list):
            sentences = []
        valid_labels = {"human", "mixed", "ai"}
        clean_sentences = []
        for s in sentences:
            if isinstance(s, str):
                s = {"text": s, "label": "mixed"}
            elif not isinstance(s, dict):
                continue
            label = s.get("label", "mixed")
            if label not in valid_labels:
                label = "mixed"
            clean_sentences.append({
                "text": s.get("text", ""),
                "label": label
            })

        # Пересчёт процентов из реальных меток
        if clean_sentences:
            total = len(clean_sentences)
            ai_count = sum(1 for s in clean_sentences if s["label"] == "ai")
            human_count = sum(1 for s in clean_sentences if s["label"] == "human")
            mixed_count = sum(1 for s in clean_sentences if s["label"] == "mixed")

            ai_probability = round(ai_count / total * 100)
            human_probability = round(human_count / total * 100)
            mixed_probability = 100 - ai_probability - human_probability
        else:
            ai_probability = 33
            human_probability = 34
            mixed_probability = 33

        return {
            "ai_probability": ai_probability,
            "human_probability": human_probability,
            "mixed_probability": mixed_probability,
            "verdict": parsed.get("verdict", "Не удалось определить точно"),
            "explanation": parsed.get("explanation", ""),
            "sentences": clean_sentences
        }

    except LLMTimeoutError:
        raise
    except json.JSONDecodeError as e:
        print(f"JSON decode error in detect_ai_pipeline: {e}")
        print(f"Raw result: {repr(raw_result)}")
        return {
            "ai_probability": 33,
            "human_probability": 34,
            "mixed_probability": 33,
            "verdict": "Не удалось точно определить происхождение текста",
            "explanation": "Произошла ошибка при анализе текста. Попробуйте ещё раз.",
            "sentences": [{"text": text, "label": "mixed"}]
        }
    except Exception as e:
        print(f"Error in detect_ai_pipeline: {e}")
        raise LLMProcessingError("Detector service failed") from e



async def detect_ai_pipeline(text: str) -> dict:
    """Analyze long texts in sentence-boundary chunks and return one combined report."""
    chunks = split_detector_chunks(text)
    if len(chunks) > 1:
        print(f"Detector: split {len(text.split())} words into {len(chunks)} chunks")

    results = []
    timed_out_chunks = 0
    for index, chunk in enumerate(chunks, start=1):
        try:
            results.append(await _detect_ai_chunk(chunk))
        except LLMTimeoutError:
            timed_out_chunks += 1
            print(f"Detector: chunk {index}/{len(chunks)} timed out")
            # Preserve the text in the response even if one provider call fails.
            results.append({"sentences": [{"text": chunk, "label": "mixed"}]})

    if timed_out_chunks == len(chunks):
        raise LLMTimeoutError

    combined = combine_detector_results(results)
    if timed_out_chunks:
        combined["explanation"] = (
            f"{timed_out_chunks} из {len(chunks)} частей не успела ответить. "
            "Эти фрагменты помечены как требующие ручной проверки."
        )
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
            print(f"Template patterns: chunk {index}/{len(chunks)} timed out")
        except (json.JSONDecodeError, AttributeError, IndexError) as error:
            print(f"Template patterns: invalid response in chunk {index}/{len(chunks)}: {error}")

    if not successful_chunks:
        raise LLMTimeoutError
    return {"paragraphs": list(dict.fromkeys(paragraphs))[:8]}


async def paraphrase_pipeline(text: str, style: str, tone: str) -> str:
    """Пайплайн перефразирования текста"""

    original_length = len(text)
    print(f"Перефразер. Оригинал: {original_length} символов")

    prompt = format_paraphraser_prompt(text, style, tone)

    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.7,
            messages=[
                {"role": "system", "content": PARAPHRASER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()

        result_length = len(result)
        print(f"Перефразер. Результат: {result_length} символов")

        # Если результат слишком короткий — повторная попытка
        if result_length < original_length * 0.6:
            print("⚠️ Перефразер: результат слишком короткий, повторная попытка...")
            fallback_prompt = f"""Ты сократил текст слишком сильно. Было {original_length} символов, стало {result_length}.

Перефразируй заново, сохранив ВСЕ идеи и детали оригинала. Длина результата должна быть примерно {original_length} символов (±20%).

【ОРИГИНАЛЬНЫЙ ТЕКСТ】
{text}

Ответь ТОЛЬКО готовым перефразированным текстом."""

            response2 = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.5,
                messages=[
                    {"role": "system", "content": PARAPHRASER_SYSTEM_PROMPT},
                    {"role": "user", "content": fallback_prompt}
                ]
            )
            result = response2.choices[0].message.content.strip()
            print(f"Перефразер. Результат после повтора: {len(result)} символов")

        return result

    except LLMTimeoutError:
        raise
    except Exception as e:
        print(f"Error in paraphrase_pipeline: {e}")
        raise LLMProcessingError("Paraphraser service failed") from e


async def grammar_pipeline(text: str) -> str:
    """Correct grammar and spelling while preserving meaning and structure."""
    prompt = (
        "Исправь только орфографические, пунктуационные и грамматические ошибки.\n"
        "Сохрани смысл, порядок предложений, абзацы, списки, числа и факты.\n"
        "Не добавляй новую информацию и не объясняй исправления.\n"
        "Верни только исправленный текст.\n\nТекст:\n" + text
    )
    try:
        response = await create_completion(
            model=GIGACHAT_CONFIG["model"],
            temperature=0.2,
            messages=[
                {"role": "system", "content": "Ты аккуратный корректор русского и английского текста."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except LLMTimeoutError:
        raise
    except Exception as e:
        print(f"Error in grammar_pipeline: {e}")
        raise LLMProcessingError("Grammar service failed") from e


def get_available_models():
    """Получить список доступных моделей"""
    return MODELS


def set_model(model_key: str):
    """Сменить модель"""
    if model_key in MODELS:
        GIGACHAT_CONFIG["model"] = MODELS[model_key]
        print(f"Model changed to: {MODELS[model_key]}")
        return True
    return False


async def test():
    """Тестовая функция"""
    test_text = """В глубинах океана скрывается мир, который человечество изучило хуже, чем поверхность Марса. 
    Температура там близка к нулю, а давление способно раздавить привычный батискаф, словно консервную банку. 
    Despite this, life in the abyss not only exists but thrives in the most unexpected forms."""

    print("=" * 50)
    print("Тест обработки текста (один запрос)")
    print("=" * 50)

    result = await humanize_pipeline(
        text=test_text,
        tone="neutral",
        style="simple",
        target_language="ru"
    )

    print("\n📝 ОРИГИНАЛ:")
    print(test_text)
    print("\n✨ РЕЗУЛЬТАТ:")
    print(result)
    print(f"\n📊 Статистика: {len(test_text)} → {len(result)} символов")


if __name__ == "__main__":
    asyncio.run(test())
