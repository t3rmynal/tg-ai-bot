"""Unit tests for the pure logic - no network, no Telegram.

Run: python -m pytest -q
"""

import asyncio
import time

import pytest

import ai_service
import config
import personas
import providers
import userbot
from ai_service import AIError, RateLimited
from ratelimit import AsyncRateLimiter


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    # keep tests from touching the real config.json
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    config.load()
    yield


# ── rate limiter ─────────────────────────────────────────────────────────

def test_rate_limiter_spaces_calls():
    async def go():
        rl = AsyncRateLimiter(rpm=600)  # interval 0.1s
        await rl.acquire()              # first is free
        start = time.monotonic()
        await rl.acquire()              # second waits ~0.1s
        return time.monotonic() - start

    waited = asyncio.run(go())
    assert waited >= 0.08


# ── config ───────────────────────────────────────────────────────────────

def test_deep_merge_fills_missing():
    merged = config._deep_merge({"a": 1, "b": {"c": 2, "d": 3}}, {"b": {"c": 9}})
    assert merged["a"] == 1
    assert merged["b"]["c"] == 9   # existing kept
    assert merged["b"]["d"] == 3   # missing filled


def test_is_chat_allowed_rules():
    config.set("behavior.enabled", True)
    config.set("blacklist_chats", [5])
    config.set("active_chats", [10])
    assert config.is_chat_allowed(10) is True
    assert config.is_chat_allowed(11) is False   # whitelist active
    assert config.is_chat_allowed(5) is False     # blacklisted
    config.set("active_chats", [])
    assert config.is_chat_allowed(11) is True      # empty whitelist -> all
    config.set("behavior.enabled", False)
    assert config.is_chat_allowed(10) is False


# ── providers ────────────────────────────────────────────────────────────

def test_switch_provider_snaps_model():
    providers.set_active_provider("groq")
    assert config.get("active_provider") == "groq"
    assert config.get("active_model") in providers.models("groq")


def test_add_and_remove_model():
    assert providers.add_model("nvidia", "test/model") is True
    assert "test/model" in providers.models("nvidia")
    assert providers.add_model("nvidia", "test/model") is False  # dup
    assert providers.remove_model("nvidia", "test/model") is True
    assert "test/model" not in providers.models("nvidia")


# ── personas ─────────────────────────────────────────────────────────────

def test_render_uses_name_and_language():
    config.set("persona", "troll")
    config.set("bot_name", "кулебяка")
    config.set("language", "en")
    out = personas.render()
    assert "кулебяка" in out
    assert "English" in out


def test_build_custom_keeps_guardrails():
    out = personas.build_custom("боб", "бот", "дружелюбный", "ru", "люби котов")
    assert "котов" in out
    assert "без угроз" in out          # guardrail line present
    assert "русском" in out


# ── userbot DM decision ──────────────────────────────────────────────────

class _FakeMsg:
    def __init__(self, mid=1):
        self.id = mid
        self.text = "привет"
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


def test_dm_new_dialogues_only():
    config.set("behavior.reply_in_dm", True)
    config.set("behavior.dm_new_dialogues_only", True)
    config.set("active_chats", [])
    msg = _FakeMsg()

    # only the incoming message -> brand new dialogue -> answer
    ev_new = _FakeEvent(_FakeClient([msg]), msg)
    assert asyncio.run(userbot._should_respond(ev_new, msg, 1, is_group=False)) is True

    # there is older history -> skip
    ev_old = _FakeEvent(_FakeClient([msg, _FakeMsg(2)]), msg)
    assert asyncio.run(userbot._should_respond(ev_old, msg, 1, is_group=False)) is False


def test_whitelisted_chat_always_responds():
    config.set("behavior.reply_in_dm", False)   # DMs off...
    config.set("active_chats", [42])            # ...but chat is whitelisted
    msg = _FakeMsg()
    ev = _FakeEvent(_FakeClient([msg]), msg)
    assert asyncio.run(userbot._should_respond(ev, msg, 42, is_group=False)) is True


# ── ai_service 429 handling (mocked HTTP) ────────────────────────────────

class _FakeResp:
    def __init__(self, status, payload=None, headers=None):
        self.status = status
        self._payload = payload or {}
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return "error body"


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.closed = False

    def post(self, *a, **k):
        return self._responses.pop(0)


def _setup_provider():
    config.set("active_provider", "nvidia")
    config.set("providers.nvidia.api_key", "nvapi-test")
    config.set("active_model", "moonshotai/kimi-k2.6")


def test_429_then_success(monkeypatch, tmp_path):
    _setup_provider()
    monkeypatch.setattr(ai_service, "HISTORIES_FILE", str(tmp_path / "h.json"))
    ok = {"choices": [{"message": {"content": "привет — друг"}}]}
    session = _FakeSession([
        _FakeResp(429, headers={"Retry-After": "0"}),
        _FakeResp(200, ok),
    ])
    monkeypatch.setattr(ai_service, "_get_session", lambda: session)

    out = asyncio.run(ai_service.ask_ai(1, "hi"))
    assert out == "привет - друг"          # em-dash normalised
    assert ai_service.stats["rate_limited"] >= 1


def test_429_exhausted_raises_ratelimited(monkeypatch, tmp_path):
    _setup_provider()
    monkeypatch.setattr(ai_service, "HISTORIES_FILE", str(tmp_path / "h.json"))
    session = _FakeSession([_FakeResp(429, headers={"Retry-After": "0"}) for _ in range(4)])
    monkeypatch.setattr(ai_service, "_get_session", lambda: session)
    with pytest.raises(RateLimited):
        asyncio.run(ai_service.ask_ai(1, "hi"))


def test_auth_error_raises_not_returns(monkeypatch, tmp_path):
    _setup_provider()
    monkeypatch.setattr(ai_service, "HISTORIES_FILE", str(tmp_path / "h.json"))
    session = _FakeSession([_FakeResp(401)])
    monkeypatch.setattr(ai_service, "_get_session", lambda: session)
    with pytest.raises(AIError):
        asyncio.run(ai_service.ask_ai(1, "hi"))
