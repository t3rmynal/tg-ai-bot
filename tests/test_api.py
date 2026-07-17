"""API tests over the asgi app: auth flow, settings, providers, chats, runtime."""

import asyncio

from .conftest import FakeResp

# auth


async def test_auth_flow_no_credentials_to_qr(client, state):
    r = await client.get("/api/auth/status")
    assert r.status_code == 200
    assert r.json()["state"] == "no_credentials"

    # qr before credentials is a 409
    r = await client.post("/api/auth/qr")
    assert r.status_code == 409

    r = await client.post("/api/auth/credentials", json={"api_id": 123, "api_hash": "abc"})
    assert r.status_code == 200
    assert r.json()["state"] == "unauthorized"
    assert state.cfg.get("telegram.api_id") == 123

    r = await client.post("/api/auth/qr")
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("tg://login")
    assert body["expires_at"]

    r = await client.get("/api/auth/status")
    assert r.json()["state"] == "qr_pending"
    assert r.json()["qr"]["url"].startswith("tg://login")


async def test_auth_qr_timeout_returns_to_unauthorized(client, state):
    await client.post("/api/auth/credentials", json={"api_id": 1, "api_hash": "x"})
    state.auth.client.qr_behavior = "timeout"
    r = await client.post("/api/auth/qr")
    assert r.status_code == 200
    await asyncio.sleep(0.05)  # let the wait task run
    r = await client.get("/api/auth/status")
    assert r.json()["state"] == "unauthorized"


async def test_auth_2fa_flow(client, state):
    await client.post("/api/auth/credentials", json={"api_id": 1, "api_hash": "x"})
    state.auth.client.qr_behavior = "password"
    await client.post("/api/auth/qr")
    await asyncio.sleep(0.05)

    r = await client.get("/api/auth/status")
    assert r.json()["state"] == "password_needed"

    r = await client.post("/api/auth/password", json={"password": "nope"})
    assert r.status_code == 401
    r = await client.get("/api/auth/status")
    assert r.json()["state"] == "password_needed"  # state kept, retry allowed

    r = await client.post("/api/auth/password", json={"password": "hunter2"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "authorized"
    assert body["user"]["username"] == "testuser"
    assert state.bot.attached is True
    assert state.identity.username == "testuser"

    r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    assert state.bot.attached is False
    r = await client.get("/api/auth/status")
    assert r.json()["state"] == "unauthorized"


async def test_password_without_prompt_is_409(client):
    r = await client.post("/api/auth/password", json={"password": "x"})
    assert r.status_code == 409


# settings


async def test_settings_patch_and_validation(client, state):
    r = await client.get("/api/settings")
    assert r.json()["behavior"]["ai_temperature"] == 0.85

    r = await client.patch("/api/settings", json={
        "behavior": {"ai_temperature": 1.2, "response_delay": 0},
        "language": "ru",
        "bot_name": "  kulebyaka  ",
    })
    assert r.status_code == 200
    assert state.cfg.get("behavior.ai_temperature") == 1.2
    assert state.cfg.get("behavior.response_delay") == 0
    assert state.cfg.get("language") == "ru"
    assert state.cfg.get("bot_name") == "kulebyaka"
    # untouched keys survive a partial patch
    assert state.cfg.get("behavior.reply_in_dm") is True

    r = await client.patch("/api/settings", json={"behavior": {"ai_temperature": 3}})
    assert r.status_code == 422
    r = await client.patch("/api/settings", json={"persona": "nonexistent"})
    assert r.status_code == 422
    r = await client.patch("/api/settings", json={"language": "de"})
    assert r.status_code == 422


async def test_personas_list_and_preview(client, state):
    state.cfg.set("persona", "witty")
    r = await client.get("/api/settings/personas")
    body = r.json()
    active = [p for p in body["personas"] if p["is_active"]]
    assert [p["key"] for p in active] == ["witty"]
    assert "telegram" in body["preview"]


async def test_generate_prompt_falls_back_offline(client):
    # no provider key configured, the ai call fails, offline builder answers
    r = await client.post("/api/settings/prompt/generate", json={
        "name": "bob", "kind": "bot", "tone": "dry", "language": "en", "extra": "",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback"
    assert "bob" in body["prompt"]


# providers


async def test_providers_list_masks_keys(client, state):
    state.cfg.set("providers.nvidia.api_key", "nvapi-supersecretvalue")
    r = await client.get("/api/providers")
    body = r.json()
    nvidia = next(p for p in body["providers"] if p["name"] == "nvidia")
    assert nvidia["key_set"] is True
    assert "supersecret" not in r.text
    assert nvidia["api_key_masked"].startswith("nvapi")
    names = [p["name"] for p in body["providers"]]
    assert "willow" in names and "opencode" in names


async def test_set_active_snaps_model_and_rpm(client, state):
    r = await client.put("/api/providers/active", json={"name": "groq"})
    assert r.status_code == 200
    assert r.json()["model"] == "llama-3.3-70b-versatile"
    assert state.ai.limiter.rpm == 30

    r = await client.put("/api/providers/active", json={"name": "missing"})
    assert r.status_code == 404


async def test_provider_crud_and_builtin_guard(client, state):
    r = await client.delete("/api/providers/nvidia")
    assert r.status_code == 409  # builtin

    r = await client.post("/api/providers", json={
        "name": "myapi", "label": "My API", "base_url": "https://my.api/v1/", "rpm": 10,
    })
    assert r.status_code == 201
    assert r.json()["base_url"] == "https://my.api/v1"

    r = await client.post("/api/providers", json={
        "name": "myapi", "label": "My API", "base_url": "https://my.api/v1",
    })
    assert r.status_code == 409  # duplicate

    r = await client.patch("/api/providers/myapi", json={"rpm": 99})
    assert r.json()["rpm"] == 99

    r = await client.put("/api/providers/myapi/key", json={"api_key": "sk-verysecretkey1"})
    assert r.json()["key_set"] is True
    assert "verysecret" not in r.text

    r = await client.delete("/api/providers/myapi")
    assert r.status_code == 204
    assert state.cfg.get("providers.myapi") is None


async def test_models_live_falls_back_to_static(client, state):
    state.fake_session._responses = [FakeResp(500)]
    r = await client.get("/api/providers/nvidia/models", params={"live": "true"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "static"
    assert "error" in body
    assert body["models"] == state.cfg.get("providers.nvidia.models")


async def test_models_refresh_merges_and_persists(client, state):
    state.fake_session._responses = [
        FakeResp(200, {"data": [{"id": "brand/new-model"}, {"id": "moonshotai/kimi-k2.6"}]}),
    ]
    r = await client.post("/api/providers/nvidia/models/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == ["brand/new-model"]
    assert "moonshotai/kimi-k2.6" in body["models"]  # no dup
    assert "brand/new-model" in state.cfg.get("providers.nvidia.models")


async def test_models_refresh_upstream_error_is_502(client, state):
    state.fake_session._responses = [FakeResp(500)]
    r = await client.post("/api/providers/nvidia/models/refresh")
    assert r.status_code == 502


async def test_model_add_remove(client, state):
    r = await client.post("/api/providers/nvidia/models", json={"model": "x/y"})
    assert "x/y" in r.json()["models"]
    r = await client.post("/api/providers/nvidia/models", json={"model": "x/y"})
    assert r.status_code == 409
    r = await client.delete("/api/providers/nvidia/models", params={"model": "x/y"})
    assert "x/y" not in r.json()["models"]


# chats


async def test_chat_lists_crud(client):
    r = await client.post("/api/chats/whitelist", json={"chat_id": 42})
    assert r.json()["whitelist"] == [42]
    r = await client.post("/api/chats/whitelist", json={"chat_id": 42})
    assert r.status_code == 409
    r = await client.post("/api/chats/blacklist", json={"chat_id": -100500})
    assert r.json()["blacklist"] == [-100500]
    r = await client.delete("/api/chats/whitelist/42")
    assert r.json()["whitelist"] == []
    r = await client.delete("/api/chats/whitelist/42")
    assert r.status_code == 404


async def test_dialogs_require_auth(client, state):
    r = await client.get("/api/chats/dialogs")
    assert r.status_code == 409

    # sign in through the fake client, then dialogs come through mapped
    from types import SimpleNamespace

    await client.post("/api/auth/credentials", json={"api_id": 1, "api_hash": "x"})
    state.auth.client.qr_behavior = "ok"
    state.auth.client.dialogs = [
        SimpleNamespace(id=1, title="Alice", is_user=True, is_channel=False, unread_count=2),
        SimpleNamespace(id=-100, title="News", is_user=False, is_channel=True, unread_count=0),
    ]
    await client.post("/api/auth/qr")
    await asyncio.sleep(0.05)
    r = await client.get("/api/chats/dialogs")
    assert r.status_code == 200
    assert r.json() == [
        {"id": 1, "title": "Alice", "type": "user", "unread_count": 2},
        {"id": -100, "title": "News", "type": "channel", "unread_count": 0},
    ]


# runtime


async def test_runtime_and_enabled_toggle(client, state):
    r = await client.get("/api/runtime")
    body = r.json()
    assert body["enabled"] is True
    assert body["auth_state"] == "no_credentials"
    assert body["stats"]["ai_calls"] == 0

    r = await client.put("/api/runtime/enabled", json={"enabled": False})
    assert r.json()["enabled"] is False
    assert state.cfg.get("behavior.enabled") is False


async def test_activity_snapshot(client, state):
    state.feed.push("info", "hello")
    r = await client.get("/api/runtime/activity")
    events = r.json()
    assert events[-1]["text"] == "hello"
    assert events[-1]["kind"] == "info"


async def test_history_endpoints(client, state):
    state.ai.add_to_history(7, "user", "hi")
    state.ai.add_to_history(7, "assistant", "hello")

    r = await client.get("/api/history")
    assert r.json() == [{"chat_id": 7, "message_count": 2, "last_role": "assistant"}]

    r = await client.get("/api/history/7")
    assert len(r.json()["messages"]) == 2

    r = await client.delete("/api/history/7")
    assert r.status_code == 204
    r = await client.get("/api/history/7")
    assert r.status_code == 404


async def test_test_chat_roundtrip(client, state):
    state.cfg.set("providers.nvidia.api_key", "nvapi-test")
    state.fake_session._responses = [
        FakeResp(200, {"choices": [{"message": {"content": "test reply"}}]}),
    ]
    r = await client.post("/api/test-chat", json={"message": "hello"})
    assert r.status_code == 200
    assert r.json()["reply"] == "test reply"
    assert "latency_ms" in r.json()
    assert state.ai.histories == {}  # never persisted


async def test_health(client):
    r = await client.get("/api/health")
    assert r.json()["ok"] is True
