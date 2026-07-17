"""Composition root. One asyncio loop runs Telethon and the FastAPI server."""

import asyncio
import logging
import logging.handlers
from dataclasses import dataclass, field
from time import monotonic

import uvicorn

from tgai import providers
from tgai.ai_service import AIService
from tgai.config import ConfigStore
from tgai.personas import Identity
from tgai.proxy import ProxyManager
from tgai.ratelimit import ActivityFeed
from tgai.telegram.auth import AuthManager
from tgai.telegram.bot import BotRunner
from tgai.updates import DEFAULT_REPO, UpdateChecker

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    cfg: ConfigStore
    feed: ActivityFeed
    identity: Identity
    ai: AIService
    auth: AuthManager
    bot: BotRunner
    updates: UpdateChecker
    proxy: ProxyManager
    started_at: float = field(default_factory=monotonic)


def build_state(config_path: str = "config.json", histories_path: str = "histories.json") -> AppState:
    cfg = ConfigStore(config_path)
    cfg.load()
    feed = ActivityFeed()
    identity = Identity()
    proxy = ProxyManager(cfg)
    ai = AIService(cfg, feed, identity, histories_path=histories_path, proxy=proxy)
    ai.load_histories()
    ai.limiter.set_rpm(providers.active_rpm(cfg))
    auth = AuthManager(cfg, feed, identity, proxy=proxy)
    bot = BotRunner(cfg, ai, feed, identity)
    auth.on_authorized = lambda: bot.attach(auth.client)
    auth.on_logout = bot.detach
    updates = UpdateChecker(cfg.get("update_repo") or DEFAULT_REPO)
    return AppState(
        cfg=cfg, feed=feed, identity=identity, ai=ai, auth=auth, bot=bot,
        updates=updates, proxy=proxy,
    )


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.handlers.RotatingFileHandler(
        "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    for noisy in ("telethon", "aiohttp", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def run() -> None:
    from tgai.api.server import create_app

    state = build_state()
    await state.auth.startup()

    host = state.cfg.get("api.host", "127.0.0.1")
    port = int(state.cfg.get("api.port", 8471))
    server = uvicorn.Server(uvicorn.Config(
        create_app(state), host=host, port=port, log_config=None,
    ))
    # we own sigint/sigterm so shutdown reaches telethon too
    server.install_signal_handlers = lambda: None

    logger.info("[App] api on http://%s:%d", host, port)
    state.feed.push("info", f"api on http://{host}:{port}")
    try:
        await server.serve()
    finally:
        state.bot.detach()
        await state.auth.shutdown()
        await state.ai.close()


def main() -> None:
    setup_logging()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
