"""Prompt templates for the Study Work tool."""

import json


STUDY_WORK_DOCX_SYSTEM_PROMPT = """Ты редактор учебных текстов. Возвращай только корректный JSON без пояснений."""

STUDY_WORK_HUMANIZE_PROMPT_TEMPLATE = """【УЧЕБНАЯ РАБОТА】
Тип: {work_type}.
{work_type_rules}
Сделай текст грамотным, ясным и естественным для студенческой работы, но не усложняй его и не придавай ему обезличенный канцелярский вид.
Передай содержание каждого самостоятельного предложения исходника: не выбрасывай определения, пояснения, выводы и причинно-следственные связи даже при сокращении формулировки.
Не меняй дословно: {protected_text}."""

STUDY_WORK_DOCX_BATCH_PROMPT_TEMPLATE = """Отредактируй абзацы {work_type}. {work_type_rules}
Язык результата: {language}.
Нужен ясный академический стиль, понятный студенту.
ЗАМЕТНО перепиши каждое обычное предложение, а не меняй отдельные слова.
Используй короткие и средние предложения с прямым порядком слов. Длинные предложения с несколькими оборотами и придаточными при необходимости разделяй на два. Убирай канцелярит, пустые вводные фразы и шаблоны вроде «следует отметить», «в рамках данного», «осуществляется». Заменяй слишком сложные нетерминологические слова на более простые и точные.

Не переходи в разговорный стиль, не упрощай научные термины, не добавляй новые факты и не сокращай смысл. Сохраняй логику, аргументы и объём каждого абзаца. Содержание каждого самостоятельного исходного предложения должно остаться в результате: не удаляй определения, пояснения, выводы, примеры и причинно-следственные связи. Не объединяй несколько исходных предложений так, чтобы хотя бы одна мысль исчезла. Не меняй: {protected_text}.
Не используй Markdown-разметку.

КРИТИЧЕСКОЕ ПРАВИЛО: верни только JSON-массив. В нём должны быть все исходные id строго по порядку и ровно по одному разу. Не добавляй, не удаляй и не объединяй элементы. Изменяй только поле text.

Входной JSON:
{payload}"""

_WORK_TYPES = {
    "report": "реферат",
    "essay": "эссе",
    "presentation": "доклад",
    "coursework": "курсовая работа",
    "other": "учебная работа",
}

_DOCX_WORK_TYPES = {
    "report": "реферата",
    "essay": "эссе",
    "presentation": "доклада",
    "coursework": "курсовой работы",
    "other": "учебной работы",
}

WORK_TYPE_RULES = {
    "report": (
        "Для реферата сохраняй нейтральный обзорный тон. Не добавляй личную позицию "
        "и не превращай изложение источников в спор или оценку."
    ),
    "essay": (
        "Для эссе сохраняй авторскую позицию, оценочные формулировки и ход рассуждения, "
        "если они есть в исходнике. Не добавляй новую позицию или личный опыт от себя."
    ),
    "presentation": (
        "Для доклада сохраняй ясную последовательность мысли и формулировки, удобные для "
        "восприятия на слух. Не добавляй обращения к аудитории и не сокращай содержание."
    ),
    "coursework": (
        "Для курсовой работы сохраняй строгий учебно-научный тон, логику аргументации, "
        "термины, ссылки на источники, таблицы и рисунки."
    ),
    "other": (
        "Для другой учебной работы придерживайся нейтрального, грамотного учебного стиля."
    ),
}


PROTECTED_TEXT = "числа и даты, термины, ссылки и цитаты, формулы и обозначения"


def format_study_work_humanize_prompt(
        base_prompt: str,
        academic_work_type: str,
) -> str:
    """Add Study Work rules to the shared Humanize prompt."""
    return base_prompt + "\n\n" + STUDY_WORK_HUMANIZE_PROMPT_TEMPLATE.format(
        work_type=_WORK_TYPES.get(academic_work_type, "учебная работа"),
        work_type_rules=WORK_TYPE_RULES.get(academic_work_type, WORK_TYPE_RULES["other"]),
        protected_text=PROTECTED_TEXT,
    )


def format_study_work_docx_batch_prompt(
        items: list[dict],
        academic_work_type: str,
        target_language: str = "ru",
) -> str:
    """Build the one-to-one JSON rewrite prompt for Study Work DOCX paragraphs."""
    payload = json.dumps(items, ensure_ascii=False)
    work_type_label = _DOCX_WORK_TYPES.get(academic_work_type, "учебной работы")
    language = "русский" if target_language == "ru" else "английский"
    return STUDY_WORK_DOCX_BATCH_PROMPT_TEMPLATE.format(
        work_type=work_type_label,
        work_type_rules=WORK_TYPE_RULES.get(academic_work_type, WORK_TYPE_RULES["other"]),
        protected_text=PROTECTED_TEXT,
        payload=payload,
        language=language,
    )
