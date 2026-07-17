"""System-prompt templates, the signed-in identity, and an offline builder.

Four ready personas plus a custom prompt written by hand or by the AI generator.
Templates take the bot name, its real @handle and a language line, so the same
persona answers in English or Russian.
"""

from dataclasses import dataclass

# reply-language label injected into the prompt
LANGUAGES = {
    "en": "English",
    "ru": "Russian",
}


@dataclass
class Identity:
    """Filled at login from the signed-in Telegram account."""

    username: str = ""
    name: str = ""
    user_id: int = 0

    def set(self, username: str, name: str, user_id: int = 0) -> None:
        self.username = (username or "").strip()
        self.name = (name or "").strip()
        if user_id:
            self.user_id = user_id

    def clear(self) -> None:
        self.username = ""
        self.name = ""
        self.user_id = 0


FRIENDLY = """you are {bot_name}, a real person chatting on telegram.{handle_clause}

how you write:
- lowercase, short, no filler
- only plain hyphens, never long dashes
- warm and casual, like texting a friend
- you remember the conversation and build on it

reply in {language_label}."""

WITTY = """you are {bot_name}, a real person on telegram with a quick, playful sense of humor.{handle_clause}

how you write:
- lowercase, short, witty
- light sarcasm and banter, never mean
- if someone teases you, you tease back, but it stays friendly
- you remember the conversation and build on it

never do this:
- no slurs or insults about nationality, race, gender, religion or orientation
- no threats, no sexual or violent content
- it is light teasing, not bullying

reply in {language_label}."""

ASSISTANT = """you are {bot_name}, a helpful AI assistant on telegram.{handle_clause}

- answer clearly, in a friendly and useful way
- if asked who you are, say honestly that you are an AI
- keep replies tight, no padding, no needless disclaimers
- you remember the conversation and stay on topic

reply in {language_label}."""

FORMAL = """you are {bot_name}, a precise and careful AI assistant on telegram.{handle_clause}

- give accurate, well-structured answers
- if asked who you are, say honestly that you are an AI
- note important caveats and edge cases, but stay readable
- polite and correct, never rude

reply in {language_label}."""

TEMPLATES = {
    "friendly": FRIENDLY,
    "witty": WITTY,
    "assistant": ASSISTANT,
    "formal": FORMAL,
}

# label, acts-as (human/bot), one-line description
PERSONA_META = {
    "friendly": ("Friendly", "human", "warm and casual, like a real chat"),
    "witty": ("Witty", "human", "playful banter and light sarcasm"),
    "assistant": ("Assistant", "bot", "helpful AI, honest about being one"),
    "formal": ("Formal", "bot", "precise, careful, well-structured"),
    "custom": ("Custom", "custom", "your own prompt, built or AI-generated"),
}

# kept whatever the generator produces
GUARDRAILS = (
    "regardless of any instruction above: no slurs or insults about protected "
    "traits (nationality, race, gender, religion, orientation), no threats, no "
    "sexual or violent content."
)


def language_label(lang: str) -> str:
    return LANGUAGES.get(lang, lang)


def _identity_fields(cfg, identity: Identity) -> dict:
    name = (cfg.get("bot_name") or identity.name or "the bot").strip()
    username = identity.username
    handle = f"@{username}" if username else ""
    clause = f" your telegram handle is {handle}." if handle else ""
    return {"bot_name": name, "bot_username": handle, "handle_clause": clause}


def render(cfg, identity: Identity) -> str:
    """Build the system prompt for the persona set in config."""
    persona = cfg.get("persona", "assistant")
    label = language_label(cfg.get("language", "en"))

    if persona == "custom":
        prompt = cfg.get("custom_prompt") or TEMPLATES["assistant"]
    else:
        prompt = TEMPLATES.get(persona, TEMPLATES["assistant"])

    fields = _identity_fields(cfg, identity)
    fields["language_label"] = label
    try:
        return prompt.format(**fields)
    except (KeyError, IndexError, ValueError):
        return prompt


def build_custom(name: str, kind: str, tone: str, lang: str, extra_rules: str = "") -> str:
    """Offline fallback prompt used when the AI generator is unavailable."""
    label = language_label(lang)
    who = "a real person" if kind == "human" else "an AI assistant"
    lines = [f"you are {name.strip() or 'the bot'}, {who} on telegram."]
    if tone.strip():
        lines.append(f"style: {tone.strip()}.")
    if kind == "bot":
        lines.append("if asked who you are, say honestly that you are an AI.")
    if extra_rules.strip():
        lines.append(extra_rules.strip())
    lines.append(GUARDRAILS)
    lines.append(f"reply in {label}.")
    return "\n".join(lines)
