import asyncio
import json
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

STORAGE_FILE = "storage.json"

DEFAULT_SETTINGS = {
    "enabled": True,
    "active_chats": [],
    "blacklist_chats": [],
    "reply_to_mentions": True,
    "reply_to_replies": True,
    "reply_in_dm": True,
    "bot_name": "бот",
    "response_delay": 1.5,
    "rate_limit_seconds": 3.0,
    "ai_model": "minimax/minimax-m2.5:free",
    "ai_temperature": 0.85,
    "ai_max_tokens": 500,
}

_lock = asyncio.Lock()


def _load_from_disk() -> dict:
    if not os.path.exists(STORAGE_FILE):
        _save_to_disk(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in DEFAULT_SETTINGS.items():
            if key not in data:
                data[key] = val
        return data
    except Exception as e:
        logger.error(f"[Storage] Ошибка загрузки: {e}, использую дефолты")
        return DEFAULT_SETTINGS.copy()


def _save_to_disk(data: dict) -> None:
    """Атомарная запись: пишем во временный файл, потом rename."""
    tmp_path = STORAGE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, STORAGE_FILE)
    except Exception as e:
        logger.error(f"[Storage] Ошибка сохранения: {e}")
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


settings: dict = _load_from_disk()


def get(key: str):
    return settings.get(key, DEFAULT_SETTINGS.get(key))


async def set_async(key: str, value) -> None:
    async with _lock:
        settings[key] = value
        _save_to_disk(settings)


def set_val(key: str, value) -> None:
    settings[key] = value
    _save_to_disk(settings)


def is_chat_allowed(chat_id: int) -> bool:
    if not settings["enabled"]:
        return False
    if chat_id in settings["blacklist_chats"]:
        return False
    if not settings["active_chats"]:
        return True
    return chat_id in settings["active_chats"]
