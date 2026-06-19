# llm.py - оптимизированная версия с одним запросом

from openai import AsyncOpenAI
import asyncio
import json

from app.config import OPENROUTER_API_KEY, MODEL_NAME, TEMPERATURE
from prompts import SYSTEM_PROMPT, format_humanize_prompt, DETECTOR_SYSTEM_PROMPT, format_detector_prompt

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

OPENROUTER_CONFIG = {
    "api_key": OPENROUTER_API_KEY,
    "base_url": "https://openrouter.ai/api/v1",
    "model": MODEL_NAME,
    "temperature": TEMPERATURE
}

# Словарь для разных моделей (можно выбрать лучшую)
MODELS = {
    "best": "anthropic/claude-3.5-sonnet",  # Лучший для русского языка
    "good": "openai/gpt-4-turbo",  # Хороший, но дороже
    "cheap": "meta-llama/llama-3-70b-instruct",  # Дешёвый
    "fast": "google/gemini-2.0-flash-exp:free"  # Быстрый и бесплатный
}


async def ask_llm(text: str, intensity: str, tone: str, style: str, length: str, target_language: str,
                  temperature: float = 0.7):
    """Универсальный запрос к LLM с корректным промптом"""

    # Форматируем промпт с текстом
    prompt = format_humanize_prompt(text, intensity, tone, style, length, target_language)

    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_CONFIG["model"],
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


async def humanize_pipeline(text: str, intensity: str, tone: str, style: str, length: str, target_language: str = "ru"):
    """Основной пайплайн обработки текста с проверкой длины"""

    original_length = len(text)
    print(f"Оригинал: {original_length} символов")

    # Один запрос
    prompt = format_humanize_prompt(text, intensity, tone, style, length, target_language)

    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_CONFIG["model"],
            temperature=0.5,  # Низкая температура для точности
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()

        # ПРОВЕРКА ДЛИНЫ
        result_length = len(result)
        print(f"Результат: {result_length} символов")

        # Если результат слишком короткий - отправляем повторно с жестким требованием
        if result_length < original_length * 0.7:
            print(f"⚠️ Результат слишком короткий! Повторная попытка...")

            fallback_prompt = f"""ТЫ НЕ ПРАВИЛЬНО ВЫПОЛНИЛ ЗАДАНИЕ!

Ты сильно сократил текст. Было {original_length} символов, стало {result_length}.

ПЕРЕДЕЛАЙ ТЕКСТ ЗАНОВО, СТРОГО СОБЛЮДАЯ ПРАВИЛА:

1. КАЖДЫЙ абзац из оригинала должен быть в ответе
2. КАЖДЫЙ заголовок - должен быть
3. НИЧЕГО НЕ УДАЛЯЙ

Вот исходный текст, который ты должен обработать:

{text}

Сделай так, чтобы длина результата была примерно {original_length} символов (плюс-минус 15%).

ОТВЕТЬ ТОЛЬКО ГОТОВЫМ ТЕКСТОМ."""

            response2 = await client.chat.completions.create(
                model=OPENROUTER_CONFIG["model"],
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "Ты редактор. ОБЯЗАН сохранить всю информацию и структуру текста."},
                    {"role": "user", "content": fallback_prompt}
                ]
            )
            result = response2.choices[0].message.content.strip()
            print(f"Результат после повторной попытки: {len(result)} символов")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return text


async def detect_ai_pipeline(text: str) -> dict:
    """Анализирует текст и возвращает вероятность того, что он написан ИИ, с разметкой по предложениям"""

    prompt = format_detector_prompt(text)
    raw_result = None

    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_CONFIG["model"],
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

        # Удаляем строки-заглушки "..." которые ломают JSON
        import re
        cleaned = re.sub(r',?\s*\n\s*\.\.\.\s*\n', '\n', cleaned)
        cleaned = re.sub(r',\s*\.\.\.\s*]', ']', cleaned)

        parsed = json.loads(cleaned)

        # Валидация меток предложений
        sentences = parsed.get("sentences", [])
        valid_labels = {"human", "mixed", "ai"}
        clean_sentences = []
        for s in sentences:
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
        return {
            "ai_probability": 33,
            "human_probability": 34,
            "mixed_probability": 33,
            "verdict": "Ошибка анализа",
            "explanation": "Не удалось проанализировать текст из-за технической ошибки.",
            "sentences": [{"text": text, "label": "mixed"}]
        }


def get_available_models():
    """Получить список доступных моделей"""
    return MODELS


def set_model(model_key: str):
    """Сменить модель"""
    if model_key in MODELS:
        OPENROUTER_CONFIG["model"] = MODELS[model_key]
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
        intensity="medium",
        tone="neutral",
        style="simple",
        length="same",
        target_language="ru"
    )

    print("\n📝 ОРИГИНАЛ:")
    print(test_text)
    print("\n✨ РЕЗУЛЬТАТ:")
    print(result)
    print(f"\n📊 Статистика: {len(test_text)} → {len(result)} символов")


if __name__ == "__main__":
    asyncio.run(test())