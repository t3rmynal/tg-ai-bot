"""Config store backed by config.json. Dotted-path get/set, atomic writes."""

import copy
import json
import logging
import os
import threading

import providers

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

DEFAULTS = {
    "telegram": {"api_id": None, "api_hash": None},
    "active_provider": "nvidia",
    "providers": providers.default_providers(),
    "active_model": "moonshotai/kimi-k2.6",
    "persona": "assistant",
    "custom_prompt": "",
    "language": "en",
    "bot_name": "",
    "behavior": {
        "enabled": True,
        "reply_in_dm": True,
        "reply_in_groups": True,
        "reply_to_mentions": True,
        "reply_to_replies": True,
        "dm_new_dialogues_only": False,
        "history_limit": 200,
        "response_delay": 1.5,
        "per_chat_cooldown": 3.0,
        "ai_temperature": 0.85,
        "ai_max_tokens": 500,
        "ai_thinking": False,
    },
    "active_chats": [],
    "blacklist_chats": [],
}

_lock = threading.Lock()
_data: dict = {}


def _deep_merge(defaults: dict, data: dict) -> dict:
    """Copy of `data` with any keys missing from it filled in from `defaults`."""
    result = dict(data)
    for key, dval in defaults.items():
        if key not in result:
            result[key] = copy.deepcopy(dval)
        elif isinstance(dval, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(dval, result[key])
    return result


def load() -> dict:
    global _data
    if not os.path.exists(CONFIG_FILE):
        _data = copy.deepcopy(DEFAULTS)
        _save_unlocked()
        return _data
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _data = _deep_merge(DEFAULTS, raw)
    except Exception as e:
        logger.error("could not read config.json (%s), using defaults", e)
        _data = copy.deepcopy(DEFAULTS)
    return _data


def _save_unlocked() -> None:
    tmp = CONFIG_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except Exception as e:
        logger.error("could not save config.json: %s", e)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def save() -> None:
    with _lock:
        _save_unlocked()


def data() -> dict:
    return _data


def get(path: str, default=None):
    node = _data
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


def set(path: str, value) -> None:
    with _lock:
        parts = path.split(".")
        node = _data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        _save_unlocked()


def add_to_list(list_name: str, chat_id: int) -> bool:
    with _lock:
        lst = _data.setdefault(list_name, [])
        if chat_id in lst:
            return False
        lst.append(chat_id)
        _save_unlocked()
        return True


def remove_from_list(list_name: str, chat_id: int) -> bool:
    with _lock:
        lst = _data.setdefault(list_name, [])
        if chat_id not in lst:
            return False
        lst.remove(chat_id)
        _save_unlocked()
        return True


def is_complete() -> bool:
    """True once the first-run wizard has the essentials."""
    tg = _data.get("telegram", {})
    if not (tg.get("api_id") and tg.get("api_hash")):
        return False
    name, prov = providers.active()
    if not prov.get("base_url"):
        return False
    if prov.get("needs_key", True) and not prov.get("api_key"):  # local providers skip the key
        return False
    return bool(_data.get("active_model"))


def is_chat_allowed(chat_id: int) -> bool:
    """enabled + blacklist + whitelist gate. dm/group switches live in userbot.py."""
    b = _data.get("behavior", {})
    if not b.get("enabled", True):
        return False
    if chat_id in _data.get("blacklist_chats", []):
        return False
    active_chats = _data.get("active_chats", [])
    if active_chats:
        return chat_id in active_chats
    return True


# load on import so other modules can read config immediately
load()
