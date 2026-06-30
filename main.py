"""Entry point. One asyncio loop runs the Telethon client and the console menu."""

import asyncio
import logging
import logging.handlers

import ai_service
import config
import console
import personas
import providers
from userbot import create_client


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.handlers.RotatingFileHandler(
        "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    for noisy in ("telethon", "aiohttp", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def _shutdown(client) -> None:
    try:
        if client and client.is_connected():
            await client.disconnect()
    except Exception:
        pass
    await ai_service.close_session()


async def main() -> None:
    ai_service.load_histories()

    if not config.is_complete():
        if not await console.run_wizard() or not config.is_complete():
            console.console.print(f"[{console.ERR}]setup not finished, exiting[/]")
            return

    client = create_client()
    if not await console.interactive_login(client):
        console.console.print(f"[{console.ERR}]could not sign in to Telegram[/]")
        await _shutdown(client)
        return

    me = await client.get_me()
    personas.set_identity(me.username or "", me.first_name or "")
    ai_service._limiter.set_rpm(providers.active_rpm())

    try:
        await console.main_menu(client)
    finally:
        await _shutdown(client)


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
