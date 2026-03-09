"""
Userbot - сидит на твоём аккаунте и отвечает на сообщения
"""

import asyncio
import re
import os
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
PHONE = os.getenv("TG_PHONE")

from ai_service import ask_ai
import storage

client = TelegramClient("userbot", API_ID, API_HASH)

bot_sent_messages: set[int] = set()
MAX_SENT_CACHE = 500


def is_reply_to_bot(message) -> bool:
    """Проверяет что сообщение - реплай на сообщение бота"""
    if not message.reply_to:
        return False
    reply_id = message.reply_to.reply_to_msg_id
    return reply_id in bot_sent_messages


async def get_my_username() -> tuple[str, int]:
    """Возвращает username и id текущего аккаунта"""
    me = await client.get_me()
    username = me.username or ""
    return username.lower(), me.id


async def is_mentioned(message, my_username: str, my_id: int) -> bool:
    """Проверяет что аккаунт упомянут в сообщении"""
    if not message.text:
        return False
    
    text = message.text.lower()
    
    if my_username and f"@{my_username}" in text:
        return True
    
    if message.entities:
        for entity in message.entities:
            entity_type = type(entity).__name__
            if "MentionName" in entity_type:
                if hasattr(entity, "user_id") and entity.user_id == my_id:
                    return True
            elif "Mention" in entity_type:
                start = entity.offset
                end = entity.offset + entity.length
                mention_text = message.text[start:end].lower().lstrip("@")
                if mention_text == my_username:
                    return True
    
    return False


@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    """Обработка входящих сообщений"""
    
    message = event.message
    chat_id = event.chat_id
    
    if message.out:
        return

    if not message.text:
        return
    
    if not storage.is_chat_allowed(chat_id):
        return
    
    my_username, my_id = await get_my_username()
    
    is_private = isinstance(event.chat, User) or event.is_private
    is_group = not is_private
    
    should_respond = False
    
    if is_private:
        if storage.get("reply_in_dm"):
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
            rf"@{re.escape(my_username)}", 
            "", 
            user_text, 
            flags=re.IGNORECASE
        ).strip()
    
    if not user_text:
        user_text = "привет"

    sender = await event.get_sender()
    sender_name = ""
    if sender:
        if hasattr(sender, "first_name") and sender.first_name:
            sender_name = sender.first_name
        elif hasattr(sender, "title"):
            sender_name = sender.title
    
    extra_context = f"тебя написал(а): {sender_name}" if sender_name else ""

    delay = storage.get("response_delay")
    if delay > 0:
        await asyncio.sleep(delay)

    async with client.action(chat_id, "typing"):
        bot_name = storage.get("bot_name")
        response = await ask_ai(
            chat_id=chat_id,
            user_message=user_text,
            bot_name=bot_name,
            extra_context=extra_context
        )
    
    if is_group:
        sent = await event.reply(response)
    else:
        sent = await client.send_message(chat_id, response)
    
    bot_sent_messages.add(sent.id)
    if len(bot_sent_messages) > MAX_SENT_CACHE:
        oldest = list(bot_sent_messages)[:100]
        for msg_id in oldest:
            bot_sent_messages.discard(msg_id)
    
    print(f"[Userbot] Ответил в {chat_id}: {response[:50]}...")


@client.on(events.NewMessage(outgoing=True))
async def track_own_messages(event):
    """Отслеживаем свои исходящие сообщения"""
    if event.message.id:
        bot_sent_messages.add(event.message.id)


async def start_userbot():
    print("[Userbot] Запуск...")
    await client.start(phone=PHONE)
    me = await client.get_me()
    print(f"[Userbot] Авторизован как: {me.first_name} (@{me.username})")
    print("[Userbot] Бот активен и ждёт сообщений")
    await client.run_until_disconnected()