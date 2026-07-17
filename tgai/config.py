"""Config store backed by config.json. Dotted-path get/set, atomic writes.

No import-time side effects: build a ConfigStore and call load() explicitly.
"""

import copy
import json
import logging
import os
import threading

from tgai import providers

logger = logging.getLogger(__name__)


def _defaults() -> dict:
    return {
        "telegram": {"api_id": None, "api_hash": None},
        "api": {"host": "127.0.0.1", "port": 8471},
        "update_repo": "canary443/tg-ai-bot",
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


def _deep_merge(defaults: dict, data: dict) -> dict:
    """Copy of `data` with any keys missing from it filled in from `defaults`."""
    result = dict(data)
    for key, dval in defaults.items():
        if key not in result:
            result[key] = copy.deepcopy(dval)
        elif isinstance(dval, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(dval, result[key])
    return result


class ConfigStore:
    """Thread-safe dict store persisted to a json file with atomic writes."""

    def __init__(self, path: str = "config.json"):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict = {}

    def load(self) -> dict:
        if not os.path.exists(self.path):
            self._data = _defaults()
            self._save_unlocked()
            return self._data
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            self._data = _deep_merge(_defaults(), raw)
        except Exception as e:
            logger.error("could not read %s (%s), using defaults", self.path, e)
            self._data = _defaults()
        return self._data

    def _save_unlocked(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as e:
            logger.error("could not save %s: %s", self.path, e)
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def save(self) -> None:
        with self._lock:
            self._save_unlocked()

    def data(self) -> dict:
        return self._data

    def get(self, path: str, default=None):
        node = self._data
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, path: str, value) -> None:
        with self._lock:
            parts = path.split(".")
            node = self._data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
            self._save_unlocked()

    def delete(self, path: str) -> bool:
        with self._lock:
            parts = path.split(".")
            node = self._data
            for part in parts[:-1]:
                if not isinstance(node, dict) or part not in node:
                    return False
                node = node[part]
            if not isinstance(node, dict) or parts[-1] not in node:
                return False
            del node[parts[-1]]
            self._save_unlocked()
            return True

    def add_to_list(self, list_name: str, chat_id: int) -> bool:
        with self._lock:
            lst = self._data.setdefault(list_name, [])
            if chat_id in lst:
                return False
            lst.append(chat_id)
            self._save_unlocked()
            return True

    def remove_from_list(self, list_name: str, chat_id: int) -> bool:
        with self._lock:
            lst = self._data.setdefault(list_name, [])
            if chat_id not in lst:
                return False
            lst.remove(chat_id)
            self._save_unlocked()
            return True

    def is_complete(self) -> bool:
        """True once setup has the essentials: telegram creds, provider, model."""
        tg = self._data.get("telegram", {})
        if not (tg.get("api_id") and tg.get("api_hash")):
            return False
        _, prov = providers.active(self)
        if not prov.get("base_url"):
            return False
        if prov.get("needs_key", True) and not prov.get("api_key"):  # local providers skip the key
            return False
        return bool(self._data.get("active_model"))

    def is_chat_allowed(self, chat_id: int) -> bool:
        """enabled + blacklist + whitelist gate. dm/group switches live in the bot."""
        b = self._data.get("behavior", {})
        if not b.get("enabled", True):
            return False
        if chat_id in self._data.get("blacklist_chats", []):
            return False
        active_chats = self._data.get("active_chats", [])
        if active_chats:
            return chat_id in active_chats
        return True
