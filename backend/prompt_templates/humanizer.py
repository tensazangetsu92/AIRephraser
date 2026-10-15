"""Prompts and formatting for the Humanize tool."""

import re


COMMON_SYSTEM_PROMPTS = {
    "ru": """Ты редактируешь исходный текст.
Сохраняй смысл, порядок мыслей, факты, цифры, даты, имена, цитаты, ссылки, термины и авторскую позицию.
Не придумывай новую информацию, не сокращай текст и не меняй его структуру.
Если формулировка нужна для точности или сохранения смысла, не меняй её без необходимости.
Ответ возвращай только готовым текстом без пояснений, оценок и предисловий.""",
    "en": """You edit source text.
Preserve its meaning, order of ideas, facts, figures, dates, names, quotations, links, terms, and the author's position.
Do not invent information, shorten the text, or alter its structure.
Do not change wording that is necessary for precision or preserving the meaning.
Return only the finished text, without explanations, assessments, or introductions.""",
}


STYLE_SYSTEM_PROMPTS = {
    "human": {
        "ru": """Ты студент и перерабатываешь формулировки, которые звучат как шаблонный текст ИИ.
Пиши естественно и нейтрально: допускается небольшая простота отдельных фраз, если мысль остаётся точной.
Убирай канцелярит, шаблонные вводные конструкции и искусственную идеальность. Чередуй короткие и более развёрнутые предложения.
Сложные, но не специальные формулировки можно сделать понятнее. Не добавляй сленг, намеренные ошибки, разговорность или метафоры.""",
        "en": """You are a student revising wording that sounds like AI boilerplate.
Write naturally and neutrally: slightly simple phrasing is acceptable when the meaning stays precise.
Remove bureaucratic wording, stock introductions, and artificial perfection. Vary short and longer sentences.
You may simplify difficult non-specialist wording. Do not add slang, deliberate mistakes, colloquial language, or metaphors.""",
    },
    "literary": {
        "ru": """Ты литературный редактор.
Сделай изложение плавным, связным и выразительным за счёт точного выбора слов и естественного ритма фраз.
Убирай повторы и резкие переходы, но не добавляй метафоры, образность, оценки или эмоции, которых нет в исходнике. Не упрощай текст специально и не делай его разговорным.""",
        "en": """You are a literary editor.
Make the exposition fluent, coherent, and expressive through precise word choice and a natural sentence rhythm.
Remove repetition and abrupt transitions, but do not add metaphors, imagery, judgments, or emotions absent from the source. Do not deliberately simplify the text or make it colloquial.""",
    },
    "academic": {
        "ru": """Ты академический редактор.
Используй нейтральную учебно-научную подачу, точную терминологию из исходника и ясные логические связи.
Не упрощай значимые термины и не заменяй их бытовыми словами. Не добавляй канцелярит, громоздкие конструкции, шаблонные вводные фразы или метафоры ради формальности.""",
        "en": """You are an academic editor.
Use a neutral scholarly tone, the precise terminology already present in the source, and clear logical connections.
Do not simplify important terms or replace them with everyday wording. Do not add bureaucratic phrasing, cumbersome constructions, stock introductions, or metaphors merely to sound formal.""",
    },
}

STYLE_NAMES = {
    "human": {"ru": "человеческий", "en": "human"},
    "literary": {"ru": "литературный", "en": "literary"},
    "academic": {"ru": "академический", "en": "academic"},
}


def get_humanize_system_prompt(style: str, target_language: str) -> str:
    """Build the system prompt for the selected Humanize editing mode."""
    language = target_language if target_language in {"ru", "en"} else "ru"
    selected_style = style if style in STYLE_SYSTEM_PROMPTS else "human"
    return "\n\n".join((
        COMMON_SYSTEM_PROMPTS[language],
        STYLE_SYSTEM_PROMPTS[selected_style][language],
    ))


# Backward-compatible export. Live Humanize requests use get_humanize_system_prompt().
SYSTEM_PROMPT = COMMON_SYSTEM_PROMPTS["ru"]


HUMANIZE_PROMPT_TEMPLATE = """Перепиши исходный текст согласно выбранному режиму. Это не пересказ и не сокращённое изложение.

【БРИФ ОБРАБОТКИ】
Язык результата: {language}.
Режим редактуры: {style_name}.
Количество абзацев: ровно {paragraph_count}.
Границы абзацев: {paragraph_boundary_rule}.

【ТРЕБОВАНИЯ К ЭТОЙ ОБРАБОТКЕ】
1. Сохрани порядок мыслей, заголовки, списки и ровно {paragraph_count} абзацев.
2. Не удаляй, не объединяй и не дроби абзацы.
3. В списках сохрани каждый пункт, его порядок, характеристики и уточнения.
4. Переписывай только формулировки, а не содержание.
5. Не меняй объём текста более чем на 5%.
6. Не используй Markdown-разметку.

【ИСХОДНЫЙ ТЕКСТ】
{text}
【КОНЕЦ ИСХОДНОГО ТЕКСТА】

Перед ответом проверь:
- осталось ли ровно {paragraph_count} абзацев;
- сохранены ли заголовки и списки;
- не изменились ли факты, цифры, даты, имена, цитаты, ссылки и термины;
- не изменился ли объём более чем на 5%.

Выведи только готовый текст без комментариев."""


HUMANIZE_EN_PROMPT_TEMPLATE = """Rewrite the source text according to the selected mode. This is not a retelling or a shortened version.

[PROCESSING BRIEF]
Result language: {language}.
Editing mode: {style_name}.
Paragraph count: exactly {paragraph_count}.
Paragraph boundaries: {paragraph_boundary_rule}.

[REQUIREMENTS FOR THIS PROCESSING]
1. Preserve the order of ideas, headings, lists, and exactly {paragraph_count} paragraphs.
2. Do not delete, merge, or split paragraphs.
3. In lists, preserve every item, its order, characteristics, and qualifications.
4. Rewrite only the wording, not the content.
5. Do not change the text length by more than 5%.
6. Do not use Markdown markup.

[SOURCE TEXT]
{text}
[END OF SOURCE TEXT]

Before answering, check:
- that exactly {paragraph_count} paragraphs remain;
- that headings and lists are preserved;
- that facts, figures, dates, names, quotations, links, and terms are unchanged;
- that the length has not changed by more than 5%.

Return only the finished text without comments."""


def split_humanize_paragraphs(text: str) -> list[str]:
    """Split user text into paragraph blocks without losing single-line paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Do not use ``strip()`` here: indentation in pasted lists must reach the model.
    blank_line_paragraphs = [
        part.strip("\n")
        for part in re.split(r"\n\s*\n", normalized)
        if part.strip()
    ]
    if len(blank_line_paragraphs) > 1:
        return blank_line_paragraphs

    non_empty_lines = [line.rstrip() for line in normalized.split("\n") if line.strip()]
    return non_empty_lines or [text.strip("\r\n")]


def format_humanize_prompt(text: str, style: str, target_language: str) -> str:
    """Build the user prompt for the selected Humanize editing mode."""
    language_code = target_language if target_language in {"ru", "en"} else "ru"
    selected_style = style if style in STYLE_NAMES else "human"
    paragraphs = split_humanize_paragraphs(text)
    paragraph_count = len(paragraphs)
    has_single_line_paragraphs = len(paragraphs) > 1 and not re.search(r"\n\s*\n", text)
    paragraph_boundary_rule = (
        "каждая непустая строка исходника является отдельным абзацем; не объединяй строки"
        if has_single_line_paragraphs
        else "сохрани границы каждого исходного абзаца"
    )

    if language_code == "en":
        language = "English"
        paragraph_boundary_rule = (
            "each non-empty source line is a separate paragraph; do not merge lines"
            if has_single_line_paragraphs
            else "preserve each source paragraph boundary"
        )
    else:
        language = "русский"

    template = (
        HUMANIZE_PROMPT_TEMPLATE
        if language_code == "ru"
        else HUMANIZE_EN_PROMPT_TEMPLATE
    )
    return template.format(
        text=text,
        language=language,
        style_name=STYLE_NAMES[selected_style][language_code],
        paragraph_count=paragraph_count,
        paragraph_boundary_rule=paragraph_boundary_rule,
    )
