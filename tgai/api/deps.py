"""Request-scoped access to the app state."""

from fastapi import HTTPException, Request

from tgai.app import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.appstate


def require_authorized(state: AppState) -> None:
    if not state.auth.authorized:
        raise HTTPException(status_code=409, detail="not signed in to Telegram")
