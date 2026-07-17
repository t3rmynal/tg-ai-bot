"""Whitelist/blacklist crud plus a live dialog picker."""

from fastapi import APIRouter, Depends, HTTPException

from tgai.api.deps import get_state, require_authorized
from tgai.api.schemas import ChatIn

router = APIRouter(prefix="/chats", tags=["chats"])


def _lists(state) -> dict:
    return {
        "whitelist": state.cfg.get("active_chats", []),
        "blacklist": state.cfg.get("blacklist_chats", []),
    }


@router.get("")
async def get_chats(state=Depends(get_state)):
    return _lists(state)


@router.post("/whitelist")
async def add_whitelist(body: ChatIn, state=Depends(get_state)):
    if not state.cfg.add_to_list("active_chats", body.chat_id):
        raise HTTPException(status_code=409, detail="already in the whitelist")
    return _lists(state)


@router.delete("/whitelist/{chat_id}")
async def remove_whitelist(chat_id: int, state=Depends(get_state)):
    if not state.cfg.remove_from_list("active_chats", chat_id):
        raise HTTPException(status_code=404, detail="not in the whitelist")
    return _lists(state)


@router.post("/blacklist")
async def add_blacklist(body: ChatIn, state=Depends(get_state)):
    if not state.cfg.add_to_list("blacklist_chats", body.chat_id):
        raise HTTPException(status_code=409, detail="already in the blacklist")
    return _lists(state)


@router.delete("/blacklist/{chat_id}")
async def remove_blacklist(chat_id: int, state=Depends(get_state)):
    if not state.cfg.remove_from_list("blacklist_chats", chat_id):
        raise HTTPException(status_code=404, detail="not in the blacklist")
    return _lists(state)


@router.get("/dialogs")
async def list_dialogs(limit: int = 100, state=Depends(get_state)):
    require_authorized(state)
    limit = max(1, min(limit, 500))
    dialogs = []
    try:
        for d in await state.auth.client.get_dialogs(limit=limit):
            if d.is_user:
                kind = "user"
            elif d.is_channel:
                kind = "channel"
            else:
                kind = "group"
            dialogs.append({
                "id": d.id,
                "title": d.title or "",
                "type": kind,
                "unread_count": d.unread_count or 0,
            })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"could not list dialogs: {e}") from e
    return dialogs
