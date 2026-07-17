"""Shared fixtures: tmp config store, fake aiohttp session, fake telethon client."""

import asyncio
from types import SimpleNamespace

import pytest
from telethon.errors import SessionPasswordNeededError

from tgai.ai_service import AIService
from tgai.app import AppState
from tgai.config import ConfigStore
from tgai.personas import Identity
from tgai.ratelimit import ActivityFeed
from tgai.telegram.auth import AuthManager
from tgai.telegram.bot import BotRunner
from tgai.updates import UpdateChecker


@pytest.fixture
def cfg(tmp_path) -> ConfigStore:
    store = ConfigStore(str(tmp_path / "config.json"))
    store.load()
    return store


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None, body="error body"):
        self.status = status
        self._payload = payload or {}
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return self._body


class FakeSession:
    """Scripted responses for both post and get."""

    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.closed = False
        self.requests: list[tuple] = []

    def post(self, url, **kwargs):
        self.requests.append(("post", url, kwargs))
        return self._responses.pop(0)

    def get(self, url, **kwargs):
        self.requests.append(("get", url, kwargs))
        return self._responses.pop(0)

    async def close(self):
        self.closed = True


class FakeQRLogin:
    def __init__(self, behavior: str):
        self.url = "tg://login?token=test-token"
        self.behavior = behavior

    async def wait(self, timeout=None):
        if self.behavior == "password":
            raise SessionPasswordNeededError(None)
        if self.behavior == "timeout":
            raise asyncio.TimeoutError
        if self.behavior == "ok":
            return True
        await asyncio.sleep(3600)  # hang until cancelled


class FakeTelegramClient:
    """Just enough of the telethon client for auth and dialog tests."""

    def __init__(self, session, api_id, api_hash):
        self.session_name = session
        self.api_id = api_id
        self.api_hash = api_hash
        self.connected = False
        self.authorized = False
        self.password = "hunter2"
        self.qr_behavior = "hang"
        self.dialogs = []

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def is_user_authorized(self):
        return self.authorized

    async def qr_login(self):
        return FakeQRLogin(self.qr_behavior)

    async def sign_in(self, password=None):
        if password != self.password:
            raise RuntimeError("PASSWORD_HASH_INVALID")
        self.authorized = True

    async def log_out(self):
        self.authorized = False

    async def get_me(self):
        return SimpleNamespace(id=777, username="testuser", first_name="Tess")

    async def get_dialogs(self, limit=100):
        return self.dialogs[:limit]

    def add_event_handler(self, *a, **k):
        pass

    def remove_event_handler(self, *a, **k):
        pass


def make_state(tmp_path, responses=None) -> AppState:
    """App state wired with fakes, no network and no telegram."""
    cfg = ConfigStore(str(tmp_path / "config.json"))
    cfg.load()
    feed = ActivityFeed()
    identity = Identity()
    session = FakeSession(responses)
    ai = AIService(
        cfg, feed, identity,
        histories_path=str(tmp_path / "histories.json"),
        session_factory=lambda: session,
    )
    auth = AuthManager(cfg, feed, identity)
    bot = BotRunner(cfg, ai, feed, identity)
    auth.on_authorized = lambda: bot.attach(auth.client)
    auth.on_logout = bot.detach
    state = AppState(
        cfg=cfg, feed=feed, identity=identity, ai=ai, auth=auth, bot=bot,
        updates=UpdateChecker("example/repo"),
    )
    state.fake_session = session  # type: ignore[attr-defined]
    return state


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr("tgai.telegram.auth.TelegramClient", FakeTelegramClient)
    return make_state(tmp_path)


@pytest.fixture
async def client(state):
    import httpx

    from tgai.api.server import create_app

    app = create_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
