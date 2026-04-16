from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from typing import Any

class EventBus:
    """
    Per-job event bus with bounded replay buffer.
    - publish(job_id, event)    -> buffers + fans out to all live subscribers
    - subscribe(job_id) -> queue live events (does NOT replay)
    - replay(job_id) -> returns buffered events so caller can send them first
    """
    def __init__(self, buffer_size: int = 200):
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=buffer_size))
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        self._buffers[job_id].append(event)
        for q in list(self._subscribers[job_id]):
            await q.put(event)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        if q in self._subscribers[job_id]:
            self._subscribers[job_id].remove(q)

    def replay(self, job_id: str) -> list[dict[str, Any]]:
        return list(self._buffers[job_id])
