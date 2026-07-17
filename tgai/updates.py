"""Update check against the github releases of this repo (or a fork)."""

import logging
import re
import time

import aiohttp

from tgai import __version__

logger = logging.getLogger(__name__)

DEFAULT_REPO = "canary443/tg-ai-bot"
CACHE_TTL = 6 * 3600.0


def parse_version(value: str) -> tuple[int, int, int] | None:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (value or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer(candidate: str, current: str) -> bool:
    a = parse_version(candidate)
    b = parse_version(current)
    if a is None or b is None:
        return False
    return a > b


class UpdateChecker:
    """Latest-release lookup with a small in-memory cache."""

    def __init__(self, repo: str = DEFAULT_REPO):
        self.repo = repo
        self._cache: dict | None = None
        self._checked_at = 0.0

    async def check(self, session: aiohttp.ClientSession, force: bool = False) -> dict:
        now = time.monotonic()
        if not force and self._cache is not None and now - self._checked_at < CACHE_TTL:
            return self._cache

        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "tgai"}
        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 404:
                    # no releases yet, not an error worth surfacing
                    data = {}
                elif resp.status != 200:
                    raise RuntimeError(f"github returned {resp.status}")
                else:
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("[Updates] check failed: %s", e)
            return {
                "current": __version__,
                "latest": None,
                "update_available": False,
                "url": "",
                "error": str(e),
            }

        tag = (data.get("tag_name") or "").lstrip("v")
        result = {
            "current": __version__,
            "latest": tag or None,
            "update_available": is_newer(tag, __version__),
            "url": data.get("html_url", ""),
        }
        self._cache = result
        self._checked_at = now
        return result
