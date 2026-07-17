"""Unit tests for the pure logic - no network, no Telegram.

Run: python -m pytest -q
"""

import asyncio
import time

import pytest

from tgai import ai_service, personas, providers
from tgai.ai_service import AIError, AIService, RateLimited
from tgai.config import _deep_merge
from tgai.personas import Identity
from tgai.ratelimit import ActivityFeed, AsyncRateLimiter
from tgai.telegram.bot import BotRunner

from .conftest import FakeResp, FakeSession

# rate limiter


def test_rate_limiter_spaces_calls():
    async def go():
        rl = AsyncRateLimiter(rpm=600)  # interval 0.1s
        await rl.acquire()              # first is free
        start = time.monotonic()
        await rl.acquire()              # second waits ~0.1s
        return time.monotonic() - start

    waited = asyncio.run(go())
    assert waited >= 0.08


def test_retry_after_parsing():
    assert ai_service._retry_after("5", 1) == 5.0
    assert ai_service._retry_after("99999", 1) == ai_service.MAX_BACKOFF   # clamped
    assert ai_service._retry_after("Wed, 21 Oct 2015 07:28:00 GMT", 1) == 0.0  # past date
    assert ai_service._retry_after("garbage", 1) > 0.0                     # falls back to backoff


# config


def test_deep_merge_fills_missing():
    merged = _deep_merge({"a": 1, "b": {"c": 2, "d": 3}}, {"b": {"c": 9}})
    assert merged["a"] == 1
    assert merged["b"]["c"] == 9   # existing kept
    assert merged["b"]["d"] == 3   # missing filled


def test_is_chat_allowed_rules(cfg):
    cfg.set("behavior.enabled", True)
    cfg.set("blacklist_chats", [5])
    cfg.set("active_chats", [10])
    assert cfg.is_chat_allowed(10) is True
    assert cfg.is_chat_allowed(11) is False   # whitelist active
    assert cfg.is_chat_allowed(5) is False    # blacklisted
    cfg.set("active_chats", [])
    assert cfg.is_chat_allowed(11) is True    # empty whitelist -> all
    cfg.set("behavior.enabled", False)
    assert cfg.is_chat_allowed(10) is False


def test_old_config_gains_new_defaults(tmp_path):
    # a config written before the api/willow keys existed still loads fine
    import json

    from tgai.config import ConfigStore

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"telegram": {"api_id": 1, "api_hash": "x"}, "active_provider": "groq"}))
    store = ConfigStore(str(path))
    store.load()
    assert store.get("api.port") == 8471
    assert "willow" in store.get("providers")
    assert "opencode" in store.get("providers")
    assert store.get("active_provider") == "groq"  # user value kept


# providers


def test_switch_provider_snaps_model(cfg):
    providers.set_active_provider(cfg, "groq")
    assert cfg.get("active_provider") == "groq"
    assert cfg.get("active_model") in providers.models(cfg, "groq")


def test_add_and_remove_model(cfg):
    assert providers.add_model(cfg, "nvidia", "test/model") is True
    assert "test/model" in providers.models(cfg, "nvidia")
    assert providers.add_model(cfg, "nvidia", "test/model") is False  # dup
    assert providers.remove_model(cfg, "nvidia", "test/model") is True
    assert "test/model" not in providers.models(cfg, "nvidia")


def test_mask_key():
    assert providers.mask_key("") == ""
    assert providers.mask_key("short") == "sh..."
    assert providers.mask_key("sk-abcdefghijklmnop") == "sk-ab...mnop"


# personas


def test_render_uses_name_and_language(cfg):
    cfg.set("persona", "assistant")
    cfg.set("bot_name", "kulebyaka")
    cfg.set("language", "en")
    out = personas.render(cfg, Identity())
    assert "kulebyaka" in out
    assert "English" in out


def test_build_custom_keeps_guardrails():
    out = personas.build_custom("bob", "bot", "friendly", "en", "love cats")
    assert "cats" in out
    assert "no threats" in out          # guardrail line present
    assert "English" in out


# bot dm decision


class _FakeMsg:
    def __init__(self, mid=1):
        self.id = mid
        self.text = "hi"
        self.entities = None
        self.reply_to = None


class _FakeClient:
    def __init__(self, history):
        self._history = history

    async def get_messages(self, chat, limit):
        return self._history


class _FakeEvent:
    def __init__(self, client, msg):
        self.client = client
        self.message = msg


def _make_bot(cfg) -> BotRunner:
    feed = ActivityFeed()
    identity = Identity()
    ai = AIService(cfg, feed, identity, histories_path="unused.json", session_factory=FakeSession)
    return BotRunner(cfg, ai, feed, identity)


def test_dm_new_dialogues_only(cfg):
    cfg.set("behavior.reply_in_dm", True)
    cfg.set("behavior.dm_new_dialogues_only", True)
    cfg.set("active_chats", [])
    bot = _make_bot(cfg)
    msg = _FakeMsg()

    # only the incoming message -> brand new dialogue -> answer
    ev_new = _FakeEvent(_FakeClient([msg]), msg)
    assert asyncio.run(bot._should_respond(ev_new, msg, 1, is_group=False)) is True

    # there is older history -> skip
    ev_old = _FakeEvent(_FakeClient([msg, _FakeMsg(2)]), msg)
    assert asyncio.run(bot._should_respond(ev_old, msg, 1, is_group=False)) is False


def test_whitelisted_chat_always_responds(cfg):
    cfg.set("behavior.reply_in_dm", False)   # dms off...
    cfg.set("active_chats", [42])            # ...but chat is whitelisted
    bot = _make_bot(cfg)
    msg = _FakeMsg()
    ev = _FakeEvent(_FakeClient([msg]), msg)
    assert asyncio.run(bot._should_respond(ev, msg, 42, is_group=False)) is True


# ai service 429 handling (mocked http)


def _make_ai(cfg, tmp_path, responses) -> AIService:
    cfg.set("active_provider", "nvidia")
    cfg.set("providers.nvidia.api_key", "nvapi-test")
    cfg.set("active_model", "moonshotai/kimi-k2.6")
    session = FakeSession(responses)
    return AIService(
        cfg, ActivityFeed(), Identity(),
        histories_path=str(tmp_path / "h.json"),
        session_factory=lambda: session,
    )


def test_429_then_success(cfg, tmp_path):
    ok = {"choices": [{"message": {"content": "hello \u2014 friend"}}]}
    ai = _make_ai(cfg, tmp_path, [
        FakeResp(429, headers={"Retry-After": "0"}),
        FakeResp(200, ok),
    ])
    out = asyncio.run(ai.ask(1, "hi"))
    assert out == "hello - friend"          # em-dash normalised
    assert ai.stats["rate_limited"] >= 1


def test_429_exhausted_raises_ratelimited(cfg, tmp_path):
    ai = _make_ai(cfg, tmp_path, [FakeResp(429, headers={"Retry-After": "0"}) for _ in range(4)])
    with pytest.raises(RateLimited):
        asyncio.run(ai.ask(1, "hi"))


def test_auth_error_raises_not_returns(cfg, tmp_path):
    ai = _make_ai(cfg, tmp_path, [FakeResp(401)])
    with pytest.raises(AIError):
        asyncio.run(ai.ask(1, "hi"))


def test_test_chat_does_not_touch_history(cfg, tmp_path):
    ok = {"choices": [{"message": {"content": "sure"}}]}
    ai = _make_ai(cfg, tmp_path, [FakeResp(200, ok)])
    out = asyncio.run(ai.test_chat("hello", [{"role": "user", "content": "prior"}]))
    assert out == "sure"
    assert ai.histories == {}
