"""Console app: banner, first-run wizard, menus and the live monitor.

The menu loop and the Telethon client share one event loop, so the bot keeps
answering while you navigate, and any setting you change applies to the next
message.
"""

import asyncio
import time

import pyfiglet
import questionary
from questionary import Choice
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

import ai_service
import config
import personas
import providers
from ratelimit import recent

console = Console()

# palette
P = "bold cyan"
ACCENT = "magenta"
OK = "green"
WARN = "yellow"
ERR = "red"
DIM = "dim"

VERSION = "v2.0.0"

QSTYLE = questionary.Style([
    ("qmark", "fg:#00d7ff bold"),
    ("question", "bold"),
    ("answer", "fg:#ff5fff bold"),
    ("pointer", "fg:#00d7ff bold"),
    ("highlighted", "fg:#00d7ff bold"),
    ("selected", "fg:#5fff87"),
])


# ─────────────────────────────── helpers ────────────────────────────────

def _onoff(value: bool) -> str:
    return f"[{OK}]on[/]" if value else f"[{DIM}]off[/]"


def _is_number(text: str) -> bool:
    try:
        float(str(text).replace(",", "."))
        return True
    except ValueError:
        return False


async def _select(message: str, choices, default=None):
    return await questionary.select(
        message, choices=choices, default=default, style=QSTYLE, qmark="›",
    ).ask_async()


async def _text(message: str, default: str = "", password: bool = False, validate=None):
    fn = questionary.password if password else questionary.text
    return await fn(message, default=default, style=QSTYLE, qmark="›", validate=validate).ask_async()


async def _confirm(message: str, default: bool = True) -> bool:
    return await questionary.confirm(message, default=default, style=QSTYLE, qmark="›").ask_async()


def _pause() -> None:
    console.input(f"[{DIM}]Enter · back[/]")


# ─────────────────────────────── banner ─────────────────────────────────

def banner() -> None:
    console.clear()
    try:
        art = pyfiglet.figlet_format("TG  AI", font="ansi_shadow")
    except Exception:
        art = pyfiglet.figlet_format("TG AI")
    lines = [ln for ln in art.splitlines() if ln.strip()]
    text = Text()
    shades = ["#00d7ff", "#22c1e8", "#3aa9d1", "#5fafff"]
    for i, ln in enumerate(lines):
        text.append(ln + "\n", style=shades[i % len(shades)])
    subtitle = Text("Telegram AI Userbot  ·  ", style=DIM)
    subtitle.append(VERSION, style=ACCENT)
    console.print(Align.center(text))
    console.print(Align.center(subtitle))
    console.print()


def _provider_label() -> str:
    name, prov = providers.active()
    return prov.get("label", name)


def status_panel() -> Panel:
    b = config.get("behavior", {})
    persona = config.get("persona", "assistant")
    pmeta = personas.PERSONA_META.get(persona, (persona, "", ""))
    lang = config.get("language", "en")

    t = Table.grid(padding=(0, 2))
    t.add_column(justify="right", style=DIM)
    t.add_column()
    t.add_row("provider", f"[{P}]{_provider_label()}[/]  ·  {config.get('active_model') or 'none'}")
    t.add_row("persona", f"{pmeta[0]}  [{DIM}]({lang})[/]")
    t.add_row("bot enabled", _onoff(b.get("enabled", True)))
    t.add_row("DMs / groups", f"{_onoff(b.get('reply_in_dm', True))}  /  {_onoff(b.get('reply_in_groups', True))}")
    t.add_row("mentions / replies", f"{_onoff(b.get('reply_to_mentions', True))}  /  {_onoff(b.get('reply_to_replies', True))}")
    t.add_row("whitelist / blacklist", f"{len(config.get('active_chats', []))}  /  {len(config.get('blacklist_chats', []))}")
    return Panel(t, title="status", border_style=P, box=box.ROUNDED)


# ─────────────────────────────── login ──────────────────────────────────

def _render_qr(url: str) -> Text:
    """Render a login URL as a scannable QR code using filled block chars."""
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    text = Text(no_wrap=True)
    for row in matrix:
        text.append("  ")
        for cell in row:
            text.append("██" if cell else "  ", style=P)
        text.append("\n")
    return text


async def _enter_2fa(client) -> bool:
    """Ask for the cloud (2FA) password. Three attempts, then bail."""
    for _ in range(3):
        pw = await _text("Cloud (2FA) password:", password=True)
        if not pw:
            return False
        try:
            await client.sign_in(password=pw)
            console.print(f"[{OK}]signed in[/]")
            return True
        except Exception as e:
            console.print(f"[{ERR}]wrong password: {e}[/]")
    return False


async def _login_by_qr(client) -> bool:
    """Sign in by showing a QR code to scan from another Telegram session."""
    from telethon.errors import SessionPasswordNeededError

    console.print(Panel(
        f"Sign in by QR code.\n"
        f"Settings -> Devices -> [{P}]Link Desktop Device[/] in your Telegram app,\n"
        f"then point it at the code below. It refreshes itself every ~30s.",
        border_style=ACCENT, box=box.ROUNDED))

    while True:
        try:
            qr_login = await client.qr_login()
        except Exception as e:
            console.print(f"[{ERR}]could not create QR code: {e}[/]")
            return False

        console.clear()
        console.print(Align.center(_render_qr(qr_login.url)))
        console.print(Align.center(Text("point your Telegram camera at the code", style=DIM)))
        console.print()

        wait_task = asyncio.create_task(qr_login.wait())
        spinner = asyncio.create_task(_qr_spinner())
        try:
            await wait_task
        except asyncio.TimeoutError:
            spinner.cancel()
            console.print(f"\n[{WARN}]code expired, generating a new one…[/]")
            continue
        except SessionPasswordNeededError:
            spinner.cancel()
            console.print(f"\n[{WARN}]cloud (2FA) password needed.[/]")
            return await _enter_2fa(client)
        except Exception as e:
            spinner.cancel()
            console.print(f"\n[{ERR}]QR sign-in error: {e}[/]")
            return False
        else:
            spinner.cancel()
            console.print(f"\n[{OK}]signed in[/]")
            return True


async def _qr_spinner():
    """Animated 'waiting for scan' hint while QR login polls."""
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    try:
        while True:
            console.print(f"\r[{P}]{frames[i % len(frames)]}[/] waiting for scan…",
                          end="", soft_wrap=True)
            i += 1
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        console.print("\r", end="")


async def interactive_login(client) -> bool:
    """Sign in to Telegram by QR code. 2FA is handled if the account has it."""
    if not client.is_connected():
        await client.connect()
    if await client.is_user_authorized():
        return True

    console.print(Panel("Signing in to Telegram.", border_style=ACCENT, box=box.ROUNDED))
    return await _login_by_qr(client)


# ─────────────────────────────── wizard ─────────────────────────────────

async def run_wizard() -> bool:
    banner()
    console.print(Panel(
        "First run. Let's grab a couple of things and go.\n"
        f"[{DIM}]API_ID and API_HASH come from my.telegram.org/apps[/]",
        title="setup", border_style=ACCENT, box=box.ROUNDED,
    ))

    api_id = await _text("Telegram API_ID:", validate=lambda v: v.isdigit() or "digits only")
    if not api_id:
        return False
    api_hash = await _text("Telegram API_HASH:")
    config.set("telegram.api_id", int(api_id))
    config.set("telegram.api_hash", (api_hash or "").strip())

    await _provider_setup_flow(first_run=True)
    await _persona_setup_flow()

    name = await _text("Bot name (blank uses your account name):", default=config.get("bot_name", ""))
    config.set("bot_name", (name or "").strip()[:30])

    console.print(f"\n[{OK}]done, config saved to config.json[/]\n")
    return True


# ─────────────────────────── providers / models ─────────────────────────

async def _provider_setup_flow(first_run: bool = False) -> None:
    choices = []
    for name, prov in config.get("providers", {}).items():
        tag = "  [recommended]" if prov.get("recommended") else ""
        choices.append(Choice(title=f"{prov.get('label', name)}{tag}", value=name))
    default = "nvidia" if first_run else config.get("active_provider")
    name = await _select("AI provider:", choices, default=default)
    if not name:
        return
    providers.set_active_provider(name)

    prov = config.get(f"providers.{name}", {})
    if prov.get("needs_key", True):
        if prov.get("signup"):
            console.print(f"[{DIM}]get a key here: {prov['signup']}[/]")
        key = await _text(f"API key ({prov.get('key_hint', '')}):", password=True)
        if key:
            providers.set_key(name, key)
    else:
        console.print(f"[{DIM}]this provider needs no key ({prov.get('key_hint', '')})[/]")

    if name in ("openai_compat", "ollama"):
        url = await _text("base_url (OpenAI-compatible):", default=prov.get("base_url", ""))
        if url:
            config.set(f"providers.{name}.base_url", url.strip())

    await _pick_model(name)


async def _pick_model(name: str) -> None:
    mdls = providers.models(name)
    if not mdls:
        m = await _text("Add at least one model:")
        if m and providers.add_model(name, m):
            mdls = providers.models(name)
    if not mdls:
        return
    choice = await _select("Active model:", [Choice(m, m) for m in mdls],
                           default=config.get("active_model") if config.get("active_model") in mdls else mdls[0])
    if choice:
        providers.set_active_model(choice)


async def providers_menu() -> None:
    while True:
        banner()
        name, prov = providers.active()
        rpm = prov.get("rpm", 40)
        info = Table.grid(padding=(0, 2))
        info.add_column(justify="right", style=DIM)
        info.add_column()
        info.add_row("provider", f"[{P}]{prov.get('label', name)}[/]")
        if prov.get("needs_key", True):
            info.add_row("key", "set" if prov.get("api_key") else f"[{ERR}]none[/]")
        else:
            info.add_row("key", f"[{DIM}]not required[/]")
        info.add_row("model", config.get("active_model") or "none")
        info.add_row("limit", f"~{rpm} requests/min")
        info.add_row("models", ", ".join(providers.models(name)) or "none")
        console.print(Panel(info, title="providers and models", border_style=P, box=box.ROUNDED))
        if name == "nvidia":
            console.print(f"[{DIM}]NVIDIA free tier: ~{rpm} req/min, shared per key, plus starter credits.[/]\n")
        elif name == "ollama":
            console.print(f"[{DIM}]Ollama runs locally, limited only by your hardware. Pull models: ollama pull <name>[/]\n")

        action = await _select("What now?", [
            Choice("🔀 Switch provider", "provider"),
            Choice("🔑 Set API key", "key"),
            Choice("🎯 Pick active model", "pick"),
            Choice("➕ Add model", "add"),
            Choice("➖ Remove model", "remove"),
            Choice("← back", "back"),
        ])
        if action in (None, "back"):
            ai_service._limiter.set_rpm(providers.active_rpm())
            return
        if action == "provider":
            await _provider_pick_only()
        elif action == "key":
            key = await _text("new API key:", password=True)
            if key:
                providers.set_key(name, key)
        elif action == "pick":
            await _pick_model(name)
        elif action == "add":
            m = await _text("model id:")
            if m:
                providers.add_model(name, m)
        elif action == "remove":
            mdls = providers.models(name)
            if mdls:
                m = await _select("which one?", [Choice(x, x) for x in mdls] + [Choice("← cancel", None)])
                if m:
                    providers.remove_model(name, m)


async def _provider_pick_only() -> None:
    choices = [Choice(f"{p.get('label', n)}{'  [recommended]' if p.get('recommended') else ''}", n)
               for n, p in config.get("providers", {}).items()]
    name = await _select("Provider:", choices, default=config.get("active_provider"))
    if name:
        providers.set_active_provider(name)
        prov = config.get(f"providers.{name}", {})
        if prov.get("needs_key", True) and not prov.get("api_key"):
            key = await _text(f"API key for {prov.get('label', name)} ({prov.get('key_hint','')}):", password=True)
            if key:
                providers.set_key(name, key)
        await _pick_model(name)


# ──────────────────────────── persona / prompt ──────────────────────────

async def _persona_setup_flow() -> None:
    choices = []
    for key, (label, kind, desc) in personas.PERSONA_META.items():
        if key == "custom":
            continue
        choices.append(Choice(title=f"{label}  [{kind}] · {desc}", value=key))
    choice = await _select("Persona:", choices, default=config.get("persona", "assistant"))
    if choice:
        config.set("persona", choice)
    lang = await _select("Reply language:", [Choice("English", "en"), Choice("Russian", "ru")],
                         default=config.get("language", "en"))
    if lang:
        config.set("language", lang)


async def persona_menu() -> None:
    while True:
        banner()
        persona = config.get("persona", "assistant")
        meta = personas.PERSONA_META.get(persona, (persona, "", ""))
        preview = personas.render()
        body = Group(
            Text(f"{meta[0]}   language: {config.get('language','en')}", style=P),
            Text(""),
            Panel(Text(preview, style=DIM), title="prompt preview", border_style=DIM, box=box.MINIMAL),
        )
        console.print(Panel(body, title="persona / system prompt", border_style=P, box=box.ROUNDED))

        action = await _select("What now?", [
            Choice("🎭 Pick a template", "pick"),
            Choice("🌐 Reply language", "lang"),
            Choice("✏️ Generate a prompt with AI", "gen"),
            Choice("← back", "back"),
        ])
        if action in (None, "back"):
            return
        if action == "pick":
            choices = [Choice(f"{label} [{kind}] · {desc}", key)
                       for key, (label, kind, desc) in personas.PERSONA_META.items() if key != "custom"]
            c = await _select("Persona:", choices, default=persona)
            if c:
                config.set("persona", c)
        elif action == "lang":
            lang = await _select("Language:", [Choice("English", "en"), Choice("Russian", "ru")],
                                 default=config.get("language", "en"))
            if lang:
                config.set("language", lang)
        elif action == "gen":
            await _generator_flow()


async def _generator_flow() -> None:
    name = await _text("Persona name:", default=config.get("bot_name", ""))
    kind = await _select("Acts as:", [Choice("human (never admits being an AI)", "human"),
                                       Choice("bot (honest AI assistant)", "bot")])
    tone = await _text("Tone / personality (e.g. friendly and concise):")
    lang = await _select("Reply language:", [Choice("English", "en"), Choice("Russian", "ru")],
                         default=config.get("language", "en"))
    extra = await _text("Extra flavor / rules (optional):")
    if not kind:
        return

    with console.status("[cyan]generating prompt with AI…[/]", spinner="dots"):
        prompt = await ai_service.generate_system_prompt(name or "", kind, tone or "", lang, extra or "")

    console.print(Panel(Text(prompt, style=DIM), title="generated prompt", border_style=OK, box=box.ROUNDED))
    if await _confirm("Use this prompt?", default=True):
        config.set("custom_prompt", prompt)
        config.set("persona", "custom")
        config.set("language", lang)
        if name:
            config.set("bot_name", name.strip()[:30])


# ─────────────────────────────── chats ──────────────────────────────────

async def chats_menu() -> None:
    while True:
        banner()
        b = config.get("behavior", {})
        active = config.get("active_chats", [])
        black = config.get("blacklist_chats", [])
        info = Table.grid(padding=(0, 2))
        info.add_column(justify="right", style=DIM)
        info.add_column()
        info.add_row("DMs", _onoff(b.get("reply_in_dm", True)))
        info.add_row("groups", _onoff(b.get("reply_in_groups", True)))
        info.add_row("on mentions", _onoff(b.get("reply_to_mentions", True)))
        info.add_row("on replies", _onoff(b.get("reply_to_replies", True)))
        info.add_row("DMs new dialogues only", _onoff(b.get("dm_new_dialogues_only", False)))
        info.add_row("whitelist", ", ".join(map(str, active)) or f"[{DIM}]empty, reply everywhere[/]")
        info.add_row("blacklist", ", ".join(map(str, black)) or f"[{DIM}]empty[/]")
        console.print(Panel(info, title="chats", border_style=P, box=box.ROUNDED))
        console.print(f"[{DIM}]whitelist: reply only there (always, even if DMs/groups are off). "
                      f"blacklist: never reply.[/]\n")

        action = await _select("What now?", [
            Choice("💬 DMs on/off", "dm"),
            Choice("👥 Groups on/off", "groups"),
            Choice("📢 Mentions on/off", "mentions"),
            Choice("↩️  Replies on/off", "replies"),
            Choice("🆕 DMs new dialogues only on/off", "newonly"),
            Choice("➕ Add chat to whitelist", "add_white"),
            Choice("➖ Remove from whitelist", "del_white"),
            Choice("🚫 Add to blacklist", "add_black"),
            Choice("✅ Remove from blacklist", "del_black"),
            Choice("← back", "back"),
        ])
        if action in (None, "back"):
            return
        toggles = {
            "dm": "reply_in_dm", "groups": "reply_in_groups",
            "mentions": "reply_to_mentions", "replies": "reply_to_replies",
            "newonly": "dm_new_dialogues_only",
        }
        if action in toggles:
            k = toggles[action]
            config.set(f"behavior.{k}", not b.get(k, True if action != "newonly" else False))
        elif action == "add_white":
            await _add_chat("active_chats")
        elif action == "del_white":
            await _del_chat("active_chats")
        elif action == "add_black":
            await _add_chat("blacklist_chats")
        elif action == "del_black":
            await _del_chat("blacklist_chats")


async def _add_chat(list_name: str) -> None:
    raw = await _text("Chat id (number, channels/groups often start with -100):",
                      validate=lambda v: (v.lstrip("-").isdigit()) or "need a numeric id")
    if raw:
        config.add_to_list(list_name, int(raw))


async def _del_chat(list_name: str) -> None:
    lst = config.get(list_name, [])
    if not lst:
        return
    c = await _select("which one?", [Choice(str(x), x) for x in lst] + [Choice("← cancel", None)])
    if c is not None:
        config.remove_from_list(list_name, c)


# ─────────────────────────────── behavior ───────────────────────────────

async def behavior_menu() -> None:
    fields = [
        ("response_delay", "Delay before replying (s)", 0, 30),
        ("per_chat_cooldown", "Per-chat cooldown (s)", 0, 120),
        ("ai_temperature", "Temperature (0..2)", 0, 2),
        ("ai_max_tokens", "Max tokens in a reply", 1, 4000),
        ("history_limit", "History depth (messages)", 1, 1000),
    ]
    while True:
        banner()
        b = config.get("behavior", {})
        info = Table.grid(padding=(0, 2))
        info.add_column(justify="right", style=DIM)
        info.add_column(style=P)
        info.add_row("bot enabled", "yes" if b.get("enabled", True) else "no")
        for key, label, *_ in fields:
            info.add_row(label, str(b.get(key)))
        info.add_row("AI thinking", _onoff(b.get("ai_thinking", False)))
        console.print(Panel(info, title="behavior", border_style=P, box=box.ROUNDED))

        choices = [Choice("⏻ Enable/disable bot", "enabled")]
        choices += [Choice(f"✏️ {label}", key) for key, label, *_ in fields]
        choices.append(Choice("🧠 Thinking on/off", "thinking"))
        choices.append(Choice("← back", "back"))
        action = await _select("What to change?", choices)
        if action in (None, "back"):
            return
        if action == "enabled":
            config.set("behavior.enabled", not b.get("enabled", True))
            continue
        if action == "thinking":
            config.set("behavior.ai_thinking", not b.get("ai_thinking", False))
            continue
        for key, label, lo, hi in fields:
            if action == key:
                raw = await _text(f"{label} [{lo}..{hi}]:", default=str(b.get(key)),
                                  validate=lambda v: _is_number(v) or "enter a number")
                if raw is None:
                    break
                val = float(raw.replace(",", "."))
                val = max(lo, min(hi, val))
                if key in ("ai_max_tokens", "history_limit"):
                    val = int(val)
                config.set(f"behavior.{key}", val)
                break


# ─────────────────────────────── stats ──────────────────────────────────

def stats_panel(client) -> Panel:
    s = ai_service.stats
    t = Table.grid(padding=(0, 2))
    t.add_column(justify="right", style=DIM)
    t.add_column(style=P)
    t.add_row("messages processed", str(s["messages_processed"]))
    t.add_row("AI calls", str(s["ai_calls"]))
    t.add_row("AI errors", str(s["ai_errors"]))
    t.add_row("rate-limit hits", str(s["rate_limited"]))
    t.add_row("chats with history", str(len(ai_service.chat_histories)))
    return Panel(t, title="stats", border_style=P, box=box.ROUNDED)


async def stats_screen(client) -> None:
    banner()
    console.print(stats_panel(client))
    _pause()


# ─────────────────────────────── monitor ────────────────────────────────

_KIND_STYLE = {"incoming": "cyan", "reply": "green", "wait": "yellow", "error": "red", "info": "dim"}
_KIND_ICON = {"incoming": "←", "reply": "→", "wait": "⏳", "error": "✖", "info": "·"}


def _dashboard(client) -> Group:
    header = Text()
    header.append("● ", style=OK if config.get("behavior.enabled", True) else ERR)
    header.append("LIVE  ", style="bold")
    header.append(f"{_provider_label()} · {config.get('active_model') or 'none'}", style=P)
    header.append(f"   ~{providers.active_rpm()} rpm", style=DIM)

    note = ""
    now = time.time()
    for ev in reversed(recent(20)):
        if ev.kind == "wait" and now - ev.ts < 8:
            note = f"  ⏳ {ev.text}"
            break

    feed = Table.grid(padding=(0, 1))
    feed.add_column(width=2)
    feed.add_column(style=DIM, width=8)
    feed.add_column()
    for ev in recent(14):
        st = _KIND_STYLE.get(ev.kind, "white")
        ts = time.strftime("%H:%M:%S", time.localtime(ev.ts))
        feed.add_row(Text(_KIND_ICON.get(ev.kind, "·"), style=st), Text(ts), Text(ev.text, style=st))

    return Group(
        Panel(Text.assemble(header, (note, WARN)), border_style=P, box=box.ROUNDED),
        Panel(feed, title="activity", border_style=DIM, box=box.ROUNDED),
        Align.center(Text("Ctrl+C · back to menu", style=DIM)),
    )


async def live_monitor(client) -> None:
    try:
        with Live(_dashboard(client), console=console, refresh_per_second=4, screen=True) as live:
            while True:
                await asyncio.sleep(0.4)
                live.update(_dashboard(client))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return


# ─────────────────────────────── main menu ──────────────────────────────

async def main_menu(client) -> None:
    while True:
        banner()
        console.print(status_panel())
        console.print()
        action = await _select("Menu", [
            Choice("📡 Monitor (live feed)", "monitor"),
            Choice("🤖 Providers and models", "providers"),
            Choice("🎭 Persona / prompt", "persona"),
            Choice("💬 Chats (DMs, groups, lists)", "chats"),
            Choice("⚙️  Behavior", "behavior"),
            Choice("📊 Stats", "stats"),
            Choice("⏻ Shut down", "quit"),
        ])
        if action in (None, "quit"):
            return
        if action == "monitor":
            await live_monitor(client)
        elif action == "providers":
            await providers_menu()
        elif action == "persona":
            await persona_menu()
        elif action == "chats":
            await chats_menu()
        elif action == "behavior":
            await behavior_menu()
        elif action == "stats":
            await stats_screen(client)
