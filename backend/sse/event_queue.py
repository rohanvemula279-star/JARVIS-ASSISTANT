# backend/sse/event_queue.py
"""Simple in‑memory event queue for background tasks.

The :class:`SSEEventQueue` implements a per‑session ring buffer that
stores the latest 100 :class:`backend.agents.StepEvent` instances.
Consumers can stream events from a specified index.  The API is used by
the `/api/v1/tasks/{session_id}/events` endpoint.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any, Dict

from backend.agents import StepEvent

__all__ = ["SSEEventQueue", "get_event_queue"]

# Global singleton – created when the module is imported.
_event_queue: SSEEventQueue | None = None


class SSEEventQueue:
    """Per‑session ring buffer of StepEvents.

    The queue uses :class:`collections.deque` with a maxlen of 100 –
    older events are automatically discarded as new ones arrive.
    """

    def __init__(self, maxlen: int = 100):
        self._queues: defaultdict[str, deque[StepEvent]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )
        self._waiters: dict[str, asyncio.Event] = {}

    async def put(self, session_id: str, event: StepEvent) -> None:
        self._queues[session_id].append(event)
        if session_id in self._waiters:
            self._waiters[session_id].set()

    async def stream(self, session_id: str, since_index: int = 0):
        """Yield events from ``since_index`` onward.

        This async generator yields existing items from the internal
        deque and then waits for new events using an ``asyncio.Event``.
        """
        queue = self._queues[session_id]
        idx = since_index
        while True:
            while idx < len(queue):
                yield queue[idx]
                idx += 1
            # Wait for the next event
            event = asyncio.Event()
            self._waiters[session_id] = event
            await event.wait()
            del self._waiters[session_id]


# ----------------------------------------------------------------------
# Singleton accessor
# ----------------------------------------------------------------------

def get_event_queue() -> SSEEventQueue:
    global _event_queue
    if _event_queue is None:
        _event_queue = SSEEventQueue()
    return _event_queue