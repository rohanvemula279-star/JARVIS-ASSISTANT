"""Full integration smoke test — runs all 7 steps."""
import asyncio
import sys
import os
import traceback

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

results = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    icon = "[OK]" if passed else "[FAIL]"
    print(f"  {icon} {name}: {status}" + (f" -- {detail}" if detail else ""))


# ──── Step 1: Import chain ────
print("\n=== Step 1: Import Chain ===")
try:
    from backend.agents.coordinator import AgentCoordinator
    from backend.agents.sub_agent import SubAgent
    from backend.memory.shared_workspace import SharedWorkspace
    from backend.skills.registry import SkillRegistry
    from backend.skills.extractor import SkillExtractor
    from backend.utils.retry import with_retry
    record("All core imports", True)
except Exception as e:
    record("All core imports", False, str(e))


# ──── Step 2: TaskGraph dependency resolution ────
print("\n=== Step 2: TaskGraph ===")
try:
    from backend.agents.task_graph import Task, TaskGraph, TaskStatus

    g = TaskGraph(root_goal="research and summarize Python 3.13")
    g.add(Task(id="research", goal="Find Python 3.13 release notes", agent_profile="RESEARCHER"))
    g.add(Task(id="summarize", goal="Summarize findings", agent_profile="ANALYST", dependencies=["research"]))

    ready = g.get_ready_tasks()
    assert len(ready) == 1 and ready[0].id == "research", f"Expected research ready, got {[t.id for t in ready]}"
    record("Only research is ready initially", True)

    g.tasks["research"].status = TaskStatus.COMPLETE
    g.tasks["research"].result = {"answer": "Python 3.13 released October 2024"}
    ready = g.get_ready_tasks()
    assert len(ready) == 1 and ready[0].id == "summarize", f"Expected summarize ready, got {[t.id for t in ready]}"
    record("Summarize unblocked after research completes", True)

    g.tasks["summarize"].status = TaskStatus.COMPLETE
    assert g.is_complete()
    record("Graph is_complete after all tasks done", True)

    # Edge case: parallel tasks
    g2 = TaskGraph(root_goal="parallel test")
    g2.add(Task(id="a", goal="Task A"))
    g2.add(Task(id="b", goal="Task B"))
    g2.add(Task(id="c", goal="Merge", dependencies=["a", "b"]))
    assert len(g2.get_ready_tasks()) == 2
    record("Parallel tasks both ready simultaneously", True)

except Exception as e:
    record("TaskGraph", False, traceback.format_exc())


# ──── Step 3: SharedWorkspace ────
print("\n=== Step 3: SharedWorkspace ===")
try:
    from backend.memory.shared_workspace import SharedWorkspace

    ws = SharedWorkspace("test-session")
    ws.write("python_version", "3.13.1", agent_name="RESEARCHER")
    val = ws.read("python_version", reader_agent="ANALYST")
    assert val == "3.13.1"
    record("Write/read roundtrip", True)

    prov = ws.get_provenance()
    assert prov[0]["read_by"] == ["ANALYST"]
    record("Provenance tracking", True)

    assert ws.read("nonexistent", reader_agent="X") is None
    record("Missing key returns None", True)

    ws.write("python_version", "3.14.0", agent_name="CODER")
    assert ws.read("python_version", reader_agent="ANALYST") == "3.14.0"
    record("Overwrite updates value", True)

except Exception as e:
    record("SharedWorkspace", False, traceback.format_exc())


# ──── Step 4: Retry utility ────
print("\n=== Step 4: Retry Utility ===")

async def test_retry():
    import backend.utils.retry as r
    original_delays = r.RETRY_DELAYS
    r.RETRY_DELAYS = [0.05, 0.05, 0.05]
    
    try:
        # 4a: Succeeds on third attempt
        call_count = 0
        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 RESOURCE_EXHAUSTED")
            return "success"

        result = await r.with_retry(flaky_fn, fallback="fallback")
        assert result == "success", f"Got: {result}"
        assert call_count == 3
        record("Retry succeeds on 3rd attempt", True)

        # 4b: Non-retryable error raises immediately
        call_count = 0
        async def auth_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid API key")

        try:
            await r.with_retry(auth_error, fallback="fallback")
            record("Non-retryable raises", False, "Should have raised")
        except ValueError:
            assert call_count == 1
            record("Non-retryable raises immediately (1 call)", True)

        # 4c: Fallback on exhaustion
        async def always_429():
            raise Exception("429 rate limit")
        result = await r.with_retry(always_429, fallback="used_fallback")
        assert result == "used_fallback"
        record("Fallback returned on exhaustion", True)

    finally:
        r.RETRY_DELAYS = original_delays

try:
    asyncio.run(test_retry())
except Exception as e:
    record("Retry utility", False, traceback.format_exc())


# ──── Step 5: VectorMemory fallback ────
print("\n=== Step 5: VectorMemory Fallback ===")
try:
    from backend.memory.chroma_store import VectorMemory
    vm = VectorMemory(persist_dir="./data/test_chroma")
    record(f"VectorMemory instantiated (chroma={'available' if vm.is_available else 'fallback'})", True)
    
    async def test_memory():
        doc_id = await vm.save({"user": "test query", "assistant": "test response", "intent": "test"})
        assert doc_id, "save returned empty id"
        record("VectorMemory save", True)
        
        results = await vm.recall("test query", top_k=3)
        record(f"VectorMemory recall ({len(results)} results)", True)
    
    asyncio.run(test_memory())
except Exception as e:
    record("VectorMemory", False, traceback.format_exc())


# ──── Step 6: Tool Registry ────
print("\n=== Step 6: Tool Registry ===")
try:
    from backend.tools.registry import registry as tool_registry
    import backend.tools.system_tools  # trigger registration
    import backend.tools.search_tools

    tools = tool_registry.list_tools()
    assert len(tools) > 0, "No tools registered"
    record(f"Tool Registry: {len(tools)} tools registered", True)
    
    schemas = tool_registry.get_schemas()
    assert len(schemas) > 0
    record("Gemini schemas generated", True)
    
    # Test get_gemini_tools
    gemini_tools = tool_registry.get_gemini_tools()
    assert gemini_tools is not None
    record("get_gemini_tools() returns Tool objects", True)

except Exception as e:
    record("Tool Registry", False, traceback.format_exc())


# ──── Step 7: Skill system ────
print("\n=== Step 7: Skill System ===")
try:
    from backend.skills import Skill
    from backend.agents.task_graph import TaskGraph

    skill = Skill(
        name="test-skill",
        description="Test skill",
        trigger_phrases=["run test", "do test"],
        parameters=["topic"],
        task_template={
            "tasks": [
                {"id": "t1", "goal": "Research {topic}", "agent_profile": "RESEARCHER", "dependencies": []},
                {"id": "t2", "goal": "Summarize {topic}", "agent_profile": "ANALYST", "dependencies": ["t1"]},
            ]
        },
    )
    
    graph = skill.instantiate({"topic": "Python asyncio"})
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) == 2
    assert "Python asyncio" in graph.tasks["t1"].goal
    record("Skill instantiation with parameter substitution", True)

    d = skill.to_dict()
    s2 = Skill.from_dict(d)
    assert s2.name == skill.name
    record("Skill round-trip (to_dict/from_dict)", True)

except Exception as e:
    record("Skill System", False, traceback.format_exc())


# ──── Summary ────
print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print(f"  RESULTS: {passed} passed, {failed} failed, {len(results)} total")
if failed:
    print("\n  FAILURES:")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"    [FAIL] {name}: {detail[:200]}")
print("=" * 60)

sys.exit(1 if failed else 0)
