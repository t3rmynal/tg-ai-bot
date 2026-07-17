"""Proactive rate limiter plus the activity feed behind the live dashboard.

The limiter holds each call until enough time has passed to stay under the
provider RPM. The AI client handles 429s reactively on top of this.
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
    id: int = 0
    ts: float = field(default_factory=time.time)


class ActivityFeed:
    """Recent events plus fan-out queues for sse subscribers."""

    def __init__(self, maxlen: int = 200):
        self._events: deque[Event] = deque(maxlen=maxlen)
        self._subscribers: list[asyncio.Queue] = []
        self._next_id = 1

    def push(self, kind: str, text: str) -> Event:
        event = Event(kind, text, id=self._next_id)
        self._next_id += 1
        self._events.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow subscriber, drop the event for it
        return event

    def recent(self, n: int = 50) -> list[Event]:
        return list(self._events)[-n:]

    def since(self, last_id: int) -> list[Event]:
        return [e for e in self._events if e.id > last_id]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)
