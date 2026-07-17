"""Pydantic request models. Validation bounds match the old console menus."""

from pydantic import BaseModel, Field


class CredentialsIn(BaseModel):
    api_id: int = Field(gt=0)
    api_hash: str = Field(min_length=1, max_length=64)


class PasswordIn(BaseModel):
    password: str = Field(min_length=1)


class BehaviorPatch(BaseModel):
    enabled: bool | None = None
    reply_in_dm: bool | None = None
    reply_in_groups: bool | None = None
    reply_to_mentions: bool | None = None
    reply_to_replies: bool | None = None
    dm_new_dialogues_only: bool | None = None
    history_limit: int | None = Field(default=None, ge=1, le=1000)
    response_delay: float | None = Field(default=None, ge=0, le=30)
    per_chat_cooldown: float | None = Field(default=None, ge=0, le=120)
    ai_temperature: float | None = Field(default=None, ge=0, le=2)
    ai_max_tokens: int | None = Field(default=None, ge=1, le=4000)
    ai_thinking: bool | None = None


class SettingsPatch(BaseModel):
    behavior: BehaviorPatch | None = None
    persona: str | None = None
    custom_prompt: str | None = None
    language: str | None = None
    bot_name: str | None = Field(default=None, max_length=30)


class GeneratePromptIn(BaseModel):
    name: str = ""
    kind: str = Field(default="human", pattern="^(human|bot)$")
    tone: str = ""
    language: str = "en"
    extra: str = ""


class ActiveProviderIn(BaseModel):
    name: str
    model: str | None = None


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern="^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=60)
    base_url: str = Field(min_length=1)
    api_key: str = ""
    rpm: int = Field(default=60, ge=1, le=10000)
    models: list[str] = []


class ProviderPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=60)
    base_url: str | None = None
    rpm: int | None = Field(default=None, ge=1, le=10000)


class KeyIn(BaseModel):
    api_key: str


class ModelIn(BaseModel):
    model: str = Field(min_length=1)


class ChatIn(BaseModel):
    chat_id: int


class EnabledIn(BaseModel):
    enabled: bool


class TestChatIn(BaseModel):
    message: str = Field(min_length=1)
    history: list[dict] = []


class ProxyPatch(BaseModel):
    enabled: bool | None = None
    mode: str | None = Field(default=None, pattern="^(manual|mullvad)$")
    rotation: str | None = Field(default=None, pattern="^(off|per_request|per_n)$")
    rotate_every: int | None = Field(default=None, ge=1, le=1000)
    apply_to_telegram: bool | None = None
    mullvad_country: str | None = Field(default=None, max_length=2)


class ProxyUrlIn(BaseModel):
    url: str = Field(min_length=3)


class MullvadRefreshIn(BaseModel):
    country: str = Field(default="", max_length=2)


class ProxyTestIn(BaseModel):
    url: str = ""
