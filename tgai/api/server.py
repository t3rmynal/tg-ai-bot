"""FastAPI app factory. Localhost only, cors for the tauri webview and browser dev."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tgai.api import routes_auth, routes_chats, routes_providers, routes_runtime, routes_settings

# tauri webview origins (macos/linux, windows) plus next dev in a browser
CORS_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def create_app(state) -> FastAPI:
    app = FastAPI(title="tgai", docs_url=None, redoc_url=None)
    app.state.appstate = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        routes_auth.router,
        routes_settings.router,
        routes_providers.router,
        routes_chats.router,
        routes_runtime.router,
    ):
        app.include_router(router, prefix="/api")
    return app
