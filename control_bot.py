"""
Управляющий бот - через него настраиваешь userbot
"""

import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

import storage
from ai_service import clear_history, chat_histories


def admin_only(func):
    """Декоратор - только для админа"""
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id != ADMIN_ID:
            await message.answer("не твоё")
            return
        return await func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статус"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="💬 Чаты"), KeyboardButton(text="🗑️ Очистить историю")],
            [KeyboardButton(text="🔄 Перезапустить AI")]
        ],
        resize_keyboard=True
    )


def get_status_text() -> str:
    enabled = storage.get("enabled")
    bot_name = storage.get("bot_name")
    reply_dm = storage.get("reply_in_dm")
    reply_mentions = storage.get("reply_to_mentions")
    reply_replies = storage.get("reply_to_replies")
    delay = storage.get("response_delay")
    active_chats = storage.get("active_chats")
    blacklist = storage.get("blacklist_chats")
    history_count = len(chat_histories)
    
    status_emoji = "✅" if enabled else "❌"
    
    return (
        f"**Статус бота**\n\n"
        f"{status_emoji} Включён: {enabled}\n"
        f"👤 Имя: {bot_name}\n"
        f"💬 Отвечать в ЛС: {'да' if reply_dm else 'нет'}\n"
        f"📢 На упоминания: {'да' if reply_mentions else 'нет'}\n"
        f"↩️ На реплаи: {'да' if reply_replies else 'нет'}\n"
        f"⏱ Задержка: {delay} сек\n"
        f"📋 Активных чатов (белый список): {len(active_chats)}\n"
        f"🚫 Чёрный список: {len(blacklist)}\n"
        f"🧠 Чатов с историей: {history_count}"
    )


@dp.message(Command("start"))
@admin_only
async def cmd_start(message: types.Message):
    await message.answer(
        "управляющий бот запущен\n\nвыбирай что хочешь",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == "📊 Статус")
@admin_only
async def show_status(message: types.Message):
    await message.answer(get_status_text(), parse_mode="Markdown")


@dp.message(F.text == "⚙️ Настройки")
@admin_only
async def show_settings(message: types.Message):
    enabled = storage.get("enabled")
    reply_dm = storage.get("reply_in_dm")
    reply_mentions = storage.get("reply_to_mentions")
    reply_replies = storage.get("reply_to_replies")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅' if enabled else '❌'} Бот {'вкл' if enabled else 'выкл'}",
                callback_data="toggle_enabled"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if reply_dm else '❌'} ЛС",
                callback_data="toggle_dm"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if reply_mentions else '❌'} Упоминания",
                callback_data="toggle_mentions"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if reply_replies else '❌'} Реплаи",
                callback_data="toggle_replies"
            )
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить имя", callback_data="change_name"),
            InlineKeyboardButton(text="⏱ Изменить задержку", callback_data="change_delay")
        ]
    ])
    
    await message.answer("настройки:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_setting(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("не твоё")
        return
    
    action = callback.data.replace("toggle_", "")
    
    mapping = {
        "enabled": "enabled",
        "dm": "reply_in_dm",
        "mentions": "reply_to_mentions",
        "replies": "reply_to_replies"
    }
    
    key = mapping.get(action)
    if not key:
        await callback.answer("неизвестная настройка")
        return
    
    current = storage.get(key)
    storage.set_val(key, not current)
    new_val = not current
    
    await callback.answer(f"{'включено' if new_val else 'выключено'}")
    
    # Обновляем сообщение
    enabled = storage.get("enabled")
    reply_dm = storage.get("reply_in_dm")
    reply_mentions = storage.get("reply_to_mentions")
    reply_replies = storage.get("reply_to_replies")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅' if enabled else '❌'} Бот {'вкл' if enabled else 'выкл'}",
                callback_data="toggle_enabled"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if reply_dm else '❌'} ЛС",
                callback_data="toggle_dm"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if reply_mentions else '❌'} Упоминания",
                callback_data="toggle_mentions"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if reply_replies else '❌'} Реплаи",
                callback_data="toggle_replies"
            )
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить имя", callback_data="change_name"),
            InlineKeyboardButton(text="⏱ Изменить задержку", callback_data="change_delay")
        ]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass


# Ожидание ввода с блокировкой для безопасности
waiting_for: dict[int, str] = {}
waiting_for_lock = asyncio.Lock()


@dp.callback_query(F.data == "change_name")
async def change_name_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        waiting_for[callback.from_user.id] = "name"
    await callback.answer()
    await callback.message.answer(
        f"текущее имя: {storage.get('bot_name')}\n\nнапиши новое имя:"
    )


@dp.callback_query(F.data == "change_delay")
async def change_delay_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    async with waiting_for_lock:
        waiting_for[callback.from_user.id] = "delay"
    await callback.answer()
    await callback.message.answer(
        f"текущая задержка: {storage.get('response_delay')} сек\n\nнапиши новое значение (например 2.5):"
    )


@dp.message(F.text == "💬 Чаты")
@admin_only
async def manage_chats(message: types.Message):
    active = storage.get("active_chats")
    blacklist = storage.get("blacklist_chats")
    
    text = "**управление чатами**\n\n"
    
    if active:
        text += f"белый список (отвечаю только здесь):\n"
        for chat_id in active:
            text += f"  - `{chat_id}`\n"
    else:
        text += "белый список пуст (отвечаю везде)\n"
    
    text += "\n"
    
    if blacklist:
        text += f"чёрный список (никогда не отвечаю):\n"
        for chat_id in blacklist:
            text += f"  - `{chat_id}`\n"
    else:
        text += "чёрный список пуст\n"
    
    text += (
        "\n**команды:**\n"
        "/add\\_white 123456 - добавить в белый список\n"
        "/del\\_white 123456 - убрать из белого списка\n"
        "/add\\_black 123456 - добавить в чёрный список\n"
        "/del\\_black 123456 - убрать из чёрного списка\n"
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
            storage.set_val("active_chats", active)
        await message.answer(f"добавил {chat_id} в белый список")
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
            storage.set_val("active_chats", active)
            await message.answer(f"убрал {chat_id} из белого списка")
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
            storage.set_val("blacklist_chats", blacklist)
        await message.answer(f"добавил {chat_id} в чёрный список")
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
            storage.set_val("blacklist_chats", blacklist)
            await message.answer(f"убрал {chat_id} из чёрного списка")
        else:
            await message.answer("этого чата нет в чёрном списке")
    except ValueError:
        await message.answer("некорректный id")


@dp.message(Command("clear_white"))
@admin_only
async def clear_white(message: types.Message):
    storage.set_val("active_chats", [])
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
        await message.answer(f"история чата {chat_id} очищена")
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
                reply_markup=get_main_keyboard()
            )
            return
        
        action = waiting_for.pop(user_id)
    
    if action == "name":
        new_name = message.text.strip()
        if len(new_name) > 30:
            await message.answer("имя слишком длинное, максимум 30 символов")
            return
        storage.set_val("bot_name", new_name)
        await message.answer(f"имя изменено на: {new_name}")
    
    elif action == "delay":
        try:
            delay = float(message.text.strip().replace(",", "."))
            if delay < 0 or delay > 10:
                await message.answer("задержка должна быть от 0 до 10 секунд")
                return
            storage.set_val("response_delay", delay)
            await message.answer(f"задержка изменена на {delay} сек")
        except ValueError:
            await message.answer("введи число, например 1.5")


async def start_control_bot():
    print("[ControlBot] Запуск...")
    await dp.start_polling(bot)