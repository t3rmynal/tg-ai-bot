"""QR login state machine, driven by the API instead of a terminal.

States: no_credentials -> unauthorized -> qr_pending -> (password_needed) -> authorized.
The frontend polls status, renders the tg:// url as a qr code, and submits the
2fa password when asked.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from tgai.config import ConfigStore
from tgai.personas import Identity
from tgai.ratelimit import ActivityFeed

logger = logging.getLogger(__name__)

SESSION_NAME = "userbot"  # keep this so existing userbot.session files work
QR_TIMEOUT = 30.0


class AuthState(str, Enum):
    NO_CREDENTIALS = "no_credentials"
    CONNECTING = "connecting"
    UNAUTHORIZED = "unauthorized"
    QR_PENDING = "qr_pending"
    PASSWORD_NEEDED = "password_needed"
    AUTHORIZED = "authorized"


class AuthManager:
    """Owns the Telethon client and the login flow."""

    def __init__(self, cfg: ConfigStore, feed: ActivityFeed, identity: Identity, proxy=None):
        self.cfg = cfg
        self.feed = feed
        self.identity = identity
        self.proxy = proxy
        self.client: TelegramClient | None = None
        self.state = AuthState.NO_CREDENTIALS
        self.on_authorized = None  # set by app wiring
        self.on_logout = None
        self._qr_login = None
        self._qr_expires_at: datetime | None = None
        self._wait_task: asyncio.Task | None = None
        self._user: dict | None = None

    # status

    def status(self) -> dict:
        qr = None
        if self.state == AuthState.QR_PENDING and self._qr_login is not None:
            qr = {
                "url": self._qr_login.url,
                "expires_at": self._qr_expires_at.isoformat() if self._qr_expires_at else None,
            }
        return {"state": self.state.value, "user": self._user, "qr": qr}

    @property
    def authorized(self) -> bool:
        return self.state == AuthState.AUTHORIZED

    # lifecycle

    async def startup(self) -> None:
        """Connect with saved credentials if present. Never prompts."""
        api_id = self.cfg.get("telegram.api_id")
        api_hash = self.cfg.get("telegram.api_hash")
        if not (api_id and api_hash):
            self.state = AuthState.NO_CREDENTIALS
            return
        await self._connect(int(api_id), api_hash)

    async def _connect(self, api_id: int, api_hash: str) -> None:
        self.state = AuthState.CONNECTING
        tg_proxy = self.proxy.telegram_proxy() if self.proxy else None
        if tg_proxy:
            self.feed.push("info", "telegram connecting through proxy")
        self.client = TelegramClient(SESSION_NAME, api_id, api_hash, proxy=tg_proxy)
        try:
            await self.client.connect()
        except Exception as e:
            logger.error("[Auth] could not connect: %s", e)
            self.state = AuthState.UNAUTHORIZED
            return
        if await self.client.is_user_authorized():
            await self._finish_login()
        else:
            self.state = AuthState.UNAUTHORIZED

    async def set_credentials(self, api_id: int, api_hash: str) -> None:
        if self.state == AuthState.AUTHORIZED:
            raise RuntimeError("already signed in, log out first")
        await self._cancel_qr()
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self.cfg.set("telegram.api_id", api_id)
        self.cfg.set("telegram.api_hash", api_hash.strip())
        await self._connect(api_id, api_hash.strip())

    # qr flow

    async def begin_qr(self) -> dict:
        if self.client is None or self.state == AuthState.NO_CREDENTIALS:
            raise RuntimeError("telegram credentials not set")
        if self.state == AuthState.AUTHORIZED:
            raise RuntimeError("already signed in")
        await self._cancel_qr()
        self._qr_login = await self.client.qr_login()
        self._qr_expires_at = datetime.now(timezone.utc) + timedelta(seconds=QR_TIMEOUT)
        self.state = AuthState.QR_PENDING
        self._wait_task = asyncio.create_task(self._await_scan(self._qr_login))
        return {"url": self._qr_login.url, "expires_at": self._qr_expires_at.isoformat()}

    async def _await_scan(self, qr_login) -> None:
        try:
            await qr_login.wait(timeout=QR_TIMEOUT)
        except asyncio.TimeoutError:
            if self.state == AuthState.QR_PENDING:
                self.state = AuthState.UNAUTHORIZED  # frontend re-posts /auth/qr
            return
        except SessionPasswordNeededError:
            self.state = AuthState.PASSWORD_NEEDED
            self.feed.push("info", "2fa password needed")
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[Auth] qr wait failed: %s", e)
            if self.state == AuthState.QR_PENDING:
                self.state = AuthState.UNAUTHORIZED
            return
        await self._finish_login()

    async def submit_password(self, password: str) -> None:
        if self.state != AuthState.PASSWORD_NEEDED:
            raise RuntimeError("no password prompt pending")
        try:
            await self.client.sign_in(password=password)
        except Exception as e:
            raise ValueError(f"wrong password: {e}") from e
        await self._finish_login()

    async def logout(self) -> None:
        await self._cancel_qr()
        if self.on_logout:
            self.on_logout()
        if self.client is not None:
            try:
                await self.client.log_out()
            except Exception as e:
                logger.warning("[Auth] logout: %s", e)
        self._user = None
        self.identity.clear()
        self.state = AuthState.UNAUTHORIZED
        self.feed.push("info", "signed out")

    async def _finish_login(self) -> None:
        me = await self.client.get_me()
        self.identity.set(me.username or "", me.first_name or "", me.id)
        self._user = {
            "id": me.id,
            "username": me.username or "",
            "first_name": me.first_name or "",
        }
        self._qr_login = None
        self._qr_expires_at = None
        self.state = AuthState.AUTHORIZED
        if self.on_authorized:
            self.on_authorized()
        self.feed.push("info", f"signed in as {me.first_name or me.username or me.id}")
        logger.info("[Auth] signed in as %s", me.id)

    async def _cancel_qr(self) -> None:
        if self._wait_task and not self._wait_task.done():
            self._wait_task.cancel()
            try:
                await self._wait_task
            except (asyncio.CancelledError, Exception):
                pass
        self._wait_task = None
        self._qr_login = None
        self._qr_expires_at = None

    async def shutdown(self) -> None:
        await self._cancel_qr()
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
