# backend/storage/task_store.py
"""Persistent storage for TaskGraphs using JSON files.

Simplified implementation that writes a `tasks.json` file to disk in the
``data`` directory.  The module exposes a small API:

- :func:`get_task_store` – Returns a cached :class:`TaskStore` singleton.
- :class:`TaskStore` – In‑memory cache backed by a JSON file.

The file format is a mapping from task ID to a dictionary containing all
metadata needed by the UI.  The ``TaskGraph`` itself is not fully
serialized – the planner stores enough information to recreate the graph
for retry.  For production a proper schema would be required, but this
implementation keeps the logic small and deterministic.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.agents.task_graph import TaskGraph, TaskStatus

__all__ = ["TaskStore", "get_task_store"]

# Path constants – all persisted data lives under ``PROJECT_ROOT/data``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TASKS_FILE = DATA_DIR / "tasks.json"

# Ensure the data directory exists.
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Simple in‑memory cache keeping the mapping from task ID to a dict.
_cache: dict[str, dict] | None = None
_lock = asyncio.Lock()


class TaskStore:
    """Thread‑safe JSON‑backed storage for TaskGraph descriptors.

    The store operates on the following task dict format:

    .. code-block:: json

        {
            "id": "uuid",
            "session_id": "default",
            "root_goal": "...",
            "status": "pending",
            "created_at": "2024‑05‑10T12:34:56",
            "started_at": null,
            "completed_at": null,
            "result_json": null
        }

    The :class:`TaskGraph` serialization is intentionally lightweight –
    only the tasks dict, not the full object.  Updating the status or
    result is done by modifying the stored mapping; the in‑memory cache
    is written back to disk after each mutation.
    """

    def __init__(self, file_path: Path = TASKS_FILE):
        self.file_path = file_path
        self.store: dict[str, dict] = {}

    async def initialize(self) -> None:
        """Ensure the store file exists and load it into memory.

        The operation is idempotent; concurrent initialisation is safe
        thanks to :data:`_lock`.
        """
        async with _lock:
            if not self.file_path.exists():
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                await self._write([])
            await self._read()

    async def _read(self) -> None:
        content = self.file_path.read_text(encoding="utf-8")
        data = json.loads(content) if content else []
        self.store = {t["id"]: t for t in data}

    async def _write(self, tasks: list[dict]) -> None:
        self.file_path.write_text(json.dumps(tasks, indent=2), encoding="utf-8")

    async def _persist(self) -> None:
        async with _lock:
            await self._write(list(self.store.values()))

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    async def save(self, graph: TaskGraph, session_id: str) -> str:
        """Persist a new graph as a pending task and return its ID.

        ``graph``: The :class:`TaskGraph` instance to be persisted.
        ``session_id``: Identifier for the caller session.
        """
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        entry = {
            "id": task_id,
            "session_id": session_id,
            "root_goal": graph.root_goal,
            "status": TaskStatus.PENDING.value,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "result_json": None,
            "graph_json": json.dumps(graph.to_dict()),
        }
        self.store[task_id] = entry
        await self._persist()
        return task_id

    async def load(self, task_id: str) -> TaskGraph | None:
        entry = self.store.get(task_id)
        if not entry:
            return None
        if entry.get("graph_json"):
            data = json.loads(entry["graph_json"])
            return TaskGraph.from_dict(data)
        return None

    async def list_all(self) -> list[dict]:
        # Return a shallow copy to avoid accidental mutation.
        return [dict(v) for v in self.store.values()]

    async def get(self, task_id: str) -> dict | None:
        entry = self.store.get(task_id)
        return dict(entry) if entry else None

    async def delete(self, task_id: str) -> bool:
        if task_id in self.store:
            del self.store[task_id]
            await self._persist()
            return True
        return False

    async def update_status(
        self, task_id: str, status: str, *, result: dict | None = None
    ) -> None:
        entry = self.store.get(task_id)
        if not entry:
            return
        entry["status"] = status
        now = datetime.utcnow().isoformat()
        if status == TaskStatus.RUNNING.value:
            entry["started_at"] = now
        elif status in (TaskStatus.COMPLETE.value, TaskStatus.FAILED.value):
            entry["completed_at"] = now
        if result is not None:
            entry["result_json"] = json.dumps(result)
        await self._persist()


# ----------------------------------------------------------------------
# Global singleton accessor
# ----------------------------------------------------------------------

def get_task_store() -> TaskStore:
    global _cache
    if _cache is None:
        _cache = TaskStore()
    return _cache