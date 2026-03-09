"""    
Точка входа - запускает userbot и управляющий бот параллельно
"""

import asyncio
import logging
from userbot import start_userbot
from control_bot import start_control_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def safe_start_userbot():
    """Запуск userbot с обработкой ошибок"""
    try:
        await start_userbot()
    except Exception as e:
        logger.error(f"[Userbot] Ошибка: {e}")
        raise


async def safe_start_control_bot():
    """Запуск control bot с обработкой ошибок"""
    try:
        await start_control_bot()
    except Exception as e:
        logger.error(f"[ControlBot] Ошибка: {e}")
        raise


async def main():
    print("=" * 40)
    print("TG AI USERBOT")
    print("=" * 40)
    
    # Создаём задачи
    tasks = [
        asyncio.create_task(safe_start_userbot()),
        asyncio.create_task(safe_start_control_bot())
    ]
    
    # Ждём пока обе завершатся (или одна упадёт)
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Отменяем оставшуюся задачу
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Проверяем причину завершения
    for task in done:
        if task.exception():
            logger.error(f"Бот упал с ошибкой: {task.exception()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Main] Остановлено")