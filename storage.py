"""
Хранение настроек - какие чаты активны, настройки бота
"""

import json
import os

STORAGE_FILE = "storage.json"

DEFAULT_SETTINGS = {
    "enabled": True,           # бот вообще включён
    "active_chats": [],        # список chat_id где бот активен (пусто = все)
    "blacklist_chats": [],     # чаты где бот никогда не отвечает
    "reply_to_mentions": True, # отвечать на упоминания
    "reply_to_replies": True,  # отвечать на реплаи на сообщения бота
    "reply_in_dm": True,       # отвечать в лс
    "bot_name": "{bot_name}",  # имя в .env
    "response_delay": 1.5,     # задержка перед ответом в секундах (реалистичность)
}


def load_settings() -> dict:
    if not os.path.exists(STORAGE_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, val in DEFAULT_SETTINGS.items():
                if key not in data:
                    data[key] = val
            return data
    except Exception as e:
        print(f"[Storage] Ошибка загрузки: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    try:
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Ошибка сохранения: {e}")


settings = load_settings()


def get(key: str):
    return settings.get(key, DEFAULT_SETTINGS.get(key))


def set_val(key: str, value):
    settings[key] = value
    save_settings(settings)


def is_chat_allowed(chat_id: int) -> bool:
    """Проверяет, должен ли бот отвечать в этом чате"""
    if not settings["enabled"]:
        return False
    
    if chat_id in settings["blacklist_chats"]:
        return False

    if not settings["active_chats"]:
        return True

    return chat_id in settings["active_chats"]