import asyncio
import logging
import os
import time
import unicodedata

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

import storage
from ai_service import clear_history, chat_histories, stats

START_TIME = time.monotonic()

AVAILABLE_MODELS = [
    "minimax/minimax-m2.5:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-235b-a22b:free",
]

def admin_only(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id != ADMIN_ID:
            await message.answer("не твоё")
            logger.warning(f"[ControlBot] Попытка доступа: user_id={message.from_user.id}")
            return
        return await func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def sanitize_name(text: str) -> str:
    """Убираем управляющие символы, оставляем только печатаемые."""
    return "".join(c for c in text if unicodedata.category(c)[0] != "C").strip()


def get_uptime() -> str:
    seconds = int(time.monotonic() - START_TIME)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}ч {m}м {s}с"

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статус"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="💬 Чаты"), KeyboardButton(text="🗑️ Очистить историю")],
            [KeyboardButton(text="🔄 Перезапустить AI"), KeyboardButton(text="📈 Статистика")],
        ],
        resize_keyboard=True,
    )


def get_status_text() -> str:
    enabled = storage.get("enabled")
    bot_name = storage.get("bot_name")
    reply_dm = storage.get("reply_in_dm")
    reply_mentions = storage.get("reply_to_mentions")
    reply_replies = storage.get("reply_to_replies")
    delay = storage.get("response_delay")
    rate_limit = storage.get("rate_limit_seconds")
    active_chats = storage.get("active_chats")
    blacklist = storage.get("blacklist_chats")
    history_count = len(chat_histories)
    model = storage.get("ai_model")
    temperature = storage.get("ai_temperature")

    return (
        f"**Статус бота**\n\n"
        f"{'✅' if enabled else '❌'} Включён: {enabled}\n"
        f"👤 Имя: {bot_name}\n"
        f"💬 Отвечать в ЛС: {'да' if reply_dm else 'нет'}\n"
        f"📢 На упоминания: {'да' if reply_mentions else 'нет'}\n"
        f"↩️ На реплаи: {'да' if reply_replies else 'нет'}\n"
        f"⏱ Задержка ответа: {delay} сек\n"
        f"🚦 Rate limit: {rate_limit} сек\n"
        f"📋 Белый список: {len(active_chats)} чатов\n"
        f"🚫 Чёрный список: {len(blacklist)} чатов\n"
        f"🧠 Чатов с историей: {history_count}\n"
        f"🤖 Модель: `{model}`\n"
        f"🌡 Температура: {temperature}"
    )


def _build_settings_keyboard() -> InlineKeyboardMarkup:
    enabled = storage.get("enabled")
    reply_dm = storage.get("reply_in_dm")
    reply_mentions = storage.get("reply_to_mentions")
    reply_replies = storage.get("reply_to_replies")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅' if enabled else '❌'} Бот {'вкл' if enabled else 'выкл'}",
            callback_data="toggle_enabled",
        )],
        [
            InlineKeyboardButton(
                text=f"{'✅' if reply_dm else '❌'} ЛС",
                callback_data="toggle_dm",
            ),
            InlineKeyboardButton(
                text=f"{'✅' if reply_mentions else '❌'} Упоминания",
                callback_data="toggle_mentions",
            ),
        ],
        [InlineKeyboardButton(
            text=f"{'✅' if reply_replies else '❌'} Реплаи",
            callback_data="toggle_replies",
        )],
        [
            InlineKeyboardButton(text="✏️ Имя", callback_data="change_name"),
            InlineKeyboardButton(text="⏱ Задержка", callback_data="change_delay"),
        ],
        [
            InlineKeyboardButton(text="🚦 Rate limit", callback_data="change_rate_limit"),
            InlineKeyboardButton(text="🌡 Температура", callback_data="change_temperature"),
        ],
        [InlineKeyboardButton(text="🤖 Сменить модель", callback_data="change_model")],
    ])

@dp.message(Command("start"))
@admin_only
async def cmd_start(message: types.Message):
    await message.answer(
        "управляющий бот запущен\n\nвыбирай что хочешь",
        reply_markup=get_main_keyboard(),
    )


@dp.message(Command("ping"))
@admin_only
async def cmd_ping(message: types.Message):
    await message.answer(f"понг, аптайм: {get_uptime()}")


@dp.message(F.text == "📊 Статус")
@admin_only
async def show_status(message: types.Message):
    await message.answer(get_status_text(), parse_mode="Markdown")


@dp.message(F.text == "⚙️ Настройки")
@admin_only
async def show_settings(message: types.Message):
    await message.answer("настройки:", reply_markup=_build_settings_keyboard())


@dp.message(F.text == "📈 Статистика")
@admin_only
async def show_stats(message: types.Message):
    text = (
        f"**Статистика**\n\n"
        f"⏱ Аптайм: {get_uptime()}\n"
        f"📨 Обработано сообщений: {stats['messages_processed']}\n"
        f"🤖 AI-вызовов: {stats['ai_calls']}\n"
        f"❌ AI-ошибок: {stats['ai_errors']}\n"
        f"🧠 Активных историй: {len(chat_histories)}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_setting(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("не твоё")
        return

    mapping = {
        "toggle_enabled": "enabled",
        "toggle_dm": "reply_in_dm",
        "toggle_mentions": "reply_to_mentions",
        "toggle_replies": "reply_to_replies",
    }
    key = mapping.get(callback.data)
    if not key:
        await callback.answer("неизвестная настройка")
        return

    new_val = not storage.get(key)
    await storage.set_async(key, new_val)
    await callback.answer("включено" if new_val else "выключено")

    try:
        await callback.message.edit_reply_markup(reply_markup=_build_settings_keyboard())
    except Exception:
        pass


@dp.callback_query(F.data == "change_model")
async def change_model_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    current = storage.get("ai_model")
    buttons = [
        [InlineKeyboardButton(
            text=f"{'✅ ' if m == current else ''}{m.split('/')[1] if '/' in m else m}",
            callback_data=f"set_model:{m}",
        )]
        for m in AVAILABLE_MODELS
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.answer()
    await callback.message.answer(f"текущая модель: `{current}`\n\nвыбери:", parse_mode="Markdown", reply_markup=kb)


@dp.callback_query(F.data.startswith("set_model:"))
async def set_model(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    model = callback.data.removeprefix("set_model:")
    if model not in AVAILABLE_MODELS:
        await callback.answer("неизвестная модель")
        return

    await storage.set_async("ai_model", model)
    await callback.answer(f"модель: {model}")
    await callback.message.answer(f"✅ модель изменена на `{model}`", parse_mode="Markdown")

waiting_for: dict[int, str] = {}
waiting_for_lock = asyncio.Lock()
_expire_tasks: dict[int, asyncio.Task] = {}


async def _expire_waiting(user_id: int, delay: float = 60.0) -> None:
    """Автоматически снимает состояние ожидания через `delay` секунд."""
    await asyncio.sleep(delay)
    async with waiting_for_lock:
        if user_id in waiting_for:
            del waiting_for[user_id]
            logger.debug(f"[ControlBot] waiting_for expired for user {user_id}")


def _set_waiting(user_id: int, action: str) -> None:
    waiting_for[user_id] = action
    if user_id in _expire_tasks:
        _expire_tasks[user_id].cancel()
    _expire_tasks[user_id] = asyncio.create_task(_expire_waiting(user_id))


@dp.callback_query(F.data == "change_name")
async def change_name_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        _set_waiting(callback.from_user.id, "name")
    await callback.answer()
    await callback.message.answer(
        f"текущее имя: {storage.get('bot_name')}\n\nнапиши новое имя (макс 30 символов):"
    )


@dp.callback_query(F.data == "change_delay")
async def change_delay_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        _set_waiting(callback.from_user.id, "delay")
    await callback.answer()
    await callback.message.answer(
        f"текущая задержка: {storage.get('response_delay')} сек\n\nнапиши новое значение (0–10):"
    )


@dp.callback_query(F.data == "change_rate_limit")
async def change_rate_limit_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        _set_waiting(callback.from_user.id, "rate_limit")
    await callback.answer()
    await callback.message.answer(
        f"текущий rate limit: {storage.get('rate_limit_seconds')} сек\n\nнапиши новое значение (0–60):"
    )


@dp.callback_query(F.data == "change_temperature")
async def change_temperature_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        _set_waiting(callback.from_user.id, "temperature")
    await callback.answer()
    await callback.message.answer(
        f"текущая температура: {storage.get('ai_temperature')}\n\nнапиши новое значение (0.0–2.0):"
    )
    
@dp.message(F.text == "💬 Чаты")
@admin_only
async def manage_chats(message: types.Message):
    active = storage.get("active_chats")
    blacklist = storage.get("blacklist_chats")

    text = "**управление чатами**\n\n"
    if active:
        text += "белый список (отвечаю только здесь):\n"
        for cid in active:
            text += f"  - `{cid}`\n"
    else:
        text += "белый список пуст (отвечаю везде)\n"

    text += "\n"
    if blacklist:
        text += "чёрный список (никогда не отвечаю):\n"
        for cid in blacklist:
            text += f"  - `{cid}`\n"
    else:
        text += "чёрный список пуст\n"

    text += (
        "\n**команды:**\n"
        "/add\\_white 123456 - добавить в белый список\n"
        "/del\\_white 123456 - убрать из белого\n"
        "/add\\_black 123456 - добавить в чёрный список\n"
        "/del\\_black 123456 - убрать из чёрного\n"
        "/clear\\_white - очистить белый список\n"
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("add_white"))
@admin_only
async def add_white(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("использование: /add_white 123456789")
        return
    try:
        chat_id = int(parts[1])
        active = storage.get("active_chats")
        if chat_id not in active:
            active.append(chat_id)
            await storage.set_async("active_chats", active)
        await message.answer(f"добавил `{chat_id}` в белый список", parse_mode="Markdown")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(Command("del_white"))
@admin_only
async def del_white(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("использование: /del_white 123456789")
        return
    try:
        chat_id = int(parts[1])
        active = storage.get("active_chats")
        if chat_id in active:
            active.remove(chat_id)
            await storage.set_async("active_chats", active)
            await message.answer(f"убрал `{chat_id}` из белого списка", parse_mode="Markdown")
        else:
            await message.answer("этого чата нет в белом списке")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(Command("add_black"))
@admin_only
async def add_black(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("использование: /add_black 123456789")
        return
    try:
        chat_id = int(parts[1])
        blacklist = storage.get("blacklist_chats")
        if chat_id not in blacklist:
            blacklist.append(chat_id)
            await storage.set_async("blacklist_chats", blacklist)
        await message.answer(f"добавил `{chat_id}` в чёрный список", parse_mode="Markdown")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(Command("del_black"))
@admin_only
async def del_black(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("использование: /del_black 123456789")
        return
    try:
        chat_id = int(parts[1])
        blacklist = storage.get("blacklist_chats")
        if chat_id in blacklist:
            blacklist.remove(chat_id)
            await storage.set_async("blacklist_chats", blacklist)
            await message.answer(f"убрал `{chat_id}` из чёрного списка", parse_mode="Markdown")
        else:
            await message.answer("этого чата нет в чёрном списке")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(Command("clear_white"))
@admin_only
async def clear_white(message: types.Message):
    await storage.set_async("active_chats", [])
    await message.answer("белый список очищен, теперь отвечаю везде")
    
@dp.message(F.text == "🗑️ Очистить историю")
@admin_only
async def clear_all_history(message: types.Message):
    count = len(chat_histories)
    chat_histories.clear()
    await message.answer(f"очищена история {count} чатов")


@dp.message(Command("clear_chat"))
@admin_only
async def clear_chat_history(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("использование: /clear_chat 123456789")
        return
    try:
        chat_id = int(parts[1])
        clear_history(chat_id)
        await message.answer(f"история чата `{chat_id}` очищена", parse_mode="Markdown")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(F.text == "🔄 Перезапустить AI")
@admin_only
async def restart_ai(message: types.Message):
    chat_histories.clear()
    await message.answer("ai перезапущен, вся история очищена")

@dp.message()
@admin_only
async def handle_text_input(message: types.Message):
    user_id = message.from_user.id

    async with waiting_for_lock:
        if user_id not in waiting_for:
            await message.answer(
                "не понял команду, используй кнопки",
                reply_markup=get_main_keyboard(),
            )
            return
        action = waiting_for.pop(user_id)
        if user_id in _expire_tasks:
            _expire_tasks[user_id].cancel()
            del _expire_tasks[user_id]

    if action == "name":
        new_name = sanitize_name(message.text)
        if not new_name:
            await message.answer("имя не может быть пустым")
            return
        if len(new_name) > 30:
            await message.answer("имя слишком длинное, максимум 30 символов")
            return
        await storage.set_async("bot_name", new_name)
        await message.answer(f"имя изменено на: {new_name}")

    elif action == "delay":
        try:
            delay = float(message.text.strip().replace(",", "."))
            if not (0 <= delay <= 10):
                await message.answer("задержка должна быть от 0 до 10 секунд")
                return
            await storage.set_async("response_delay", delay)
            await message.answer(f"задержка изменена на {delay} сек")
        except ValueError:
            await message.answer("введи число, например 1.5")

    elif action == "rate_limit":
        try:
            val = float(message.text.strip().replace(",", "."))
            if not (0 <= val <= 60):
                await message.answer("значение должно быть от 0 до 60 секунд")
                return
            await storage.set_async("rate_limit_seconds", val)
            await message.answer(f"rate limit изменён на {val} сек")
        except ValueError:
            await message.answer("введи число, например 3")

    elif action == "temperature":
        try:
            val = float(message.text.strip().replace(",", "."))
            if not (0.0 <= val <= 2.0):
                await message.answer("температура должна быть от 0.0 до 2.0")
                return
            await storage.set_async("ai_temperature", val)
            await message.answer(f"температура изменена на {val}")
        except ValueError:
            await message.answer("введи число, например 0.85")


async def start_control_bot():
    logger.info("[ControlBot] Запуск...")
    await dp.start_polling(bot)
