"""AI client.

Provider-agnostic: it reads the active provider's base_url, key and model from
config and posts an OpenAI-style ``/chat/completions`` request. The system prompt
comes from the selected persona.

Rate limiting works in two layers:
  - proactive: every call waits on a shared limiter so we stay under the provider's
    requests-per-minute cap;
  - reactive: on a 429 we honour Retry-After (or back off) and retry. If it still
    won't go through, we raise RateLimited and the userbot quietly skips the reply -
    nothing about the rate limit leaks into the chat. The next message tries again.
"""

import asyncio
import json
import logging
import os

import aiohttp

import config
import personas
import providers
from ratelimit import AsyncRateLimiter
from ratelimit import push as push_event

logger = logging.getLogger(__name__)

HISTORIES_FILE = "histories.json"

chat_histories: dict[int, list[dict]] = {}

stats = {
    "ai_calls": 0,
    "ai_errors": 0,
    "messages_processed": 0,
    "rate_limited": 0,
}

_session: aiohttp.ClientSession | None = None
_limiter = AsyncRateLimiter(40)


class RateLimited(Exception):
    """Provider kept returning 429 after our retries."""


class AIError(Exception):
    """Any other failure we don't want to surface into the chat."""


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
        with open(HISTORIES_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        chat_histories = {int(k): v for k, v in raw.items()}
        logger.info("[AI] загружена история %d чатов", len(chat_histories))
    except Exception as e:
        logger.warning("[AI] не смог прочитать histories.json: %s", e)


def _save_histories() -> None:
    tmp = HISTORIES_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_histories.items()}, f, ensure_ascii=False)
        os.replace(tmp, HISTORIES_FILE)
    except Exception as e:
        logger.error("[AI] не смог сохранить histories.json: %s", e)


def _history_limit() -> int:
    return int(config.get("behavior.history_limit", 200) or 200)


def get_history(chat_id: int) -> list[dict]:
    return chat_histories.get(chat_id, [])


def has_history(chat_id: int) -> bool:
    return bool(chat_histories.get(chat_id))


def seed_history(chat_id: int, messages: list[dict]) -> None:
    """Backfill a chat's context once (used when adding a chat). No-op if it
    already has history."""
    if chat_histories.get(chat_id):
        return
    limit = _history_limit()
    chat_histories[chat_id] = messages[-limit:]
    _save_histories()


def add_to_history(chat_id: int, role: str, content: str) -> None:
    chat_histories.setdefault(chat_id, []).append({"role": role, "content": content})
    limit = _history_limit()
    if len(chat_histories[chat_id]) > limit:
        chat_histories[chat_id] = chat_histories[chat_id][-limit:]
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


def _retry_after(header_value: str | None, attempt: int) -> float:
    """Seconds to wait before the next try. Honour Retry-After if it's a number,
    otherwise back off exponentially."""
    if header_value:
        try:
            return max(0.0, float(header_value))
        except ValueError:
            pass
    return float(2 ** attempt)


async def ask_ai(chat_id: int, user_message: str, extra_context: str = "") -> str:
    if not user_message or not user_message.strip():
        raise AIError("пустое сообщение")

    user_message = user_message.strip()

    name, prov = providers.active()
    base_url = (prov.get("base_url") or "").rstrip("/")
    api_key = prov.get("api_key") or ""
    model = config.get("active_model") or ""
    if not base_url or not api_key or not model:
        raise AIError(f"провайдер {name} не настроен (нет url/ключа/модели)")

    url = f"{base_url}/chat/completions"
    system = personas.render()
    if extra_context.strip():
        system += f"\n\nдополнительный контекст: {extra_context.strip()}"

    messages = [
        {"role": "system", "content": system},
        *get_history(chat_id),
        {"role": "user", "content": user_message},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": config.get("behavior.ai_max_tokens", 500),
        "temperature": config.get("behavior.ai_temperature", 0.85),
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    stats["ai_calls"] += 1
    session = _get_session()

    # proactive spacing so we stay under the provider's RPM
    _limiter.set_rpm(providers.active_rpm())
    waited = await _limiter.acquire()
    if waited > 0.5:
        push_event("wait", f"жду {waited:.1f}с под лимит {name}")

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 401:
                    stats["ai_errors"] += 1
                    raise AIError("неверный API-ключ")

                if resp.status == 429:
                    stats["rate_limited"] += 1
                    wait = _retry_after(resp.headers.get("Retry-After"), attempt)
                    logger.warning("[AI] 429, жду %.1fс (попытка %d/%d)", wait, attempt, max_attempts)
                    push_event("wait", f"лимит {name}, жду {wait:.0f}с")
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimited(name)

                if resp.status >= 500:
                    wait = float(2 ** attempt)
                    logger.warning("[AI] %d, жду %.1fс (попытка %d/%d)", resp.status, wait, attempt, max_attempts)
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
                        continue
                    stats["ai_errors"] += 1
                    raise AIError(f"сервер вернул {resp.status}")

                if resp.status >= 400:
                    body = (await resp.text())[:200]
                    stats["ai_errors"] += 1
                    raise AIError(f"HTTP {resp.status}: {body}")

                data = await resp.json()
                content = _parse_ai_response(data)
                if not content:
                    stats["ai_errors"] += 1
                    raise AIError(f"непонятный формат ответа: {str(data)[:200]}")

                content = content.replace("—", "-").replace("–", "-").strip()
                add_to_history(chat_id, "user", user_message)
                add_to_history(chat_id, "assistant", content)
                stats["messages_processed"] += 1
                return content

        except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
            wait = float(2 ** attempt)
            logger.warning("[AI] сеть: %s, жду %.1fс (попытка %d/%d)", e, wait, attempt, max_attempts)
            if attempt < max_attempts:
                await asyncio.sleep(wait)
                continue
            stats["ai_errors"] += 1
            raise AIError("нет связи с провайдером") from e
        except aiohttp.ClientError as e:
            stats["ai_errors"] += 1
            raise AIError(f"ошибка клиента: {e}") from e

    raise AIError("исчерпаны попытки")
