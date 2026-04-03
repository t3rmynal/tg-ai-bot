"""
Userbot — сидит на твоём аккаунте и отвечает на сообщения.
"""

import asyncio
import logging
import os
import re
import time
from collections import OrderedDict

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityMention,
    MessageEntityMentionName,
    User,
)

load_dotenv()

logger = logging.getLogger(__name__)

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
PHONE = os.getenv("TG_PHONE")

from ai_service import ask_ai
import storage

client = TelegramClient("userbot", API_ID, API_HASH)

# OrderedDict как ordered set: ключ = message_id, значение = True
# Позволяет удалять именно старые записи (FIFO), а не случайные
MAX_SENT_CACHE = 500
bot_sent_messages: OrderedDict[int, bool] = OrderedDict()

# Rate limit: chat_id → timestamp последнего ответа
_last_response_time: dict[int, float] = {}


def _track_sent(msg_id: int) -> None:
    bot_sent_messages[msg_id] = True
    while len(bot_sent_messages) > MAX_SENT_CACHE:
        bot_sent_messages.popitem(last=False)  # удаляем самый старый


def is_reply_to_bot(message) -> bool:
    if not message.reply_to:
        return False
    return message.reply_to.reply_to_msg_id in bot_sent_messages


def _is_rate_limited(chat_id: int) -> bool:
    cooldown = storage.get("rate_limit_seconds") or 3.0
    last = _last_response_time.get(chat_id, 0.0)
    return (time.monotonic() - last) < cooldown


def _update_rate_limit(chat_id: int) -> None:
    _last_response_time[chat_id] = time.monotonic()


async def get_my_username() -> tuple[str, int]:
    me = await client.get_me()
    username = me.username or ""
    return username.lower(), me.id


async def is_mentioned(message, my_username: str, my_id: int) -> bool:
    if not message.text:
        return False

    # Быстрая проверка по тексту
    if my_username and f"@{my_username}" in message.text.lower():
        return True

    if not message.entities:
        return False

    for entity in message.entities:
        if isinstance(entity, MessageEntityMentionName):
            if entity.user_id == my_id:
                return True
        elif isinstance(entity, MessageEntityMention):
            start = entity.offset
            end = entity.offset + entity.length
            mention_text = message.text[start:end].lower().lstrip("@")
            if mention_text == my_username:
                return True

    return False


@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    message = event.message
    chat_id = event.chat_id

    if message.out or not message.text:
        return

    if not storage.is_chat_allowed(chat_id):
        return

    if _is_rate_limited(chat_id):
        logger.debug(f"[Userbot] Rate limit: {chat_id}")
        return

    my_username, my_id = await get_my_username()

    is_private = isinstance(event.chat, User) or event.is_private
    is_group = not is_private

    should_respond = False

    if is_private and storage.get("reply_in_dm"):
        should_respond = True

    if is_group:
        mentioned = await is_mentioned(message, my_username, my_id)
        replied_to_bot = is_reply_to_bot(message)

        if mentioned and storage.get("reply_to_mentions"):
            should_respond = True
        if replied_to_bot and storage.get("reply_to_replies"):
            should_respond = True

    if not should_respond:
        return

    user_text = message.text
    if my_username:
        user_text = re.sub(
            rf"@{re.escape(my_username)}", "", user_text, flags=re.IGNORECASE
        ).strip()

    if not user_text:
        user_text = "привет"

    sender = await event.get_sender()
    sender_name = ""
    if sender:
        sender_name = getattr(sender, "first_name", None) or getattr(sender, "title", "")

    extra_context = f"тебя написал(а): {sender_name}" if sender_name else ""

    delay = storage.get("response_delay")
    if delay and delay > 0:
        await asyncio.sleep(delay)

    async with client.action(chat_id, "typing"):
        bot_name = storage.get("bot_name")
        response = await ask_ai(
            chat_id=chat_id,
            user_message=user_text,
            bot_name=bot_name,
            extra_context=extra_context,
        )

    _update_rate_limit(chat_id)

    try:
        if is_group:
            sent = await event.reply(response)
        else:
            sent = await client.send_message(chat_id, response)
        _track_sent(sent.id)
        logger.info(f"[Userbot] Ответил в {chat_id}: {response[:60]}...")
    except Exception as e:
        logger.error(f"[Userbot] Не удалось отправить сообщение в {chat_id}: {e}")


@client.on(events.NewMessage(outgoing=True))
async def track_own_messages(event):
    if event.message.id:
        _track_sent(event.message.id)


async def start_userbot():
    logger.info("[Userbot] Запуск...")
    await client.start(phone=PHONE)
    me = await client.get_me()
    logger.info(f"[Userbot] Авторизован как: {me.first_name} (@{me.username})")
    logger.info("[Userbot] Бот активен и ждёт сообщений")
    await client.run_until_disconnected()
