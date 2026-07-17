"""AI provider registry. Every provider speaks the OpenAI /chat/completions dialect.

A provider is plain data: label, base_url, api_key, rpm, models. Helpers take the
ConfigStore as first argument, so this module never imports config.
"""

import copy
import logging

import aiohttp

logger = logging.getLogger(__name__)


class ModelFetchError(Exception):
    """GET {base_url}/models failed or returned an unexpected shape."""


# rpm: free-tier requests per minute, used to space calls under the cap
DEFAULT_PROVIDERS = {
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "",
        "key_hint": "nvapi-...",
        "rpm": 40,  # free tier, shared across models on the key
        "models": ["moonshotai/kimi-k2.6", "deepseek-ai/deepseek-v4-flash"],
        "recommended": True,
        "signup": "https://build.nvidia.com",
    },
    "willow": {
        "label": "Willow",
        "base_url": "https://willowapi.digital/v1",
        "api_key": "",
        "key_hint": "sk-...",
        "rpm": 60,
        "models": [
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "gpt-5.5",
            "gemini-3.1-pro-preview",
            "grok-4.5",
            "deepseek-v4-pro",
            "kimi-k2.6",
        ],
        "recommended": False,
        "signup": "https://willowapi.digital",
    },
    "opencode": {
        "label": "OpenCode Zen",
        "base_url": "https://opencode.ai/zen/v1",
        "api_key": "",
        "key_hint": "sk-...",
        "rpm": 60,
        "models": [],
        "recommended": False,
        "signup": "https://opencode.ai/zen",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "key_hint": "sk-or-...",
        "rpm": 200,
        "models": ["deepseek/deepseek-chat"],
        "recommended": False,
        "signup": "https://openrouter.ai/keys",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "key_hint": "gsk_...",
        "rpm": 30,
        "models": ["llama-3.3-70b-versatile"],
        "recommended": False,
        "signup": "https://console.groq.com/keys",
    },
    "google": {
        "label": "Google AI Studio",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": "",
        "key_hint": "AIza...",
        "rpm": 15,
        "models": ["gemini-2.0-flash"],
        "recommended": False,
        "signup": "https://aistudio.google.com/app/apikey",
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",  # ignored by ollama, but the client needs something
        "key_hint": "not needed",
        "needs_key": False,
        "supports_thinking": True,  # accepts think:true, reasoning in message.reasoning
        "rpm": 120,  # local, only hardware-bound
        "models": ["gemma4"],
        "recommended": False,
        "signup": "ollama run <model>",
    },
    "openai_compat": {
        "label": "OpenAI-compatible",
        "base_url": "",
        "api_key": "",
        "key_hint": "sk-...",
        "rpm": 60,
        "models": [],
        "recommended": False,
        "signup": "",
    },
}


def default_providers() -> dict:
    """A fresh deep copy of the defaults for seeding a new config."""
    return copy.deepcopy(DEFAULT_PROVIDERS)


def is_builtin(name: str) -> bool:
    return name in DEFAULT_PROVIDERS


def mask_key(key: str) -> str:
    """Short masked form for api responses. Never return the raw key."""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 9:
        return key[:2] + "..."
    return key[:5] + "..." + key[-4:]


def active(cfg) -> tuple[str, dict]:
    """Return (name, provider_dict) for the currently selected provider."""
    name = cfg.get("active_provider", "nvidia")
    return name, cfg.get(f"providers.{name}", {})


def active_rpm(cfg) -> int:
    _, prov = active(cfg)
    return int(prov.get("rpm") or 40)


def models(cfg, name: str | None = None) -> list[str]:
    name = name or cfg.get("active_provider", "nvidia")
    return cfg.get(f"providers.{name}.models", [])


def set_active_provider(cfg, name: str) -> None:
    cfg.set("active_provider", name)
    # snap the active model to one this provider actually serves
    mdls = models(cfg, name)
    if cfg.get("active_model") not in mdls and mdls:
        cfg.set("active_model", mdls[0])


def set_active_model(cfg, model: str) -> None:
    cfg.set("active_model", model)


def set_key(cfg, name: str, key: str) -> None:
    cfg.set(f"providers.{name}.api_key", key.strip())


def add_model(cfg, name: str, model: str) -> bool:
    model = model.strip()
    if not model:
        return False
    mdls = list(cfg.get(f"providers.{name}.models", []))
    if model in mdls:
        return False
    mdls.append(model)
    cfg.set(f"providers.{name}.models", mdls)
    return True


def remove_model(cfg, name: str, model: str) -> bool:
    mdls = list(cfg.get(f"providers.{name}.models", []))
    if model not in mdls:
        return False
    mdls.remove(model)
    cfg.set(f"providers.{name}.models", mdls)
    if cfg.get("active_model") == model:
        cfg.set("active_model", mdls[0] if mdls else "")
    return True


def _parse_models_payload(data) -> list[str]:
    """Accept the openai {"data": [{"id": ...}]} shape plus common variants."""
    items = None
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            items = data["data"]
        elif isinstance(data.get("models"), list):
            items = data["models"]
    elif isinstance(data, list):
        items = data
    if items is None:
        raise ModelFetchError(f"unexpected models payload: {str(data)[:200]}")

    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            mid = item.get("id") or item.get("name") or item.get("model")
            if mid:
                out.append(str(mid))
    return sorted(set(out))


async def fetch_models(session: aiohttp.ClientSession, base_url: str, api_key: str) -> list[str]:
    """Live model discovery: GET {base_url}/models, openai dialect."""
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        raise ModelFetchError("provider has no base url")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with session.get(
            f"{base_url}/models", headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                body = (await resp.text())[:200]
                raise ModelFetchError(f"HTTP {resp.status}: {body}")
            data = await resp.json(content_type=None)
    except ModelFetchError:
        raise
    except Exception as e:
        raise ModelFetchError(f"could not fetch models: {e}") from e
    return _parse_models_payload(data)
