"""Telethon userbot. Decides whether to answer a message and sends the AI reply.

Triggers (all read live from config): DMs, group @mentions, replies to the bot.
A rate-limited reply is skipped silently. Handlers attach only after auth.
"""

import asyncio
import logging
import re
import time
from collections import OrderedDict

from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityMention,
    MessageEntityMentionName,
    User,
)

from tgai.ai_service import AIError, AIService, RateLimited
from tgai.config import ConfigStore
from tgai.personas import Identity
from tgai.ratelimit import ActivityFeed

logger = logging.getLogger(__name__)

MAX_SENT_CACHE = 500


class BotRunner:
    """Owns the message handlers and their runtime state."""

    def __init__(self, cfg: ConfigStore, ai: AIService, feed: ActivityFeed, identity: Identity):
        self.cfg = cfg
        self.ai = ai
        self.feed = feed
        self.identity = identity
        self.client: TelegramClient | None = None
        self._attached = False
        self.sent_messages: OrderedDict[int, bool] = OrderedDict()
        self._last_response_time: dict[int, float] = {}

    def attach(self, client: TelegramClient) -> None:
        if self._attached:
            return
        self.client = client
        client.add_event_handler(self.handle_message, events.NewMessage(incoming=True))
        client.add_event_handler(self.track_own_messages, events.NewMessage(outgoing=True))
        self._attached = True
        logger.info("[Bot] handlers attached")

    def detach(self) -> None:
        if not self._attached or self.client is None:
            return
        self.client.remove_event_handler(self.handle_message)
        self.client.remove_event_handler(self.track_own_messages)
        self._attached = False
        logger.info("[Bot] handlers detached")

    @property
    def attached(self) -> bool:
        return self._attached

    # helpers

    def _track_sent(self, msg_id: int) -> None:
        self.sent_messages[msg_id] = True
        while len(self.sent_messages) > MAX_SENT_CACHE:
            self.sent_messages.popitem(last=False)

    def is_reply_to_bot(self, message) -> bool:
        if not message.reply_to:
            return False
        return message.reply_to.reply_to_msg_id in self.sent_messages

    def _on_cooldown(self, chat_id: int) -> bool:
        cooldown = self.cfg.get("behavior.per_chat_cooldown", 3.0) or 0.0
        last = self._last_response_time.get(chat_id, 0.0)
        return (time.monotonic() - last) < cooldown

    def _mark_replied(self, chat_id: int) -> None:
        self._last_response_time[chat_id] = time.monotonic()

    async def is_mentioned(self, message) -> bool:
        my_username = self.identity.username.lower()
        my_id = self.identity.user_id
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

    async def _seed_context(self, event, chat_id: int) -> None:
        """Backfill recent messages for a whitelisted chat that has no local history."""
        if self.ai.has_history(chat_id):
            return
        limit = self.cfg.get("behavior.history_limit", 200) or 200
        seed: list[dict] = []
        try:
            msgs = await event.client.get_messages(chat_id, limit=limit)
        except Exception as e:
            logger.warning("[Bot] could not load history for %s: %s", chat_id, e)
            return
        for m in reversed(msgs):  # oldest first
            if not m.text or m.id == event.message.id:
                continue
            seed.append({"role": "assistant" if m.out else "user", "content": m.text})
        if seed:
            self.ai.seed_history(chat_id, seed)
            self.feed.push("info", f"seeded context for chat {chat_id} ({len(seed)} msgs)")

    async def _should_respond(self, event, message, chat_id: int, is_group: bool) -> bool:
        b = self.cfg.get("behavior", {})
        whitelisted = chat_id in self.cfg.get("active_chats", [])

        if whitelisted:  # whitelisted chats always answer
            return True

        if is_group:
            if not b.get("reply_in_groups", True):
                return False
            mentioned = await self.is_mentioned(message)
            replied = self.is_reply_to_bot(message)
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

    # handlers

    async def handle_message(self, event):
        message = event.message
        chat_id = event.chat_id

        if message.out or not message.text:
            return
        if not self.cfg.is_chat_allowed(chat_id):
            return
        if self._on_cooldown(chat_id):
            return

        is_private = isinstance(event.chat, User) or event.is_private
        is_group = not is_private

        if not await self._should_respond(event, message, chat_id, is_group):
            return

        if chat_id in self.cfg.get("active_chats", []):
            await self._seed_context(event, chat_id)

        my_username = self.identity.username
        user_text = message.text
        if my_username:
            user_text = re.sub(
                rf"@{re.escape(my_username)}", "", user_text, flags=re.IGNORECASE,
            ).strip()
        if not user_text:
            user_text = "hi"

        sender = await event.get_sender()
        sender_name = ""
        if sender:
            sender_name = getattr(sender, "first_name", None) or getattr(sender, "title", "")
        extra_context = f"the person writing to you: {sender_name}" if sender_name else ""

        self.feed.push("incoming", f"{sender_name or chat_id}: {user_text[:50]}")

        delay = self.cfg.get("behavior.response_delay", 1.5)
        if delay and delay > 0:
            await asyncio.sleep(delay)

        try:
            async with event.client.action(chat_id, "typing"):
                response = await self.ai.ask(chat_id, user_text, extra_context)
        except RateLimited:
            self.feed.push("wait", f"provider limit, skipping reply in {chat_id}")
            logger.info("[Bot] rate limited, skipping %s", chat_id)
            return
        except AIError as e:
            self.feed.push("error", f"AI error: {e}")
            logger.warning("[Bot] AI error in %s: %s", chat_id, e)
            return

        self._mark_replied(chat_id)
        try:
            if is_group:
                sent = await event.reply(response)
            else:
                sent = await event.client.send_message(chat_id, response)
            self._track_sent(sent.id)
            self.feed.push("reply", f"-> {chat_id}: {response[:50]}")
            logger.info("[Bot] replied in %s", chat_id)
        except Exception as e:
            self.feed.push("error", f"send failed in {chat_id}: {e}")
            logger.error("[Bot] could not send to %s: %s", chat_id, e)

    async def track_own_messages(self, event):
        if event.message.id:
            self._track_sent(event.message.id)
