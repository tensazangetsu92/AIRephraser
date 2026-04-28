from openai import AsyncOpenAI
import asyncio

from app.config import OPENROUTER_API_KEY, MODEL_NAME, TEMPERATURE
from prompts import (
    SYSTEM_PROMPT,
    get_rewrite_prompt,
    get_humanize_prompt
)

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


async def ask_llm(prompt: str, text: str, temperature: float = None):
    """Универсальная функция запроса к LLM"""
    if temperature is None:
        temperature = OPENROUTER_CONFIG["temperature"]

    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_CONFIG["model"],
            temperature=temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt + text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in ask_llm: {e}")
        return text


async def humanize_pipeline(text: str, intensity: str, tone: str, style: str, length: str, target_language: str = "ru"):
    """
    Основной пайплайн обработки текста

    Args:
        text: исходный текст
        intensity: сила изменения (low, medium, high)
        tone: тон (neutral, formal, casual, friendly, academic)
        style: стиль (simple, creative, professional)
        length: длина (same, shorter, longer)
        target_language: целевой язык (ru, en)

    Returns:
        обработанный текст
    """
    print(
        f"Processing text with params: intensity={intensity}, tone={tone}, style={style}, length={length}, lang={target_language}")

    # Шаг 1: переписывание с учетом параметров
    rewrite_prompt = get_rewrite_prompt(intensity, tone, style, length, target_language)
    step1 = await ask_llm(rewrite_prompt, text)
    print("Step 1 completed (rewrite)")

    # Шаг 2: очеловечивание (финальный результат)
    humanize_prompt = get_humanize_prompt(intensity, tone, style, length, target_language)
    final = await ask_llm(humanize_prompt, step1)
    print("Step 2 completed (humanize)")

    return final


async def test():
    """Тестовая функция"""
    question = """В глубинах океана скрывается мир, который человечество изучило хуже, чем поверхность Марса. 
    Температура там близка к нулю, а давление способно раздавить привычный батискаф, словно консервную банку. 
    Несмотря на это, жизнь в бездне не только существует, но и процветает в самых неожиданных формах."""

    print("=" * 50)
    print("Тест: Слабая сила, дружелюбный тон, простой стиль, длиннее")
    print("=" * 50)
    result = await humanize_pipeline(
        text=question,
        intensity="high",
        tone="friendly",
        style="simple",
        length="longer",
        target_language="ru"
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(test())