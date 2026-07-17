"""Runtime routes: status, enabled toggle, activity feed (sse), history, test chat."""

import asyncio
import json
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from tgai import providers
from tgai.ai_service import AIError, RateLimited
from tgai.api.deps import get_state
from tgai.api.schemas import EnabledIn, TestChatIn

router = APIRouter(tags=["runtime"])

STATS_INTERVAL = 5.0


def _runtime_payload(state) -> dict:
    cfg = state.cfg
    return {
        "enabled": bool(cfg.get("behavior.enabled", True)),
        "auth_state": state.auth.state.value,
        "provider": cfg.get("active_provider"),
        "provider_label": cfg.get(f"providers.{cfg.get('active_provider')}.label", ""),
        "model": cfg.get("active_model"),
        "persona": cfg.get("persona"),
        "language": cfg.get("language"),
        "rpm": providers.active_rpm(cfg),
        "uptime_s": round(monotonic() - state.started_at, 1),
        "version": _version(),
        "stats": {**state.ai.stats, "chats_with_history": len(state.ai.histories)},
    }


def _version() -> str:
    from tgai import __version__

    return __version__


@router.get("/health")
async def health():
    return {"ok": True, "version": _version()}


@router.get("/runtime")
async def runtime(state=Depends(get_state)):
    return _runtime_payload(state)


@router.get("/updates")
async def updates(force: bool = False, state=Depends(get_state)):
    return await state.updates.check(state.ai.get_session(), force=force)


@router.put("/runtime/enabled")
async def set_enabled(body: EnabledIn, state=Depends(get_state)):
    state.cfg.set("behavior.enabled", body.enabled)
    state.feed.push("info", "bot enabled" if body.enabled else "bot paused")
    return {"enabled": body.enabled}


@router.get("/runtime/activity")
async def activity(limit: int = 50, state=Depends(get_state)):
    return [
        {"id": e.id, "kind": e.kind, "text": e.text, "ts": e.ts}
        for e in state.feed.recent(max(1, min(limit, 200)))
    ]


@router.get("/runtime/events")
async def events(request: Request, state=Depends(get_state)):
    """Server-sent events: activity as it happens plus stats every few seconds."""

    async def stream():
        queue = state.feed.subscribe()
        try:
            # replay missed events for reconnecting clients
            last_id = request.headers.get("Last-Event-ID")
            if last_id and last_id.isdigit():
                for e in state.feed.since(int(last_id)):
                    yield _sse("activity", {"id": e.id, "kind": e.kind, "text": e.text, "ts": e.ts}, e.id)
            yield _sse("runtime", _runtime_payload(state))
            last_stats = monotonic()
            while True:
                if await request.is_disconnected():
                    return
                timeout = max(0.1, STATS_INTERVAL - (monotonic() - last_stats))
                try:
                    e = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield _sse("activity", {"id": e.id, "kind": e.kind, "text": e.text, "ts": e.ts}, e.id)
                except asyncio.TimeoutError:
                    pass
                if monotonic() - last_stats >= STATS_INTERVAL:
                    yield _sse("runtime", _runtime_payload(state))
                    last_stats = monotonic()
        finally:
            state.feed.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


def _sse(event: str, data: dict, event_id: int | None = None) -> str:
    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


@router.get("/history")
async def history_index(state=Depends(get_state)):
    return [
        {
            "chat_id": chat_id,
            "message_count": len(msgs),
            "last_role": msgs[-1]["role"] if msgs else None,
        }
        for chat_id, msgs in state.ai.histories.items()
    ]


@router.get("/history/{chat_id}")
async def history_chat(chat_id: int, limit: int = 100, state=Depends(get_state)):
    msgs = state.ai.get_history(chat_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="no history for this chat")
    return {"chat_id": chat_id, "messages": msgs[-max(1, min(limit, 1000)):]}


@router.delete("/history/{chat_id}", status_code=204)
async def clear_history(chat_id: int, state=Depends(get_state)):
    if not state.ai.clear_history(chat_id):
        raise HTTPException(status_code=404, detail="no history for this chat")


@router.post("/test-chat")
async def test_chat(body: TestChatIn, state=Depends(get_state)):
    start = monotonic()
    try:
        reply = await state.ai.test_chat(body.message, body.history)
    except RateLimited as e:
        raise HTTPException(status_code=429, detail=f"provider rate limit: {e}") from e
    except AIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"reply": reply, "latency_ms": round((monotonic() - start) * 1000)}
