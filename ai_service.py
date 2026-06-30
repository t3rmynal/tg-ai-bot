"""AI client. Provider-agnostic OpenAI-style /chat/completions over aiohttp.

Two rate-limit layers: a proactive limiter spaces calls under the provider RPM,
and a reactive retry loop honours Retry-After and backs off on 429/5xx. When a
call still fails we raise RateLimited/AIError and the userbot drops the reply,
so nothing about the limit leaks into the chat.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

import config
import personas
import providers
from ratelimit import AsyncRateLimiter
from ratelimit import push as push_event

logger = logging.getLogger(__name__)

HISTORIES_FILE = "histories.json"
MAX_BACKOFF = 60.0
MAX_ATTEMPTS = 4

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


# history

def load_histories() -> None:
    global chat_histories
    if not os.path.exists(HISTORIES_FILE):
        return
    try:
        with open(HISTORIES_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        chat_histories = {int(k): v for k, v in raw.items()}
        logger.info("[AI] loaded history for %d chats", len(chat_histories))
    except Exception as e:
        logger.warning("[AI] could not read histories.json: %s", e)


def _save_histories() -> None:
    tmp = HISTORIES_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_histories.items()}, f, ensure_ascii=False)
        os.replace(tmp, HISTORIES_FILE)
    except Exception as e:
        logger.error("[AI] could not save histories.json: %s", e)


def _history_limit() -> int:
    return int(config.get("behavior.history_limit", 200) or 200)


def get_history(chat_id: int) -> list[dict]:
    return chat_histories.get(chat_id, [])


def has_history(chat_id: int) -> bool:
    return bool(chat_histories.get(chat_id))


def seed_history(chat_id: int, messages: list[dict]) -> None:
    """Backfill a chat's context once. No-op if it already has history."""
    if chat_histories.get(chat_id):
        return
    chat_histories[chat_id] = messages[-_history_limit():]
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


# response parsing

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


def _extract_reasoning(data: dict) -> str | None:
    """Pull a thinking trace out of the response if present. Logged, never sent."""
    try:
        msg = data["choices"][0].get("message", {})
    except (KeyError, IndexError):
        return None
    for key in ("reasoning", "reasoning_content", "thinking"):
        val = msg.get(key)
        if val:
            return str(val)
    return None


def _sanitize(content: str) -> str:
    return content.replace("—", "-").replace("–", "-").strip()


# rate-limit timing

def _backoff(attempt: int) -> float:
    base = min(2.0 ** attempt, MAX_BACKOFF)
    return base + random.uniform(0.0, base * 0.25)


def _retry_after(header_value: str | None, attempt: int) -> float:
    """Seconds to wait. Honour Retry-After (numeric or HTTP-date), clamp, else back off."""
    if header_value:
        value = header_value.strip()
        try:
            return min(max(0.0, float(value)), MAX_BACKOFF)
        except ValueError:
            pass
        try:
            when = parsedate_to_datetime(value)
            if when is not None:
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                delta = (when - datetime.now(timezone.utc)).total_seconds()
                return min(max(0.0, delta), MAX_BACKOFF)
        except (TypeError, ValueError):
            pass
    return _backoff(attempt)


# core call

async def _chat_completion(messages: list[dict], *, max_tokens: int, temperature: float) -> str:
    name, prov = providers.active()
    base_url = (prov.get("base_url") or "").rstrip("/")
    api_key = prov.get("api_key") or ""
    model = config.get("active_model") or ""
    if not base_url or not api_key or not model:
        raise AIError(f"provider {name} not configured (missing url/key/model)")

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if config.get("behavior.ai_thinking", False) and prov.get("supports_thinking", False):
        payload["think"] = True
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    stats["ai_calls"] += 1
    session = _get_session()

    _limiter.set_rpm(providers.active_rpm())
    waited = await _limiter.acquire()
    if waited > 0.5:
        push_event("wait", f"waiting {waited:.1f}s under {name} limit")

    url = f"{base_url}/chat/completions"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 401:
                    stats["ai_errors"] += 1
                    raise AIError("invalid API key")

                if resp.status == 429:
                    stats["rate_limited"] += 1
                    wait = _retry_after(resp.headers.get("Retry-After"), attempt)
                    logger.warning("[AI] 429, waiting %.1fs (try %d/%d)", wait, attempt, MAX_ATTEMPTS)
                    push_event("wait", f"{name} limit, waiting {wait:.0f}s")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimited(name)

                if resp.status >= 500:
                    wait = _backoff(attempt)
                    logger.warning("[AI] %d, waiting %.1fs (try %d/%d)", resp.status, wait, attempt, MAX_ATTEMPTS)
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(wait)
                        continue
                    stats["ai_errors"] += 1
                    raise AIError(f"server returned {resp.status}")

                if resp.status >= 400:
                    body = (await resp.text())[:200]
                    stats["ai_errors"] += 1
                    raise AIError(f"HTTP {resp.status}: {body}")

                data = await resp.json()
                content = _parse_ai_response(data)
                if not content:
                    stats["ai_errors"] += 1
                    raise AIError(f"unexpected response shape: {str(data)[:200]}")

                reasoning = _extract_reasoning(data)
                if reasoning:
                    logger.info("[AI] thinking:\n%s", reasoning)
                    push_event("info", f"thought: {reasoning[:60]}")

                return _sanitize(content)

        except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
            wait = _backoff(attempt)
            logger.warning("[AI] network: %s, waiting %.1fs (try %d/%d)", e, wait, attempt, MAX_ATTEMPTS)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(wait)
                continue
            stats["ai_errors"] += 1
            raise AIError("no connection to provider") from e
        except aiohttp.ClientError as e:
            stats["ai_errors"] += 1
            raise AIError(f"client error: {e}") from e

    raise AIError("retries exhausted")


async def ask_ai(chat_id: int, user_message: str, extra_context: str = "") -> str:
    if not user_message or not user_message.strip():
        raise AIError("empty message")
    user_message = user_message.strip()

    system = personas.render()
    if extra_context.strip():
        system += f"\n\nextra context: {extra_context.strip()}"

    messages = [
        {"role": "system", "content": system},
        *get_history(chat_id),
        {"role": "user", "content": user_message},
    ]
    content = await _chat_completion(
        messages,
        max_tokens=config.get("behavior.ai_max_tokens", 500),
        temperature=config.get("behavior.ai_temperature", 0.85),
    )
    add_to_history(chat_id, "user", user_message)
    add_to_history(chat_id, "assistant", content)
    stats["messages_processed"] += 1
    return content


async def generate_system_prompt(name: str, kind: str, tone: str, lang: str, extra: str = "") -> str:
    """Ask the active provider to write a persona system prompt. Falls back offline."""
    label = personas.language_label(lang)
    acts = "a real person (never admits being an AI)" if kind == "human" else "an AI assistant (honest about being one)"
    spec = (
        f"Name: {name or 'the bot'}\n"
        f"Acts as: {acts}\n"
        f"Tone and personality: {tone or 'natural and friendly'}\n"
        f"Extra flavor: {extra or 'none'}\n"
        f"Reply language: {label}"
    )
    meta = (
        "You are an expert prompt engineer. Write a system prompt for a Telegram "
        "chat persona from the spec below. Write in the second person ('you are...'), "
        "keep it concise and concrete, output only the prompt with no markdown, no "
        "preamble, and no long dashes. Spec:\n\n" + spec
    )
    try:
        out = await _chat_completion(
            [{"role": "system", "content": meta}],
            max_tokens=600,
            temperature=0.9,
        )
    except (AIError, RateLimited):
        return personas.build_custom(name, kind, tone, lang, extra)

    out = out.strip()
    if personas._GUARDRAILS not in out:
        out += "\n" + personas._GUARDRAILS
    lang_line = f"reply in {label}."
    if lang_line.lower() not in out.lower():
        out += "\n" + lang_line
    return _sanitize(out)
