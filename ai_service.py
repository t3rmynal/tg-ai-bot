import asyncio
import json
import logging
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

KILOCODE_API_KEY = os.getenv("KILOCODE_API_KEY")
KILOCODE_URL = "https://api.kilo.ai/api/gateway/chat/completions"

SYSTEM_PROMPT = """ты - живой человек по имени {bot_name}. общаешься как реальный человек в телеграме (смешной и остроумный, а не как формальный ассистент)
"""

HISTORIES_FILE = "histories.json"
MAX_HISTORY = 20

chat_histories: dict[int, list[dict]] = {}

stats = {
    "ai_calls": 0,
    "ai_errors": 0,
    "messages_processed": 0,
}

_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_session() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

def load_histories() -> None:
    global chat_histories
    if not os.path.exists(HISTORIES_FILE):
        return
    try:
        with open(HISTORIES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        chat_histories = {int(k): v for k, v in raw.items()}
        logger.info(f"[AI] Загружена история {len(chat_histories)} чатов")
    except Exception as e:
        logger.warning(f"[AI] Не удалось загрузить histories.json: {e}")


def _save_histories() -> None:
    tmp = HISTORIES_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_histories.items()}, f, ensure_ascii=False)
        os.replace(tmp, HISTORIES_FILE)
    except Exception as e:
        logger.error(f"[AI] Ошибка сохранения histories.json: {e}")


def get_history(chat_id: int) -> list[dict]:
    return chat_histories.get(chat_id, [])


def add_to_history(chat_id: int, role: str, content: str) -> None:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    chat_histories[chat_id].append({"role": role, "content": content})
    if len(chat_histories[chat_id]) > MAX_HISTORY:
        chat_histories[chat_id] = chat_histories[chat_id][-MAX_HISTORY:]
    _save_histories()


def clear_history(chat_id: int) -> None:
    if chat_id in chat_histories:
        del chat_histories[chat_id]
        _save_histories()

def _parse_ai_response(data: dict) -> str | None:
    if "choices" in data and data["choices"]:
        choice = data["choices"][0]
        if "message" in choice:
            content = choice["message"].get("content")
            if content:
                return content
        if "text" in choice:
            return choice["text"]
    if "data" in data:
        nested = data["data"]
        if "choices" in nested and nested["choices"]:
            choice = nested["choices"][0]
            if "message" in choice:
                return choice["message"].get("content")
    if "content" in data:
        return data["content"]
    if "text" in data:
        return data["text"]
    return None

async def ask_ai(
    chat_id: int,
    user_message: str,
    bot_name: str | None = None,
    extra_context: str = "",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    import storage

    if not user_message or not user_message.strip():
        raise ValueError("Сообщение не может быть пустым")

    user_message = user_message.strip()
    bot_name = bot_name.strip() if bot_name else "бот"

    _max_tokens = max_tokens if max_tokens is not None else storage.get("ai_max_tokens")
    _temperature = temperature if temperature is not None else storage.get("ai_temperature")
    _model = storage.get("ai_model")

    add_to_history(chat_id, "user", user_message)

    system = SYSTEM_PROMPT.format(bot_name=bot_name)
    if extra_context and extra_context.strip():
        system += f"\n\nДополнительный контекст: {extra_context.strip()}"

    history = get_history(chat_id)
    messages = [{"role": "system", "content": system}, *history]

    payload = {
        "model": _model,
        "messages": messages,
        "max_tokens": _max_tokens,
        "temperature": _temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {KILOCODE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    stats["ai_calls"] += 1
    session = _get_session()

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            async with session.post(
                KILOCODE_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 401:
                    logger.error("[AI] Неверный API ключ")
                    stats["ai_errors"] += 1
                    return "ошибка авторизации, проверь api ключ"

                if resp.status == 429:
                    wait = 2 ** attempt
                    logger.warning(f"[AI] Лимит запросов (429), жду {wait}s, попытка {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
                        continue
                    stats["ai_errors"] += 1
                    return "слишком много запросов, попробуй позже"

                if resp.status >= 500:
                    wait = 2 ** attempt
                    logger.warning(f"[AI] Серверная ошибка {resp.status}, жду {wait}s, попытка {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
                        continue
                    stats["ai_errors"] += 1
                    return "сервис временно недоступен, попробуй позже"

                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"[AI] HTTP {resp.status}: {error_text[:200]}")
                    stats["ai_errors"] += 1
                    return "ошибка при обработке запроса"

                data = await resp.json()
                content = _parse_ai_response(data)

                if not content:
                    logger.warning(f"[AI] Неизвестный формат ответа: {str(data)[:300]}")
                    stats["ai_errors"] += 1
                    return "не удалось обработать ответ, переформулируй"

                content = content.replace("—", "-").replace("–", "-")
                add_to_history(chat_id, "assistant", content)
                stats["messages_processed"] += 1
                return content

        except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
            wait = 2 ** attempt
            logger.warning(f"[AI] Сетевая ошибка: {e}, жду {wait}s, попытка {attempt}/{max_attempts}")
            if attempt < max_attempts:
                await asyncio.sleep(wait)
        except aiohttp.ClientError as e:
            logger.error(f"[AI] Ошибка клиента: {e}")
            stats["ai_errors"] += 1
            return "ошибка при отправке запроса"
        except Exception as e:
            logger.error(f"[AI] Непредвиденная ошибка: {type(e).__name__}: {e}")
            stats["ai_errors"] += 1
            return "произошла непредвиденная ошибка"

    stats["ai_errors"] += 1
    return "нет подключения к интернету или сервис недоступен"
