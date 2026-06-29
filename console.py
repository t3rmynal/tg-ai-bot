"""The console app: banner, first-run wizard, menus and the live monitor.

This replaces the old Telegram control bot. Everything is configured here. The
menu loop and the Telethon client share one event loop, so the bot keeps
answering messages while you navigate menus, and any setting you change applies
to the very next message.
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

# questionary style tuned to match the rich palette
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
    return f"[{OK}]вкл[/]" if value else f"[{DIM}]выкл[/]"


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
    console.input(f"[{DIM}]Enter · назад[/]")


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
    persona = config.get("persona", "troll")
    pmeta = personas.PERSONA_META.get(persona, (persona, "", ""))
    lang = config.get("language", "ru")

    t = Table.grid(padding=(0, 2))
    t.add_column(justify="right", style=DIM)
    t.add_column()
    t.add_row("провайдер", f"[{P}]{_provider_label()}[/]  ·  {config.get('active_model') or 'нет'}")
    t.add_row("персона", f"{pmeta[0]}  [{DIM}]({lang})[/]")
    t.add_row("бот включён", _onoff(b.get("enabled", True)))
    t.add_row("ЛС / группы", f"{_onoff(b.get('reply_in_dm', True))}  /  {_onoff(b.get('reply_in_groups', True))}")
    t.add_row("упоминания / реплаи", f"{_onoff(b.get('reply_to_mentions', True))}  /  {_onoff(b.get('reply_to_replies', True))}")
    t.add_row("белый / чёрный список", f"{len(config.get('active_chats', []))}  /  {len(config.get('blacklist_chats', []))}")
    return Panel(t, title="статус", border_style=P, box=box.ROUNDED)


# ─────────────────────────────── login ──────────────────────────────────

async def interactive_login(client) -> bool:
    """Sign in to Telegram, asking for the code (and 2FA password) in the console."""
    from telethon.errors import SessionPasswordNeededError

    phone = config.get("telegram.phone")
    if not client.is_connected():
        await client.connect()
    if await client.is_user_authorized():
        return True

    console.print(Panel(f"Вхожу в Telegram как [{P}]{phone}[/]. Сейчас придёт код.",
                        border_style=ACCENT, box=box.ROUNDED))
    try:
        await client.send_code_request(phone)
    except Exception as e:
        console.print(f"[{ERR}]не смог отправить код: {e}[/]")
        return False

    for _ in range(3):
        code = await _text("Код из Telegram:")
        if not code:
            return False
        try:
            await client.sign_in(phone=phone, code=code.strip())
            console.print(f"[{OK}]вошёл[/]")
            return True
        except SessionPasswordNeededError:
            for _ in range(3):
                pw = await _text("Пароль 2FA:", password=True)
                if pw is None:
                    return False
                try:
                    await client.sign_in(password=pw)
                    console.print(f"[{OK}]вошёл[/]")
                    return True
                except Exception as e:
                    console.print(f"[{ERR}]неверный пароль: {e}[/]")
            return False
        except Exception as e:
            console.print(f"[{ERR}]неверный код: {e}[/]")
    return False


# ─────────────────────────────── wizard ─────────────────────────────────

async def run_wizard() -> bool:
    banner()
    console.print(Panel(
        "Первый запуск. Соберём пару вещей и поехали.\n"
        f"[{DIM}]API_ID и API_HASH берутся на my.telegram.org/apps[/]",
        title="настройка", border_style=ACCENT, box=box.ROUNDED,
    ))

    api_id = await _text("Telegram API_ID:", validate=lambda v: v.isdigit() or "только цифры")
    if not api_id:
        return False
    api_hash = await _text("Telegram API_HASH:")
    phone = await _text("Номер телефона (с +):", default="+")
    config.set("telegram.api_id", int(api_id))
    config.set("telegram.api_hash", (api_hash or "").strip())
    config.set("telegram.phone", (phone or "").strip())

    await _provider_setup_flow(first_run=True)
    await _persona_setup_flow()

    name = await _text("Как зовут бота (как он себя называет):", default=config.get("bot_name", "бот"))
    if name:
        config.set("bot_name", name.strip()[:30])

    console.print(f"\n[{OK}]готово, конфиг сохранён в config.json[/]\n")
    return True


# ─────────────────────────── providers / models ─────────────────────────

async def _provider_setup_flow(first_run: bool = False) -> None:
    choices = []
    for name, prov in config.get("providers", {}).items():
        tag = f"  [рекоменд.]" if prov.get("recommended") else ""
        choices.append(Choice(title=f"{prov.get('label', name)}{tag}", value=name))
    default = "nvidia" if first_run else config.get("active_provider")
    name = await _select("Провайдер ИИ:", choices, default=default)
    if not name:
        return
    providers.set_active_provider(name)

    prov = config.get(f"providers.{name}", {})
    if prov.get("signup"):
        console.print(f"[{DIM}]ключ берётся тут: {prov['signup']}[/]")
    key = await _text(f"API-ключ ({prov.get('key_hint', '')}):", password=True)
    if key:
        providers.set_key(name, key)

    if name == "openai_compat":
        url = await _text("base_url (OpenAI-совместимый):", default=prov.get("base_url", ""))
        if url:
            config.set(f"providers.{name}.base_url", url.strip())
        m = await _text("Модель (можно добавить ещё позже):")
        if m:
            providers.add_model(name, m)

    await _pick_model(name)


async def _pick_model(name: str) -> None:
    mdls = providers.models(name)
    if not mdls:
        m = await _text("Добавь хотя бы одну модель:")
        if m and providers.add_model(name, m):
            mdls = providers.models(name)
    if not mdls:
        return
    choice = await _select("Активная модель:", [Choice(m, m) for m in mdls],
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
        info.add_row("провайдер", f"[{P}]{prov.get('label', name)}[/]")
        info.add_row("ключ", "задан" if prov.get("api_key") else f"[{ERR}]нет[/]")
        info.add_row("модель", config.get("active_model") or "нет")
        info.add_row("лимит", f"~{rpm} запросов/мин")
        info.add_row("модели", ", ".join(providers.models(name)) or "нет")
        console.print(Panel(info, title="провайдеры и модели", border_style=P, box=box.ROUNDED))
        if name == "nvidia":
            console.print(f"[{DIM}]NVIDIA free tier: ~{rpm} req/min (~0.67/сек), общий на ключ, "
                          f"~57.6k/день в теории + стартовые кредиты.[/]\n")

        action = await _select("Что делаем?", [
            Choice("🔀 Сменить провайдера", "provider"),
            Choice("🔑 Задать API-ключ", "key"),
            Choice("🎯 Выбрать активную модель", "pick"),
            Choice("➕ Добавить модель", "add"),
            Choice("➖ Удалить модель", "remove"),
            Choice("← назад", "back"),
        ])
        if action in (None, "back"):
            ai_service._limiter.set_rpm(providers.active_rpm())
            return
        if action == "provider":
            await _provider_pick_only()
        elif action == "key":
            key = await _text("новый API-ключ:", password=True)
            if key:
                providers.set_key(name, key)
        elif action == "pick":
            await _pick_model(name)
        elif action == "add":
            m = await _text("id модели:")
            if m:
                providers.add_model(name, m)
        elif action == "remove":
            mdls = providers.models(name)
            if mdls:
                m = await _select("какую убрать?", [Choice(x, x) for x in mdls] + [Choice("← отмена", None)])
                if m:
                    providers.remove_model(name, m)


async def _provider_pick_only() -> None:
    choices = [Choice(f"{p.get('label', n)}{'  [рекоменд.]' if p.get('recommended') else ''}", n)
               for n, p in config.get("providers", {}).items()]
    name = await _select("Провайдер:", choices, default=config.get("active_provider"))
    if name:
        providers.set_active_provider(name)
        prov = config.get(f"providers.{name}", {})
        if not prov.get("api_key"):
            key = await _text(f"API-ключ для {prov.get('label', name)} ({prov.get('key_hint','')}):", password=True)
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
    choice = await _select("Персона:", choices, default=config.get("persona", "troll"))
    if choice:
        config.set("persona", choice)
    lang = await _select("Язык ответов:", [Choice("русский", "ru"), Choice("English", "en")],
                         default=config.get("language", "ru"))
    if lang:
        config.set("language", lang)


async def persona_menu() -> None:
    while True:
        banner()
        persona = config.get("persona", "troll")
        meta = personas.PERSONA_META.get(persona, (persona, "", ""))
        preview = personas.render()
        body = Group(
            Text(f"{meta[0]}   язык: {config.get('language','ru')}", style=P),
            Text(""),
            Panel(Text(preview, style=DIM), title="предпросмотр промпта", border_style=DIM, box=box.MINIMAL),
        )
        console.print(Panel(body, title="персона / системный промпт", border_style=P, box=box.ROUNDED))

        action = await _select("Что делаем?", [
            Choice("🎭 Выбрать шаблон", "pick"),
            Choice("🌐 Язык ответов", "lang"),
            Choice("✏️ Сгенерировать свой промпт", "gen"),
            Choice("← назад", "back"),
        ])
        if action in (None, "back"):
            return
        if action == "pick":
            choices = [Choice(f"{label} [{kind}] · {desc}", key)
                       for key, (label, kind, desc) in personas.PERSONA_META.items() if key != "custom"]
            c = await _select("Персона:", choices, default=persona)
            if c:
                config.set("persona", c)
        elif action == "lang":
            lang = await _select("Язык:", [Choice("русский", "ru"), Choice("English", "en")],
                                 default=config.get("language", "ru"))
            if lang:
                config.set("language", lang)
        elif action == "gen":
            await _generator_flow()


async def _generator_flow() -> None:
    name = await _text("Имя персонажа:", default=config.get("bot_name", "бот"))
    kind = await _select("Кто это?", [Choice("человек (ведёт себя как человек)", "человек"),
                                       Choice("бот (честно говорит, что он ии)", "бот")])
    tone = await _text("Стиль/характер (напр. дружелюбный и краткий):")
    lang = await _select("Язык:", [Choice("русский", "ru"), Choice("English", "en")],
                         default=config.get("language", "ru"))
    extra = await _text("Доп. правила (необязательно):")
    if not (name and kind):
        return
    prompt = personas.build_custom(name, kind, tone or "", lang, extra or "")
    console.print(Panel(Text(prompt, style=DIM), title="получилось", border_style=OK, box=box.ROUNDED))
    if await _confirm("Использовать этот промпт?", default=True):
        config.set("custom_prompt", prompt)
        config.set("persona", "custom")
        config.set("language", lang)
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
        info.add_row("ЛС", _onoff(b.get("reply_in_dm", True)))
        info.add_row("группы", _onoff(b.get("reply_in_groups", True)))
        info.add_row("на упоминания", _onoff(b.get("reply_to_mentions", True)))
        info.add_row("на реплаи", _onoff(b.get("reply_to_replies", True)))
        info.add_row("ЛС только новые диалоги", _onoff(b.get("dm_new_dialogues_only", False)))
        info.add_row("белый список", ", ".join(map(str, active)) or f"[{DIM}]пусто, отвечаю везде[/]")
        info.add_row("чёрный список", ", ".join(map(str, black)) or f"[{DIM}]пусто[/]")
        console.print(Panel(info, title="чаты", border_style=P, box=box.ROUNDED))
        console.print(f"[{DIM}]белый список: отвечаю только там (и всегда, даже если ЛС/группы выключены). "
                      f"чёрный: не отвечаю никогда.[/]\n")

        action = await _select("Что делаем?", [
            Choice("💬 ЛС вкл/выкл", "dm"),
            Choice("👥 Группы вкл/выкл", "groups"),
            Choice("📢 Упоминания вкл/выкл", "mentions"),
            Choice("↩️  Реплаи вкл/выкл", "replies"),
            Choice("🆕 ЛС только новые диалоги вкл/выкл", "newonly"),
            Choice("➕ Добавить чат в белый список", "add_white"),
            Choice("➖ Убрать из белого списка", "del_white"),
            Choice("🚫 Добавить в чёрный список", "add_black"),
            Choice("✅ Убрать из чёрного списка", "del_black"),
            Choice("← назад", "back"),
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
    raw = await _text("ID чата (число, для каналов/групп часто с -100):",
                      validate=lambda v: (v.lstrip("-").isdigit()) or "нужен числовой id")
    if raw:
        config.add_to_list(list_name, int(raw))


async def _del_chat(list_name: str) -> None:
    lst = config.get(list_name, [])
    if not lst:
        return
    c = await _select("какой убрать?", [Choice(str(x), x) for x in lst] + [Choice("← отмена", None)])
    if c is not None:
        config.remove_from_list(list_name, c)


# ─────────────────────────────── behavior ───────────────────────────────

async def behavior_menu() -> None:
    fields = [
        ("response_delay", "Задержка перед ответом (сек)", 0, 30),
        ("per_chat_cooldown", "Кулдаун в одном чате (сек)", 0, 120),
        ("ai_temperature", "Температура (0..2)", 0, 2),
        ("ai_max_tokens", "Макс. токенов в ответе", 1, 4000),
        ("history_limit", "Глубина истории (сообщений)", 1, 1000),
    ]
    while True:
        banner()
        b = config.get("behavior", {})
        info = Table.grid(padding=(0, 2))
        info.add_column(justify="right", style=DIM)
        info.add_column(style=P)
        info.add_row("бот включён", "да" if b.get("enabled", True) else "нет")
        for key, label, *_ in fields:
            info.add_row(label, str(b.get(key)))
        console.print(Panel(info, title="поведение", border_style=P, box=box.ROUNDED))

        choices = [Choice("⏻ Включить/выключить бота", "enabled")]
        choices += [Choice(f"✏️ {label}", key) for key, label, *_ in fields]
        choices.append(Choice("← назад", "back"))
        action = await _select("Что меняем?", choices)
        if action in (None, "back"):
            return
        if action == "enabled":
            config.set("behavior.enabled", not b.get("enabled", True))
            continue
        for key, label, lo, hi in fields:
            if action == key:
                raw = await _text(f"{label} [{lo}..{hi}]:", default=str(b.get(key)),
                                  validate=lambda v: _is_number(v) or "введи число")
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
    t.add_row("обработано сообщений", str(s["messages_processed"]))
    t.add_row("вызовов ИИ", str(s["ai_calls"]))
    t.add_row("ошибок ИИ", str(s["ai_errors"]))
    t.add_row("попаданий в лимит", str(s["rate_limited"]))
    t.add_row("чатов с историей", str(len(ai_service.chat_histories)))
    return Panel(t, title="статистика", border_style=P, box=box.ROUNDED)


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
    header.append(f"{_provider_label()} · {config.get('active_model') or 'нет'}", style=P)
    header.append(f"   ~{providers.active_rpm()} rpm", style=DIM)

    # rate-limit hint if we waited recently
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
        Panel(feed, title="активность", border_style=DIM, box=box.ROUNDED),
        Align.center(Text("Ctrl+C · назад в меню", style=DIM)),
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
        action = await _select("Меню", [
            Choice("📡 Монитор (живая лента)", "monitor"),
            Choice("🤖 Провайдеры и модели", "providers"),
            Choice("🎭 Персона / промпт", "persona"),
            Choice("💬 Чаты (ЛС, группы, списки)", "chats"),
            Choice("⚙️  Поведение", "behavior"),
            Choice("📊 Статистика", "stats"),
            Choice("⏻ Выключить", "quit"),
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
