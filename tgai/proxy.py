"""Optional outbound proxy: manual pool or mullvad exit nodes, with rotation.

Every AI provider call can go through a proxy, and the pool can rotate. The
telegram connection uses one fixed proxy chosen at connect time. Mullvad exits
are the per-server socks5 relays, reachable while the mullvad tunnel is up.
"""

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

MULLVAD_RELAYS_URL = "https://api.mullvad.net/www/relays/all/"
# echo endpoint that reports the exit ip and whether it is a mullvad server
MULLVAD_CHECK_URL = "https://ipv4.am.i.mullvad.net/json"

SCHEMES = {"socks5", "socks5h", "socks4", "http", "https"}


@dataclass(frozen=True)
class Proxy:
    scheme: str
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def url(self) -> str:
        auth = ""
        if self.username:
            auth = self.username
            if self.password:
                auth += f":{self.password}"
            auth += "@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

    def masked(self) -> str:
        auth = f"{self.username}:***@" if self.username else ""
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

    def telethon(self) -> dict:
        """python-socks style dict telethon understands."""
        kind = "socks5" if self.scheme.startswith("socks5") else self.scheme
        proxy = {"proxy_type": kind, "addr": self.host, "port": self.port, "rdns": True}
        if self.username:
            proxy["username"] = self.username
            proxy["password"] = self.password
        return proxy


def parse_proxy(value: str) -> Proxy | None:
    """Parse scheme://user:pass@host:port. Bare host:port is treated as socks5."""
    value = (value or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = "socks5://" + value
    try:
        p = urlparse(value)
    except ValueError:
        return None
    scheme = (p.scheme or "").lower()
    if scheme not in SCHEMES or not p.hostname or not p.port:
        return None
    return Proxy(
        scheme=scheme,
        host=p.hostname,
        port=p.port,
        username=p.username or "",
        password=p.password or "",
    )


def _parse_pool(urls: list[str]) -> list[Proxy]:
    out: list[Proxy] = []
    seen: set[str] = set()
    for u in urls:
        proxy = parse_proxy(u)
        if proxy and proxy.url not in seen:
            seen.add(proxy.url)
            out.append(proxy)
    return out


class ProxyManager:
    """Derives the pool from config and hands out proxies with rotation."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._index = 0
        self._calls = 0
        self._last_key: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("proxy.enabled", False))

    def pool(self) -> list[Proxy]:
        mode = self.cfg.get("proxy.mode", "manual")
        if mode == "mullvad":
            return _parse_pool(self.cfg.get("proxy.mullvad.loaded", []))
        return _parse_pool(self.cfg.get("proxy.manual", []))

    def active(self) -> Proxy | None:
        if not self.enabled:
            return None
        pool = self.pool()
        if not pool:
            return None
        return pool[self._index % len(pool)]

    def rotate(self) -> Proxy | None:
        pool = self.pool()
        if not pool:
            return None
        self._index = (self._index + 1) % len(pool)
        return pool[self._index]

    def next_for_request(self) -> Proxy | None:
        """Pick the proxy for the next call, applying the rotation strategy."""
        if not self.enabled:
            return None
        pool = self.pool()
        if not pool:
            return None
        strategy = self.cfg.get("proxy.rotation", "off")
        self._calls += 1
        if strategy == "per_request":
            self._index = (self._index + 1) % len(pool)
        elif strategy == "per_n":
            every = max(1, int(self.cfg.get("proxy.rotate_every", 10) or 10))
            if self._calls % every == 0:
                self._index = (self._index + 1) % len(pool)
        return pool[self._index % len(pool)]

    def telegram_proxy(self) -> dict | None:
        """Fixed proxy for the telegram connection, if opted in."""
        if not self.enabled or not self.cfg.get("proxy.apply_to_telegram", False):
            return None
        active = self.active()
        return active.telethon() if active else None

    def took_new_proxy(self, proxy: Proxy | None) -> bool:
        """True the first time a given proxy becomes active, for logging."""
        key = proxy.url if proxy else None
        if key != self._last_key:
            self._last_key = key
            return True
        return False


def build_mullvad_urls(relays: list[dict], country: str = "") -> list[str]:
    """Turn the mullvad relay list into socks5 proxy urls for active exits."""
    country = (country or "").strip().lower()
    urls: list[str] = []
    for r in relays:
        if not r.get("active") or r.get("type") != "wireguard":
            continue
        socks_name = r.get("socks_name")
        if not socks_name:
            continue
        if country and r.get("country_code", "").lower() != country:
            continue
        port = r.get("socks_port") or 1080
        urls.append(f"socks5://{socks_name}:{port}")
    return sorted(set(urls))


async def fetch_mullvad_urls(session: aiohttp.ClientSession, country: str = "") -> list[str]:
    async with session.get(
        MULLVAD_RELAYS_URL, timeout=aiohttp.ClientTimeout(total=20),
    ) as resp:
        if resp.status != 200:
            raise RuntimeError(f"mullvad api returned {resp.status}")
        relays = await resp.json(content_type=None)
    if not isinstance(relays, list):
        raise RuntimeError("unexpected mullvad response")
    return build_mullvad_urls(relays, country)


async def test_proxy(proxy: Proxy) -> dict:
    """Probe a proxy and report the exit ip and country."""
    from aiohttp_socks import ProxyConnector

    connector = ProxyConnector.from_url(proxy.url)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                MULLVAD_CHECK_URL, timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"check endpoint returned {resp.status}")
                data = await resp.json(content_type=None)
        return {
            "ok": True,
            "ip": data.get("ip", ""),
            "country": data.get("country", ""),
            "mullvad_exit": bool(data.get("mullvad_exit_ip", False)),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
