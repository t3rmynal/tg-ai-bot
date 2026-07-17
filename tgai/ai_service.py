"""AI client. Provider-agnostic OpenAI-style /chat/completions over aiohttp.

Two rate-limit layers: a proactive limiter spaces calls under the provider RPM,
and a reactive retry loop honours Retry-After and backs off on 429/5xx. When a
call still fails we raise RateLimited/AIError and the bot drops the reply, so
nothing about the limit leaks into the chat.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

from tgai import personas, providers
from tgai.config import ConfigStore
from tgai.personas import Identity
from tgai.proxy import ProxyManager
from tgai.ratelimit import ActivityFeed, AsyncRateLimiter

logger = logging.getLogger(__name__)

MAX_BACKOFF = 60.0
MAX_ATTEMPTS = 4


class RateLimited(Exception):
    """Provider kept returning 429 after our retries."""


class AIError(Exception):
    """Any other failure we don't want to surface into the chat."""


# response parsing (pure helpers, unit-tested directly)

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
    return content.replace("\u2014", "-").replace("\u2013", "-").strip()


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


class AIService:
    """Chat completions, per-chat history, stats. One instance per app."""

    def __init__(
        self,
        cfg: ConfigStore,
        feed: ActivityFeed,
        identity: Identity,
        histories_path: str = "histories.json",
        session_factory=aiohttp.ClientSession,
        proxy: ProxyManager | None = None,
    ):
        self.cfg = cfg
        self.feed = feed
        self.identity = identity
        self.histories_path = histories_path
        self._session_factory = session_factory
        self.proxy = proxy
        # sessions cached per proxy url, "direct" for no proxy
        self._sessions: dict[str, aiohttp.ClientSession] = {}
        self.limiter = AsyncRateLimiter(40)
        self.histories: dict[int, list[dict]] = {}
        self.stats = {
            "ai_calls": 0,
            "ai_errors": 0,
            "messages_processed": 0,
            "rate_limited": 0,
        }

    def get_session(self, proxy=None) -> aiohttp.ClientSession:
        """Session for the given proxy (or direct). One session cached per proxy."""
        key = proxy.url if proxy else "direct"
        s = self._sessions.get(key)
        if s is None or s.closed:
            if proxy is not None:
                from aiohttp_socks import ProxyConnector

                s = aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy.url))
            else:
                s = self._session_factory()
            self._sessions[key] = s
        return s

    async def close(self) -> None:
        for s in self._sessions.values():
            if not s.closed:
                await s.close()
        self._sessions.clear()

    # history

    def load_histories(self) -> None:
        if not os.path.exists(self.histories_path):
            return
        try:
            with open(self.histories_path, encoding="utf-8") as f:
                raw = json.load(f)
            self.histories = {int(k): v for k, v in raw.items()}
            logger.info("[AI] loaded history for %d chats", len(self.histories))
        except Exception as e:
            logger.warning("[AI] could not read %s: %s", self.histories_path, e)

    def _save_histories(self) -> None:
        tmp = self.histories_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in self.histories.items()}, f, ensure_ascii=False)
            os.replace(tmp, self.histories_path)
        except Exception as e:
            logger.error("[AI] could not save %s: %s", self.histories_path, e)

    def _history_limit(self) -> int:
        return int(self.cfg.get("behavior.history_limit", 200) or 200)

    def get_history(self, chat_id: int) -> list[dict]:
        return self.histories.get(chat_id, [])

    def has_history(self, chat_id: int) -> bool:
        return bool(self.histories.get(chat_id))

    def seed_history(self, chat_id: int, messages: list[dict]) -> None:
        """Backfill a chat's context once. No-op if it already has history."""
        if self.histories.get(chat_id):
            return
        self.histories[chat_id] = messages[-self._history_limit():]
        self._save_histories()

    def add_to_history(self, chat_id: int, role: str, content: str) -> None:
        self.histories.setdefault(chat_id, []).append({"role": role, "content": content})
        limit = self._history_limit()
        if len(self.histories[chat_id]) > limit:
            self.histories[chat_id] = self.histories[chat_id][-limit:]
        self._save_histories()

    def clear_history(self, chat_id: int) -> bool:
        if chat_id in self.histories:
            del self.histories[chat_id]
            self._save_histories()
            return True
        return False

    # core call

    async def _chat_completion(self, messages: list[dict], *, max_tokens: int, temperature: float) -> str:
        name, prov = providers.active(self.cfg)
        base_url = (prov.get("base_url") or "").rstrip("/")
        api_key = prov.get("api_key") or ""
        model = self.cfg.get("active_model") or ""
        if not base_url or not api_key or not model:
            raise AIError(f"provider {name} not configured (missing url/key/model)")

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if self.cfg.get("behavior.ai_thinking", False) and prov.get("supports_thinking", False):
            payload["think"] = True
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.stats["ai_calls"] += 1
        proxy = self.proxy.next_for_request() if self.proxy else None
        if proxy is not None and self.proxy.took_new_proxy(proxy):
            self.feed.push("info", f"routing through {proxy.masked()}")
        session = self.get_session(proxy)

        self.limiter.set_rpm(providers.active_rpm(self.cfg))
        waited = await self.limiter.acquire()
        if waited > 0.5:
            self.feed.push("wait", f"waiting {waited:.1f}s under {name} limit")

        url = f"{base_url}/chat/completions"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with session.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 401:
                        self.stats["ai_errors"] += 1
                        raise AIError("invalid API key")

                    if resp.status == 429:
                        self.stats["rate_limited"] += 1
                        wait = _retry_after(resp.headers.get("Retry-After"), attempt)
                        logger.warning("[AI] 429, waiting %.1fs (try %d/%d)", wait, attempt, MAX_ATTEMPTS)
                        self.feed.push("wait", f"{name} limit, waiting {wait:.0f}s")
                        if attempt < MAX_ATTEMPTS:
                            await asyncio.sleep(wait)
                            continue
                        raise RateLimited(name)

                    if resp.status >= 500:
                        wait = _backoff(attempt)
                        logger.warning(
                            "[AI] %d, waiting %.1fs (try %d/%d)", resp.status, wait, attempt, MAX_ATTEMPTS,
                        )
                        if attempt < MAX_ATTEMPTS:
                            await asyncio.sleep(wait)
                            continue
                        self.stats["ai_errors"] += 1
                        raise AIError(f"server returned {resp.status}")

                    if resp.status >= 400:
                        body = (await resp.text())[:200]
                        self.stats["ai_errors"] += 1
                        raise AIError(f"HTTP {resp.status}: {body}")

                    data = await resp.json()
                    content = _parse_ai_response(data)
                    if not content:
                        self.stats["ai_errors"] += 1
                        raise AIError(f"unexpected response shape: {str(data)[:200]}")

                    reasoning = _extract_reasoning(data)
                    if reasoning:
                        logger.info("[AI] thinking:\n%s", reasoning)
                        self.feed.push("info", f"thought: {reasoning[:60]}")

                    return _sanitize(content)

            except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
                wait = _backoff(attempt)
                logger.warning("[AI] network: %s, waiting %.1fs (try %d/%d)", e, wait, attempt, MAX_ATTEMPTS)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(wait)
                    continue
                self.stats["ai_errors"] += 1
                raise AIError("no connection to provider") from e
            except aiohttp.ClientError as e:
                self.stats["ai_errors"] += 1
                raise AIError(f"client error: {e}") from e

        raise AIError("retries exhausted")

    async def ask(self, chat_id: int, user_message: str, extra_context: str = "") -> str:
        if not user_message or not user_message.strip():
            raise AIError("empty message")
        user_message = user_message.strip()

        system = personas.render(self.cfg, self.identity)
        if extra_context.strip():
            system += f"\n\nextra context: {extra_context.strip()}"

        messages = [
            {"role": "system", "content": system},
            *self.get_history(chat_id),
            {"role": "user", "content": user_message},
        ]
        content = await self._chat_completion(
            messages,
            max_tokens=self.cfg.get("behavior.ai_max_tokens", 500),
            temperature=self.cfg.get("behavior.ai_temperature", 0.85),
        )
        self.add_to_history(chat_id, "user", user_message)
        self.add_to_history(chat_id, "assistant", content)
        self.stats["messages_processed"] += 1
        return content

    async def test_chat(self, message: str, history: list[dict] | None = None) -> str:
        """Try the current persona and model without touching telegram or history."""
        if not message or not message.strip():
            raise AIError("empty message")
        messages = [
            {"role": "system", "content": personas.render(self.cfg, self.identity)},
            *(history or []),
            {"role": "user", "content": message.strip()},
        ]
        return await self._chat_completion(
            messages,
            max_tokens=self.cfg.get("behavior.ai_max_tokens", 500),
            temperature=self.cfg.get("behavior.ai_temperature", 0.85),
        )

    async def generate_system_prompt(
        self, name: str, kind: str, tone: str, lang: str, extra: str = "",
    ) -> str:
        """Ask the active provider to write a persona system prompt. Falls back offline."""
        label = personas.language_label(lang)
        if kind == "human":
            acts = "a real person (never admits being an AI)"
        else:
            acts = "an AI assistant (honest about being one)"
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
            out = await self._chat_completion(
                [{"role": "system", "content": meta}],
                max_tokens=600,
                temperature=0.9,
            )
        except (AIError, RateLimited):
            return personas.build_custom(name, kind, tone, lang, extra)

        out = out.strip()
        if personas.GUARDRAILS not in out:
            out += "\n" + personas.GUARDRAILS
        lang_line = f"reply in {label}."
        if lang_line.lower() not in out.lower():
            out += "\n" + lang_line
        return _sanitize(out)
