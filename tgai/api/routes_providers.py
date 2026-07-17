"""Provider registry routes. Keys are write-only, responses carry masked hints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from tgai import providers
from tgai.api.deps import get_state
from tgai.api.schemas import ActiveProviderIn, KeyIn, ModelIn, ProviderCreate, ProviderPatch
from tgai.providers import ModelFetchError

router = APIRouter(prefix="/providers", tags=["providers"])


def _provider_payload(name: str, prov: dict) -> dict:
    return {
        "name": name,
        "label": prov.get("label", name),
        "base_url": prov.get("base_url", ""),
        "key_set": bool(prov.get("api_key")),
        "api_key_masked": providers.mask_key(prov.get("api_key", "")),
        "key_hint": prov.get("key_hint", ""),
        "needs_key": prov.get("needs_key", True),
        "supports_thinking": prov.get("supports_thinking", False),
        "recommended": prov.get("recommended", False),
        "signup": prov.get("signup", ""),
        "rpm": prov.get("rpm", 60),
        "models": prov.get("models", []),
        "builtin": providers.is_builtin(name),
    }


def _get_provider(state, name: str) -> dict:
    prov = state.cfg.get(f"providers.{name}")
    if prov is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {name}")
    return prov


@router.get("")
async def list_providers(state=Depends(get_state)):
    cfg = state.cfg
    registry = cfg.get("providers", {})
    return {
        "active": {"name": cfg.get("active_provider"), "model": cfg.get("active_model")},
        "providers": [_provider_payload(name, prov) for name, prov in registry.items()],
    }


@router.put("/active")
async def set_active(body: ActiveProviderIn, state=Depends(get_state)):
    _get_provider(state, body.name)
    providers.set_active_provider(state.cfg, body.name)
    if body.model:
        providers.set_active_model(state.cfg, body.model)
    state.ai.limiter.set_rpm(providers.active_rpm(state.cfg))
    return {"name": state.cfg.get("active_provider"), "model": state.cfg.get("active_model")}


@router.post("", status_code=201)
async def create_provider(body: ProviderCreate, state=Depends(get_state)):
    if state.cfg.get(f"providers.{body.name}") is not None:
        raise HTTPException(status_code=409, detail=f"provider {body.name} already exists")
    prov = {
        "label": body.label,
        "base_url": body.base_url.rstrip("/"),
        "api_key": body.api_key,
        "key_hint": "sk-...",
        "rpm": body.rpm,
        "models": body.models,
        "recommended": False,
        "signup": "",
    }
    state.cfg.set(f"providers.{body.name}", prov)
    return _provider_payload(body.name, prov)


@router.patch("/{name}")
async def patch_provider(name: str, body: ProviderPatch, state=Depends(get_state)):
    _get_provider(state, name)
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "base_url":
            value = value.rstrip("/")
        state.cfg.set(f"providers.{name}.{key}", value)
    if name == state.cfg.get("active_provider"):
        state.ai.limiter.set_rpm(providers.active_rpm(state.cfg))
    return _provider_payload(name, _get_provider(state, name))


@router.delete("/{name}", status_code=204)
async def delete_provider(name: str, state=Depends(get_state)):
    _get_provider(state, name)
    if providers.is_builtin(name):
        # deep-merge would resurrect it on next load anyway
        raise HTTPException(status_code=409, detail="built-in providers cannot be removed")
    if name == state.cfg.get("active_provider"):
        raise HTTPException(status_code=409, detail="provider is active, switch first")
    state.cfg.delete(f"providers.{name}")


@router.put("/{name}/key")
async def set_key(name: str, body: KeyIn, state=Depends(get_state)):
    _get_provider(state, name)
    providers.set_key(state.cfg, name, body.api_key)
    prov = _get_provider(state, name)
    return {
        "key_set": bool(prov.get("api_key")),
        "api_key_masked": providers.mask_key(prov.get("api_key", "")),
    }


@router.get("/{name}/models")
async def get_models(name: str, live: bool = False, state=Depends(get_state)):
    prov = _get_provider(state, name)
    static = prov.get("models", [])
    if not live:
        return {"models": static, "source": "static"}
    try:
        models = await providers.fetch_models(
            state.ai.get_session(), prov.get("base_url", ""), prov.get("api_key", ""),
        )
        return {"models": models, "source": "live"}
    except ModelFetchError as e:
        # graceful: the picker falls back to the configured list
        return {"models": static, "source": "static", "error": str(e)}


@router.post("/{name}/models/refresh")
async def refresh_models(name: str, state=Depends(get_state)):
    prov = _get_provider(state, name)
    try:
        live = await providers.fetch_models(
            state.ai.get_session(), prov.get("base_url", ""), prov.get("api_key", ""),
        )
    except ModelFetchError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    current = list(prov.get("models", []))
    added = [m for m in live if m not in current]
    merged = current + added
    state.cfg.set(f"providers.{name}.models", merged)
    return {"models": merged, "added": added, "source": "live"}


@router.post("/{name}/models")
async def add_model(name: str, body: ModelIn, state=Depends(get_state)):
    _get_provider(state, name)
    if not providers.add_model(state.cfg, name, body.model):
        raise HTTPException(status_code=409, detail="model already in the list")
    return {"models": providers.models(state.cfg, name)}


@router.delete("/{name}/models")
async def remove_model(name: str, model: str = Query(...), state=Depends(get_state)):
    _get_provider(state, name)
    if not providers.remove_model(state.cfg, name, model):
        raise HTTPException(status_code=404, detail="model not in the list")
    return {"models": providers.models(state.cfg, name), "active_model": state.cfg.get("active_model")}
