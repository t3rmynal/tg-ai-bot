"""
Точка входа — запускает userbot и управляющий бот параллельно.
"""

import asyncio
import logging
import logging.handlers
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Консоль
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Ротируемый файл: 5 МБ × 3 файла
    file_handler = logging.handlers.RotatingFileHandler(
        "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Шум от внешних библиотек
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


# ── Валидация окружения ───────────────────────────────────────────────────────

REQUIRED_ENV = ["TG_API_ID", "TG_API_HASH", "TG_PHONE", "CONTROL_BOT_TOKEN", "ADMIN_ID", "KILOCODE_API_KEY"]


def validate_env() -> None:
    missing = [key for key in REQUIRED_ENV if not os.getenv(key)]
    if missing:
        print(f"[ERROR] Отсутствуют переменные окружения: {', '.join(missing)}")
        print("Скопируй .envexample в .env и заполни значения.")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

_shutdown_event = asyncio.Event()


def _handle_signal(signum, frame) -> None:
    sig_name = signal.Signals(signum).name
    logger.info(f"[Main] Получен сигнал {sig_name}, завершаю работу...")
    _shutdown_event.set()


async def safe_start_userbot() -> None:
    from userbot import start_userbot
    try:
        await start_userbot()
    except Exception as e:
        logger.error(f"[Userbot] Аварийное завершение: {e}", exc_info=True)
        raise


async def safe_start_control_bot() -> None:
    from control_bot import start_control_bot
    try:
        await start_control_bot()
    except Exception as e:
        logger.error(f"[ControlBot] Аварийное завершение: {e}", exc_info=True)
        raise


async def shutdown() -> None:
    """Graceful shutdown: отключаем клиентов, сохраняем состояние."""
    logger.info("[Main] Завершение...")

    try:
        from userbot import client
        if client.is_connected():
            await client.disconnect()
            logger.info("[Main] Telethon клиент отключён")
    except Exception as e:
        logger.warning(f"[Main] Ошибка при отключении Telethon: {e}")

    try:
        from ai_service import close_session
        await close_session()
        logger.info("[Main] aiohttp сессия закрыта")
    except Exception as e:
        logger.warning(f"[Main] Ошибка при закрытии сессии: {e}")


async def main() -> None:
    print("=" * 50)
    print("  TG AI USERBOT")
    print("=" * 50)

    # Загружаем историю чатов при старте
    from ai_service import load_histories
    load_histories()

    tasks = [
        asyncio.create_task(safe_start_userbot(), name="userbot"),
        asyncio.create_task(safe_start_control_bot(), name="control_bot"),
        asyncio.create_task(_shutdown_event.wait(), name="shutdown_watcher"),
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Отменяем оставшиеся задачи
    for task in pending:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    # Проверяем что упало
    for task in done:
        if task.get_name() == "shutdown_watcher":
            continue
        exc = task.exception() if not task.cancelled() else None
        if exc:
            logger.error(f"[Main] Задача '{task.get_name()}' завершилась с ошибкой: {exc}")

    await shutdown()
    logger.info("[Main] Остановлено")


if __name__ == "__main__":
    setup_logging()
    validate_env()

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
