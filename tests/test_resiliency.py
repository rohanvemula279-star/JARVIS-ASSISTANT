import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_router_survives_quota_hit():
    """Router must return CONVERSATION fallback, not raise, on 429."""
    from backend.agents.router import IntentRouter

    router = IntentRouter()

    call_count = 0

    async def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")

    with patch.object(
        router.client.aio.models, "generate_content", side_effect=mock_generate
    ):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await router.classify("open chrome")

    # Should not raise — should return fallback after exhaustion
    assert result is not None
    assert result.intent.value == "conversation"
    assert result.reasoning == "Quota exceeded fallback"
    print(f"  router_survives_quota_hit: PASS (called {call_count} times, got fallback)")


@pytest.mark.asyncio
async def test_retry_utility_retries_on_429():
    """with_retry must retry on 429 errors and succeed when the call recovers."""
    from backend.utils.retry import with_retry

    call_count = 0

    async def flaky_api():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")
        return "success"

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(flaky_api)

    assert result == "success"
    assert call_count == 3
    print(f"  retry_utility: PASS (retried {call_count} times, succeeded)")


@pytest.mark.asyncio
async def test_retry_utility_returns_fallback_on_exhaustion():
    """with_retry must return fallback after all retries are exhausted."""
    from backend.utils.retry import with_retry

    async def always_fails():
        raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(always_fails, fallback="FALLBACK_VALUE")

    assert result == "FALLBACK_VALUE"
    print("  retry_exhaustion_fallback: PASS")


@pytest.mark.asyncio
async def test_retry_utility_raises_non_retryable():
    """with_retry must NOT retry on non-retryable errors like ValueError."""
    from backend.utils.retry import with_retry

    async def bad_logic():
        raise ValueError("Invalid argument")

    with pytest.raises(ValueError, match="Invalid argument"):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await with_retry(bad_logic)
    print("  non_retryable_raises: PASS")


@pytest.mark.asyncio
async def test_chromadb_fallback_on_init_failure():
    """VectorMemory must gracefully fall back when ChromaDB init fails."""
    from backend.memory.chroma_store import VectorMemory

    # Force the init to fail by passing a bad persist dir that triggers an error
    # Since chromadb itself may have a SyntaxError on Python 3.14,
    # the module-level CHROMA_AVAILABLE is already False — test the fallback path
    mem = VectorMemory()

    # If CHROMA_AVAILABLE is False, _use_fallback should be True
    assert mem._use_fallback == True
    assert mem._initialized == False

    # Basic save/recall should still work via keyword fallback
    await mem.save({"user": "test query", "assistant": "test response", "intent": "conversation"})
    results = await mem.recall("test query")
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["content"] == "User: test query\nJARVIS: test response"
    print("  chromadb_fallback: PASS")


@pytest.mark.asyncio
async def test_working_memory_fallback():
    """WorkingMemory must work without Redis."""
    from backend.memory.working_memory import WorkingMemory

    mem = WorkingMemory()
    await mem.push_turn("test_session", "user", "hello")
    await mem.push_turn("test_session", "assistant", "hi there")
    history = await mem.get_history("test_session")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "hi there"
    print("  working_memory_fallback: PASS")


@pytest.mark.asyncio
async def test_task_graph_dependency_resolution():
    """TaskGraph must correctly resolve dependencies and unblock tasks."""
    from backend.agents.task_graph import Task, TaskGraph, TaskStatus

    g = TaskGraph(root_goal="test")
    t1 = g.add(Task(id="t1", goal="step one"))
    t2 = g.add(Task(id="t2", goal="step two", dependencies=["t1"]))
    t3 = g.add(Task(id="t3", goal="step three", dependencies=["t1", "t2"]))

    # Only t1 should be ready
    ready = g.get_ready_tasks()
    assert len(ready) == 1 and ready[0].id == "t1"

    # Complete t1 — t2 should unblock, t3 still blocked (needs t2)
    t1.status = TaskStatus.COMPLETE
    ready = g.get_ready_tasks()
    assert len(ready) == 1 and ready[0].id == "t2"

    # Complete t2 — t3 should unblock
    t2.status = TaskStatus.COMPLETE
    ready = g.get_ready_tasks()
    assert len(ready) == 1 and ready[0].id == "t3"

    # Complete t3 — graph should be complete
    t3.status = TaskStatus.COMPLETE
    assert g.is_complete()
    assert g.summary() == {"total": 3, "complete": 3, "failed": 0, "pending": 0}
    print("  task_graph_deps: PASS")


@pytest.mark.asyncio
async def test_code_executor_sandbox():
    """CodeExecutor must execute safe code and block dangerous imports."""
    from backend.sandbox.executor import CodeExecutor

    ex = CodeExecutor()

    # Safe code should work
    result = await ex.execute("result = sum(range(100))")
    assert result["success"] == True
    assert result["result"] == "4950"

    # Blocked import should fail
    result = await ex.execute("import subprocess")
    assert result["success"] == False
    assert "Blocked" in result["error"]

    # os.system should be blocked
    result = await ex.execute("import os; os.system('dir')")
    assert result["success"] == False
    assert "Blocked" in result["error"]
    print("  code_executor_sandbox: PASS")
