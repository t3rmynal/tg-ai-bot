"""Proactive rate limiting + a small activity feed for the dashboard.

The limiter spaces out provider calls so the combined traffic stays under the
provider's requests-per-minute cap. That is the "anti rate limit" idea: rather
than hammering the API and eating 429s, we hold each call until enough time has
passed since the previous one. ai_service still handles 429s reactively on top of
this, but in practice the limiter keeps us under the cap.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field


class AsyncRateLimiter:
    """Spaces calls to at most `rpm` per minute. Shared across all chats."""

    def __init__(self, rpm: int):
        self._lock = asyncio.Lock()
        self._next_at = 0.0
        self.set_rpm(rpm)

    def set_rpm(self, rpm: int) -> None:
        self.rpm = max(1, int(rpm))
        self.interval = 60.0 / self.rpm

    async def acquire(self) -> float:
        """Block until the next call is allowed. Returns how long we waited."""
        async with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            else:
                wait = 0.0
            self._next_at = max(now, self._next_at) + self.interval
            return wait


@dataclass
class Event:
    kind: str  # incoming | reply | wait | error | info
    text: str
    ts: float = field(default_factory=time.time)


# Recent events, newest last. The live monitor renders these.
activity: deque[Event] = deque(maxlen=200)


def push(kind: str, text: str) -> None:
    activity.append(Event(kind, text))


def recent(n: int = 12) -> list[Event]:
    return list(activity)[-n:]
