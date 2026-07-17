"""Settings and persona routes."""

from fastapi import APIRouter, Depends, HTTPException

from tgai import personas
from tgai.api.deps import get_state
from tgai.api.schemas import GeneratePromptIn, SettingsPatch

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_payload(state) -> dict:
    cfg = state.cfg
    return {
        "behavior": cfg.get("behavior", {}),
        "persona": cfg.get("persona", "assistant"),
        "custom_prompt": cfg.get("custom_prompt", ""),
        "language": cfg.get("language", "en"),
        "bot_name": cfg.get("bot_name", ""),
    }


@router.get("")
async def get_settings(state=Depends(get_state)):
    return _settings_payload(state)


@router.patch("")
async def patch_settings(body: SettingsPatch, state=Depends(get_state)):
    cfg = state.cfg
    if body.behavior is not None:
        for key, value in body.behavior.model_dump(exclude_none=True).items():
            cfg.set(f"behavior.{key}", value)
    if body.persona is not None:
        if body.persona not in personas.PERSONA_META:
            raise HTTPException(status_code=422, detail=f"unknown persona {body.persona}")
        cfg.set("persona", body.persona)
    if body.custom_prompt is not None:
        cfg.set("custom_prompt", body.custom_prompt.strip())
    if body.language is not None:
        if body.language not in personas.LANGUAGES:
            raise HTTPException(status_code=422, detail=f"unknown language {body.language}")
        cfg.set("language", body.language)
    if body.bot_name is not None:
        cfg.set("bot_name", body.bot_name.strip()[:30])
    return _settings_payload(state)


@router.get("/personas")
async def list_personas(state=Depends(get_state)):
    active = state.cfg.get("persona", "assistant")
    items = [
        {"key": key, "label": label, "kind": kind, "description": desc, "is_active": key == active}
        for key, (label, kind, desc) in personas.PERSONA_META.items()
    ]
    return {"personas": items, "preview": personas.render(state.cfg, state.identity)}


@router.post("/prompt/generate")
async def generate_prompt(body: GeneratePromptIn, state=Depends(get_state)):
    prompt = await state.ai.generate_system_prompt(
        body.name, body.kind, body.tone, body.language, body.extra,
    )
    # offline fallback is detectable: it is exactly what build_custom returns
    fallback = prompt == personas.build_custom(body.name, body.kind, body.tone, body.language, body.extra)
    return {"prompt": prompt, "source": "fallback" if fallback else "ai"}
