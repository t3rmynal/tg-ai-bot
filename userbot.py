"""Telethon userbot. Decides whether to answer a message and sends the AI reply.

Triggers (all read live from config): DMs, group @mentions, replies to the bot.
A rate-limited reply is skipped silently.
"""

import asyncio
import logging
import re
from collections import OrderedDict

from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityMention,
    MessageEntityMentionName,
    User,
)

import ai_service
import config
from ai_service import AIError, RateLimited, ask_ai
from ratelimit import push as push_event

logger = logging.getLogger(__name__)

client: TelegramClient | None = None

MAX_SENT_CACHE = 500
bot_sent_messages: "OrderedDict[int, bool]" = OrderedDict()
_last_response_time: dict[int, float] = {}
_me_cache: tuple[str, int] | None = None


def create_client() -> TelegramClient:
    """Build the Telethon client from config and wire up the handlers."""
    global client
    api_id = int(config.get("telegram.api_id"))
    api_hash = config.get("telegram.api_hash")
    client = TelegramClient("userbot", api_id, api_hash)
    client.add_event_handler(handle_message, events.NewMessage(incoming=True))
    client.add_event_handler(track_own_messages, events.NewMessage(outgoing=True))
    return client


def _track_sent(msg_id: int) -> None:
    bot_sent_messages[msg_id] = True
    while len(bot_sent_messages) > MAX_SENT_CACHE:
        bot_sent_messages.popitem(last=False)


def is_reply_to_bot(message) -> bool:
    if not message.reply_to:
        return False
    return message.reply_to.reply_to_msg_id in bot_sent_messages


def _on_cooldown(chat_id: int) -> bool:
    import time

    cooldown = config.get("behavior.per_chat_cooldown", 3.0) or 0.0
    last = _last_response_time.get(chat_id, 0.0)
    return (time.monotonic() - last) < cooldown


def _mark_replied(chat_id: int) -> None:
    import time

    _last_response_time[chat_id] = time.monotonic()


async def _get_me() -> tuple[str, int]:
    global _me_cache
    if _me_cache is None:
        me = await client.get_me()
        _me_cache = ((me.username or "").lower(), me.id)
    return _me_cache


async def is_mentioned(message, my_username: str, my_id: int) -> bool:
    if not message.text:
        return False
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
            if message.text[start:end].lower().lstrip("@") == my_username:
                return True
    return False


async def _seed_context(event, chat_id: int) -> None:
    """Backfill recent messages for a whitelisted chat that has no local history."""
    if ai_service.has_history(chat_id):
        return
    limit = config.get("behavior.history_limit", 200) or 200
    seed: list[dict] = []
    try:
        msgs = await event.client.get_messages(chat_id, limit=limit)
    except Exception as e:
        logger.warning("[Userbot] could not load history for %s: %s", chat_id, e)
        return
    for m in reversed(msgs):  # oldest first
        if not m.text or m.id == event.message.id:
            continue
        seed.append({"role": "assistant" if m.out else "user", "content": m.text})
    if seed:
        ai_service.seed_history(chat_id, seed)
        push_event("info", f"seeded context for chat {chat_id} ({len(seed)} msgs)")


async def _should_respond(event, message, chat_id: int, is_group: bool) -> bool:
    b = config.get("behavior", {})
    whitelisted = chat_id in config.get("active_chats", [])

    if whitelisted:  # whitelisted chats always answer
        return True

    if is_group:
        if not b.get("reply_in_groups", True):
            return False
        my_username, my_id = await _get_me()
        mentioned = await is_mentioned(message, my_username, my_id)
        replied = is_reply_to_bot(message)
        return (mentioned and b.get("reply_to_mentions", True)) or (
            replied and b.get("reply_to_replies", True)
        )

    # direct message
    if not b.get("reply_in_dm", True):
        return False
    if b.get("dm_new_dialogues_only", False):
        try:
            msgs = await event.client.get_messages(chat_id, limit=2)
            if len(msgs) > 1:  # history existed before this message
                return False
        except Exception:
            pass
    return True


async def handle_message(event):
    message = event.message
    chat_id = event.chat_id

    if message.out or not message.text:
        return
    if not config.is_chat_allowed(chat_id):
        return
    if _on_cooldown(chat_id):
        return

    is_private = isinstance(event.chat, User) or event.is_private
    is_group = not is_private

    if not await _should_respond(event, message, chat_id, is_group):
        return

    if chat_id in config.get("active_chats", []):
        await _seed_context(event, chat_id)

    my_username, _ = await _get_me()
    user_text = message.text
    if my_username:
        user_text = re.sub(rf"@{re.escape(my_username)}", "", user_text, flags=re.IGNORECASE).strip()
    if not user_text:
        user_text = "hi"

    sender = await event.get_sender()
    sender_name = ""
    if sender:
        sender_name = getattr(sender, "first_name", None) or getattr(sender, "title", "")
    extra_context = f"the person writing to you: {sender_name}" if sender_name else ""

    push_event("incoming", f"{sender_name or chat_id}: {user_text[:50]}")

    delay = config.get("behavior.response_delay", 1.5)
    if delay and delay > 0:
        await asyncio.sleep(delay)

    try:
        async with event.client.action(chat_id, "typing"):
            response = await ask_ai(chat_id, user_text, extra_context)
    except RateLimited:
        push_event("wait", f"provider limit, skipping reply in {chat_id}")
        logger.info("[Userbot] rate limited, skipping %s", chat_id)
        return
    except AIError as e:
        push_event("error", f"AI error: {e}")
        logger.warning("[Userbot] AI error in %s: %s", chat_id, e)
        return

    _mark_replied(chat_id)
    try:
        if is_group:
            sent = await event.reply(response)
        else:
            sent = await event.client.send_message(chat_id, response)
        _track_sent(sent.id)
        push_event("reply", f"-> {chat_id}: {response[:50]}")
        logger.info("[Userbot] replied in %s", chat_id)
    except Exception as e:
        push_event("error", f"send failed in {chat_id}: {e}")
        logger.error("[Userbot] could not send to %s: %s", chat_id, e)


async def track_own_messages(event):
    if event.message.id:
        _track_sent(event.message.id)
