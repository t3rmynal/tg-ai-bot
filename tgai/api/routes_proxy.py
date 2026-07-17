"""Proxy routes: manual pool, mullvad exits, rotation and a connectivity test."""

from fastapi import APIRouter, Depends, HTTPException, Query

from tgai import proxy as proxy_mod
from tgai.api.deps import get_state
from tgai.api.schemas import MullvadRefreshIn, ProxyPatch, ProxyTestIn, ProxyUrlIn

router = APIRouter(prefix="/proxy", tags=["proxy"])


def _status(state) -> dict:
    cfg = state.cfg
    pm = state.proxy
    active = pm.active()
    pool = pm.pool()
    return {
        "enabled": cfg.get("proxy.enabled", False),
        "mode": cfg.get("proxy.mode", "manual"),
        "rotation": cfg.get("proxy.rotation", "off"),
        "rotate_every": cfg.get("proxy.rotate_every", 10),
        "apply_to_telegram": cfg.get("proxy.apply_to_telegram", False),
        "pool_size": len(pool),
        "active": active.masked() if active else None,
        "mullvad_country": cfg.get("proxy.mullvad.country", ""),
        "mullvad_count": len(cfg.get("proxy.mullvad.loaded", [])),
    }


@router.get("")
async def get_proxy(state=Depends(get_state)):
    return _status(state)


@router.patch("")
async def patch_proxy(body: ProxyPatch, state=Depends(get_state)):
    cfg = state.cfg
    data = body.model_dump(exclude_none=True)
    for key in ("enabled", "mode", "rotation", "rotate_every", "apply_to_telegram"):
        if key in data:
            cfg.set(f"proxy.{key}", data[key])
    if "mullvad_country" in data:
        cfg.set("proxy.mullvad.country", data["mullvad_country"].lower())
    return _status(state)


@router.get("/list")
async def list_proxies(state=Depends(get_state)):
    # credentials never leave the backend, delete is by index
    manual = []
    for i, url in enumerate(state.cfg.get("proxy.manual", [])):
        p = proxy_mod.parse_proxy(url)
        if p:
            manual.append({"index": i, "masked": p.masked(), "scheme": p.scheme, "host": p.host})
    loaded = state.cfg.get("proxy.mullvad.loaded", [])
    return {
        "manual": manual,
        "mullvad_count": len(loaded),
        "mullvad_sample": loaded[:8],
    }


@router.post("/manual")
async def add_manual(body: ProxyUrlIn, state=Depends(get_state)):
    p = proxy_mod.parse_proxy(body.url)
    if p is None:
        raise HTTPException(status_code=422, detail="could not parse proxy, use scheme://host:port")
    manual = list(state.cfg.get("proxy.manual", []))
    if body.url in manual:
        raise HTTPException(status_code=409, detail="already in the list")
    manual.append(body.url)
    state.cfg.set("proxy.manual", manual)
    return _status(state)


@router.delete("/manual")
async def remove_manual(index: int = Query(...), state=Depends(get_state)):
    manual = list(state.cfg.get("proxy.manual", []))
    if index < 0 or index >= len(manual):
        raise HTTPException(status_code=404, detail="no proxy at that index")
    manual.pop(index)
    state.cfg.set("proxy.manual", manual)
    return _status(state)


@router.post("/mullvad/refresh")
async def refresh_mullvad(body: MullvadRefreshIn, state=Depends(get_state)):
    country = body.country.lower()
    try:
        urls = await proxy_mod.fetch_mullvad_urls(state.ai.get_session(), country)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"could not reach mullvad: {e}") from e
    state.cfg.set("proxy.mullvad.loaded", urls)
    state.cfg.set("proxy.mullvad.country", country)
    return {"count": len(urls), "country": country}


@router.post("/test")
async def run_test(body: ProxyTestIn, state=Depends(get_state)):
    if body.url:
        p = proxy_mod.parse_proxy(body.url)
        if p is None:
            raise HTTPException(status_code=422, detail="could not parse proxy")
    else:
        p = state.proxy.active()
        if p is None:
            raise HTTPException(status_code=409, detail="no active proxy to test")
    return await proxy_mod.test_proxy(p)


@router.post("/rotate")
async def rotate(state=Depends(get_state)):
    p = state.proxy.rotate()
    return {"active": p.masked() if p else None}
