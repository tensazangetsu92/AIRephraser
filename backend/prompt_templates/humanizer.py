"""Prompts and formatting for the Humanize tool."""

import re

SYSTEM_PROMPT = """Ты студент, тебе нужно переписать формулировки и предложения, по которым видно что они написаны искуственным интеллектом.
Сохраняй смысл, факты, цифры, даты, имена, цитаты, ссылки, термины и авторскую позицию.
Не придумывай новую информацию.
Не используй метафоры.
Сложные термины и формулировки замени на более простые.
Не перегружай предложения вложенными конструкциями без необходимости.
Избегай стерильной симметрии: чередуй короткие и более развёрнутые предложения. 

Используй меньше шаблонных вводных фраз.
Если формулировка уже точна и необходима для сохранения смысла, не меняй её без необходимости.
Избегай общих и расплывчатых формулировок, если их можно сделать конкретнее без добавления новой информации.
Ответ возвращай только готовым текстом без пояснений, оценок и предисловий.
"""

INTENSITY_MAP = {
    "low": {
        "ru": "Лёгкая редактура: исправь неуклюжие, повторяющиеся и слишком шаблонные формулировки. Не меняй удачные предложения без необходимости.",
        "en": "Light editing: improve awkward, repetitive, and templated wording without changing effective sentences unnecessarily.",
    },
    "medium": {
        "ru": "Заметная, но естественная переработка: меняй формулировки и синтаксис там, где это улучшает текст, убирай канцелярит, шаблоны и повторы. Не переписывай удачные фрагменты механически и не усложняй язык.",
        "en": "Noticeable rewrite: rewrite most sentences, change syntax and word order, remove boilerplate and repetition. Every paragraph must visibly differ from the source.",
    },
    "high": {
        "ru": "Глубокая, но естественная переработка: перепиши каждое обычное предложение заново, сохраняя смысл и авторскую интонацию. Не оставляй исходные предложения дословно, кроме цитат, названий, терминов и фрагментов с точными данными. Меняй синтаксис, длину фраз и лексику, но не заменяй понятные слова сложными без причины и не добавляй искусственную образность.",
        "en": "Deep rewrite: rewrite every ordinary sentence from scratch. Do not keep source sentences verbatim except quotes, names, terms, and exact data. Change syntax, sentence length, transitions, and vocabulary; avoid repetitive constructions. Every paragraph must read as newly written while preserving the original meaning.",
    },
}

TONE_MAP = {
    "neutral": {"ru": "нейтральный, естественный и спокойный; без избыточной официальности и без разговорности", "en": "neutral, natural, and calm; neither overly formal nor colloquial"},
    "formal": {"ru": "формальный, официально-деловой, строгий", "en": "formal, official-business, strict"},
    "casual": {"ru": "живой разговорный, но грамотный; без сленга и панибратства", "en": "lively and conversational but grammatically correct; no slang or overfamiliarity"},
    "friendly": {"ru": "доброжелательный, понятный и вовлекающий, без фамильярности", "en": "friendly, clear, and engaging without overfamiliarity"},
    "academic": {"ru": "академичный, грамотный и ясный, но естественный; с сохранением нужной терминологии без канцелярита и искусственного усложнения", "en": "strictly academic, scientific, preserving terminology"},
}

STYLE_MAP = {
    "simple": {"ru": "простой и ясный: короткие понятные формулировки, активный залог там, где это уместно", "en": "simple and clear: concise phrasing and active voice where appropriate"},
    "creative": {"ru": "живой и выразительный: разнообразный ритм, точные детали и уместные образные формулировки без выдумывания фактов", "en": "lively and expressive: varied rhythm, precise details, and appropriate imagery without inventing facts"},
    "professional": {"ru": "деловой и профессиональный: точный, уверенный, без канцелярских штампов", "en": "professional and businesslike: precise, confident, and free of bureaucratic clichés"},
}

HUMANIZE_PROMPT_TEMPLATE = """Перепиши исходный текст по указанному брифу. Это не пересказ и не сокращённое изложение.

【БРИФ ОБРАБОТКИ】
Язык результата: {language}.
Тон: {tone}.
Стиль: {style}.
Количество абзацев: ровно {paragraph_count}.
Границы абзацев: {paragraph_boundary_rule}

【ТРЕБОВАНИЯ К ЭТОЙ ОБРАБОТКЕ】
1. Сохрани порядок мыслей, заголовки, списки и ровно {paragraph_count} абзацев.
2. Не удаляй, не объединяй и не дроби абзацы.
3. В списках сохрани каждый пункт, его порядок, характеристики и уточнения.
4. Не превращай осторожные предположения в категоричные утверждения.
5. Переписывай именно формулировки, а не содержание.
6. Объём результата не должен отличаться от исходного более чем на 5%.

【ИСХОДНЫЙ ТЕКСТ】
{text}
【КОНЕЦ ИСХОДНОГО ТЕКСТА】

Перед ответом проверь:
- осталось ли ровно {paragraph_count} абзацев;
- сохранены ли заголовки и списки;
- не изменились ли факты, цифры, даты, имена, цитаты, ссылки и термины;
- не изменился ли объём более чем на 5%.

Выведи только готовый текст без комментариев."""


def split_humanize_paragraphs(text: str) -> list[str]:
    """Split user text into paragraph blocks without losing single-line paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blank_line_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if len(blank_line_paragraphs) > 1:
        return blank_line_paragraphs

    non_empty_lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    return non_empty_lines or [text.strip()]


def format_humanize_prompt(text: str, tone: str, style: str, target_language: str,
                           academic_work_type: str | None = None, preserve_options: list[str] | None = None) -> str:
    """Build the Humanize prompt with the selected tone and style."""
    paragraphs = split_humanize_paragraphs(text)
    paragraph_count = len(paragraphs)
    has_single_line_paragraphs = len(paragraphs) > 1 and not re.search(r"\n\s*\n", text)
    paragraph_boundary_rule = (
        "каждая непустая строка исходника является отдельным абзацем; не объединяй строки"
        if has_single_line_paragraphs
        else "сохрани границы каждого исходного абзаца"
    )

    language = "русский" if target_language == "ru" else "английский"
    preserve_labels = {
        "numbers": "числа и даты", "terms": "термины", "sources": "ссылки и цитаты",
        "formulas": "формулы и обозначения",
    }
    prompt = HUMANIZE_PROMPT_TEMPLATE.format(
        text=text,
        language=language,
        tone=TONE_MAP[tone][target_language],
        style=STYLE_MAP[style][target_language],
        paragraph_count=paragraph_count,
        paragraph_boundary_rule=paragraph_boundary_rule,
    )
    if not academic_work_type:
        return prompt

    work_types = {
        "report": "реферат", "essay": "эссе", "presentation": "доклад",
        "coursework": "курсовая работа", "other": "учебная работа",
    }
    protected = ", ".join(preserve_labels[item] for item in (preserve_options or []) if item in preserve_labels)
    return prompt + (
        f"\n\n【УЧЕБНАЯ РАБОТА】\nТип: {work_types.get(academic_work_type, 'учебная работа')}. "
        f"Сделай текст грамотным, ясным и естественным для студенческой работы, но не усложняй его и не придавай ему обезличенный канцелярский вид. Не меняй дословно: {protected or 'точные данные и терминологию'}."
    )
