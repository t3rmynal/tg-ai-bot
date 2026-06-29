"""AI provider registry.

Every provider here talks the OpenAI ``/chat/completions`` dialect, so a single
HTTP client in ai_service.py covers all of them. The console lets you switch the
active provider, paste an API key, and add or remove models.

The helper functions read and write through config.py. config.py imports this
module for its defaults, so the config import below is done lazily inside each
function to keep the two modules from importing each other at load time.
"""

import copy

# rpm = requests per minute the free tier allows on a single key. ai_service uses
# it to space out calls so we stay under the cap instead of getting 429'd.
DEFAULT_PROVIDERS = {
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "",
        "key_hint": "nvapi-...",
        "rpm": 40,  # free tier: ~40 req/min, shared across all models on the key
        "models": ["moonshotai/kimi-k2.6", "deepseek-ai/deepseek-v4-flash"],
        "recommended": True,
        "signup": "https://build.nvidia.com",
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


def active():
    """Return (name, provider_dict) for the currently selected provider."""
    import config

    name = config.get("active_provider", "nvidia")
    return name, config.get(f"providers.{name}", {})


def active_rpm() -> int:
    _, prov = active()
    return int(prov.get("rpm") or 40)


def models(name: str | None = None) -> list[str]:
    import config

    name = name or config.get("active_provider", "nvidia")
    return config.get(f"providers.{name}.models", [])


def set_active_provider(name: str) -> None:
    import config

    config.set("active_provider", name)
    # snap the active model to one this provider actually serves
    mdls = models(name)
    if config.get("active_model") not in mdls and mdls:
        config.set("active_model", mdls[0])


def set_active_model(model: str) -> None:
    import config

    config.set("active_model", model)


def set_key(name: str, key: str) -> None:
    import config

    config.set(f"providers.{name}.api_key", key.strip())


def add_model(name: str, model: str) -> bool:
    import config

    model = model.strip()
    if not model:
        return False
    mdls = list(config.get(f"providers.{name}.models", []))
    if model in mdls:
        return False
    mdls.append(model)
    config.set(f"providers.{name}.models", mdls)
    return True


def remove_model(name: str, model: str) -> bool:
    import config

    mdls = list(config.get(f"providers.{name}.models", []))
    if model not in mdls:
        return False
    mdls.remove(model)
    config.set(f"providers.{name}.models", mdls)
    if config.get("active_model") == model:
        config.set("active_model", mdls[0] if mdls else "")
    return True


def is_ready() -> tuple[bool, str]:
    """Whether the active provider can actually be called. Returns (ok, reason)."""
    name, prov = active()
    if not prov:
        return False, "провайдер не выбран"
    if not prov.get("base_url"):
        return False, f"у провайдера {name} не задан base_url"
    if not prov.get("api_key"):
        return False, f"у провайдера {name} не задан API-ключ"
    if not config_active_model():
        return False, "не выбрана модель"
    return True, ""


def config_active_model() -> str:
    import config

    return config.get("active_model", "")
