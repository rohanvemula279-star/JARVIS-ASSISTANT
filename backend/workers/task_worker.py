# backend/workers/task_worker.py
"""Background task worker for the JARVIS assistant.

The worker keeps a simple in‑memory registry of tasks scheduled through
:class:`backend.storage.task_store.TaskStore`.  It supports exactly
what the API currently needs: submitting a new graph, cancelling, and
retrying a failed task.  The implementation uses the :class:`AgentCoordinator`
to execute the graph asynchronously.

The worker is intentionally lightweight – full persistence via SQLite
and graceful shutdown handling are out of scope for the current demo
phase.  All methods are ``async`` for consistency with the API.

"""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.agents.coordinator import AgentCoordinator
from backend.storage.task_store import get_task_store, TaskStore
from backend.agents.task_graph import TaskGraph

__all__ = ["BackgroundTaskWorker", "get_worker"]

# Global singleton – instantiated at import time.
_worker_instance = None


class BackgroundTaskWorker:
    """Very small worker that keeps a reference to the *coordinator*.

    It interacts with the :class:`TaskStore` to persist task metadata and
    provides a simple API for the routers to submit, cancel or retry
    background jobs.
    """

    def __init__(self, coordinator: AgentCoordinator):
        self.coordinator = coordinator
        self.store: TaskStore = get_task_store()
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._running: bool = False

    async def start(self) -> None:
        """Called once at server startup. Initializes store and resumes pending tasks."""
        self._running = True
        await self.store.initialize()
        all_tasks = await self.store.list_all()
        pending = [t for t in all_tasks if t.get("status") in ("pending", "running")]
        for task_summary in pending:
            asyncio.create_task(self._run_task(task_summary["id"]))

    def stop(self) -> None:
        """Signal the worker to stop accepting new tasks."""
        self._running = False

    # ------------------------------------------------------------
    # Public API used by the FastAPI endpoints
    # ------------------------------------------------------------
    async def submit(self, graph: TaskGraph, session_id: str) -> str:
        """Register a graph and kickoff its execution.

        Returns the generated task ID.
        """
        task_id = await self.store.save(graph, session_id)
        # Schedule execution but do not await – sub‑tasks run in the
        # background.
        run_task = asyncio.create_task(self._run_task(task_id))
        self._active_tasks[task_id] = run_task
        return task_id

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task.

        This simply attempts to cancel the ``asyncio.Task`` if it is
        still pending.  The task entry in the store is left untouched –
        the caller may query the status later.
        """
        act = self._active_tasks.get(task_id)
        if act and not act.done():
            act.cancel()
            await act
            return True
        return False

    async def retry(self, task_id: str) -> bool:
        """Retry a previously failed task.

        The stored ``TaskGraph`` is re‑loaded, the status is reset to
        pending and a new execution is scheduled.
        """
        graph = await self.store.load(task_id)
        if not graph:
            return False
        # Reset status
        await self.store.update_status(task_id, status="pending")
        # Re‑submit
        run_task = asyncio.create_task(self._run_task(task_id))
        self._active_tasks[task_id] = run_task
        return True

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------
    async def _run_task(self, task_id: str) -> None:
        """Execute a stored graph using the coordinator.

        The coordinator emits :class:`StepEvent` objects – the worker does
        not forward those to the UI directly; the FastAPI endpoint can
        stream them to the client if desired via SSE.  For now the worker
        updates status in the store as the graph progresses.
        """
        graph = await self.store.load(task_id)
        if not graph:
            return

        try:
            async for event in self.coordinator.execute_plan(graph, task_id):
                # Update status on completion
                if event.type == "agent_complete":
                    # Mark the single task that just finished
                    await self.store.update_status(task_id, status="running")
                elif event.type == "answer":
                    await self.store.update_status(task_id, status="complete", result={"answer": event.content})
        except asyncio.CancelledError:
            await self.store.update_status(task_id, status="failed", result={"error": "Cancelled"})
        except Exception as e:
            await self.store.update_status(task_id, status="failed", result={"error": str(e)})
        finally:
            self._active_tasks.pop(task_id, None)

    async def cleanup(self) -> None:
        """Cancel any running tasks – used when server shuts down."""
        for task in list(self._active_tasks.values()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
        self._active_tasks.clear()


# ----------------------------------------------------------------------
# Singleton accessor
# ----------------------------------------------------------------------

def get_worker() -> BackgroundTaskWorker:
    global _worker_instance
    if _worker_instance is None:
        raise RuntimeError("BackgroundTaskWorker not initialized – call Worker.once in lifespan")
    return _worker_instance

# The actual instantiation will happen in the FastAPI lifespan.