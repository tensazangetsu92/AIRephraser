# prompts.py - файл со всеми промптами

# Системный промпт (общий для всех запросов)
SYSTEM_PROMPT = "Ты профессиональный редактор текстов. Сохраняй смысл и структуру оригинального текста."

# Карты для маппинга параметров
INTENSITY_MAP = {
    "low": {
        "ru": "слабая (минимальные изменения, сохрани почти всё как есть)",
        "en": "low (minimal changes, keep almost everything as is)"
    },
    "medium": {
        "ru": "нормальная (умеренные изменения, сделай текст более естественным)",
        "en": "medium (moderate changes, make text more natural)"
    },
    "high": {
        "ru": "сильная (полная переработка, сделай текст максимально человечным)",
        "en": "high (complete rewrite, make text as human as possible)"
    }
}

TONE_MAP = {
    "neutral": {
        "ru": "нейтральный, объективный",
        "en": "neutral, objective"
    },
    "formal": {
        "ru": "формальный, официально-деловой",
        "en": "formal, official-business"
    },
    "casual": {
        "ru": "повседневный, разговорный",
        "en": "casual, conversational"
    },
    "friendly": {
        "ru": "дружелюбный, тёплый",
        "en": "friendly, warm"
    },
    "academic": {
        "ru": "академический, научный",
        "en": "academic, scholarly"
    }
}

STYLE_MAP = {
    "simple": {
        "ru": "простой, лёгкий для понимания",
        "en": "simple, easy to understand"
    },
    "creative": {
        "ru": "креативный, с необычными оборотами",
        "en": "creative, with unusual turns"
    },
    "professional": {
        "ru": "профессиональный, деловой",
        "en": "professional, business-like"
    }
}

LENGTH_MAP = {
    "same": {
        "ru": "сохрани исходную длину",
        "en": "keep the original length"
    },
    "shorter": {
        "ru": "сделай короче, убери лишнее",
        "en": "make shorter, remove unnecessary"
    },
    "longer": {
        "ru": "сделай длиннее, добавь деталей",
        "en": "make longer, add details"
    }
}

LANGUAGE_MAP = {
    "ru": "русском",
    "en": "английском"
}

# Промпт для переписывания с учетом всех параметров
REWRITE_PROMPT_TEMPLATE = """
Перепиши текст с следующими параметрами:

Сила изменения: {intensity}
Тон: {tone}
Стиль: {style}
Длина: {length}
Язык: {language}

ОБЯЗАТЕЛЬНО:
- сохрани основной смысл
- не добавляй вымышленную информацию
- сохрани ключевые факты
- следуй указанным выше параметрам

Текст для обработки:
"""

# Промпт для очеловечивания
HUMANIZE_PROMPT_TEMPLATE = """
Сделай текст более естественным и человеческим.

Параметры:
- Сила изменения: {intensity}
- Тон: {tone}
- Стиль: {style}
- Длина: {length}
- Язык: {language}

ОБЯЗАТЕЛЬНО:
- сохрани смысл
- сделай язык живым и естественным
- убери излишнюю формальность (если нужно)
- следуй параметрам обработки
- в ответ пиши ТОЛЬКО ТЕКСТ
- Текст должен получиться на языке {language}

Текст:
"""

# Функции для получения промптов с параметрами
def get_rewrite_prompt(intensity: str, tone: str, style: str, length: str, target_language: str):
    """Получить промпт для переписывания текста"""
    return REWRITE_PROMPT_TEMPLATE.format(
        intensity=INTENSITY_MAP[intensity][target_language],
        tone=TONE_MAP[tone][target_language],
        style=STYLE_MAP[style][target_language],
        length=LENGTH_MAP[length][target_language],
        language=LANGUAGE_MAP[target_language]
    )

def get_humanize_prompt(intensity: str, tone: str, style: str, length: str, target_language: str):
    """Получить промпт для очеловечивания текста"""
    return HUMANIZE_PROMPT_TEMPLATE.format(
        intensity=INTENSITY_MAP[intensity][target_language],
        tone=TONE_MAP[tone][target_language],
        style=STYLE_MAP[style][target_language],
        length=LENGTH_MAP[length][target_language],
        language=LANGUAGE_MAP[target_language]
    )


