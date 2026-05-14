# JARVIS Mark-XL Integration Tests
# Runs all validation steps without needing a running server.

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []


def report(name, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((name, passed))
    msg = f"  [{tag}] {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


# --- Step 1: Import Chain ---
print("\n--- Step 1: Import Chain ---")
try:
    from backend.agents.coordinator import AgentCoordinator
    from backend.agents.sub_agent import SubAgent
    from backend.memory.shared_workspace import SharedWorkspace
    from backend.skills.registry import SkillRegistry
    from backend.skills.extractor import SkillExtractor
    from backend.utils.retry import with_retry
    report("All core imports", True)
except Exception as e:
    report("All core imports", False, str(e))

# --- Step 2: TaskGraph ---
print("\n--- Step 2: TaskGraph Dependency Resolution ---")
try:
    from backend.agents.task_graph import Task, TaskGraph, TaskStatus

    g = TaskGraph(root_goal="research and summarize Python 3.13")
    t1 = g.add(Task(id="research", goal="Find Python 3.13 release notes", agent_profile="RESEARCHER"))
    t2 = g.add(Task(id="summarize", goal="Summarize findings", agent_profile="ANALYST", dependencies=["research"]))

    ready = g.get_ready_tasks()
    assert len(ready) == 1, f"Expected 1 ready task, got {len(ready)}"
    assert ready[0].id == "research", f"Expected 'research', got '{ready[0].id}'"
    report("Only 'research' initially ready", True)

    g.tasks["research"].status = TaskStatus.COMPLETE
    g.tasks["research"].result = {"answer": "Python 3.13 released October 2024"}
    ready2 = g.get_ready_tasks()
    assert len(ready2) == 1
    assert ready2[0].id == "summarize"
    report("'summarize' unlocked after 'research' completes", True)

    g.tasks["summarize"].status = TaskStatus.COMPLETE
    assert g.is_complete()
    report("Graph completeness check", True)

    summary = g.summary()
    assert summary["complete"] == 2 and summary["pending"] == 0
    report("Graph summary stats", True)
except Exception as e:
    report("TaskGraph tests", False, str(e))

# --- Step 3: SharedWorkspace ---
print("\n--- Step 3: SharedWorkspace ---")
try:
    ws = SharedWorkspace("test-session")
    ws.write("python_version", "3.13.1", agent_name="RESEARCHER")
    val = ws.read("python_version", reader_agent="ANALYST")
    assert val == "3.13.1", f"Expected '3.13.1', got '{val}'"
    report("Read/write", True)

    prov = ws.get_provenance()
    assert prov[0]["read_by"] == ["ANALYST"]
    report("Provenance tracking", True)

    val2 = ws.read("nonexistent", reader_agent="ANALYST")
    assert val2 is None
    report("Missing key returns None", True)

    ws.write("result_a", "data_a", agent_name="AGENT_1")
    ws.write("result_b", "data_b", agent_name="AGENT_2")
    all_data = ws.read_all()
    assert "result_a" in all_data and "result_b" in all_data
    report("Multi-agent read_all", True)
except Exception as e:
    report("SharedWorkspace tests", False, str(e))

# --- Step 4: Retry Utility ---
print("\n--- Step 4: Retry with Backoff ---")
try:
    import backend.utils.retry as retry_mod

    original_delays = retry_mod.RETRY_DELAYS
    retry_mod.RETRY_DELAYS = [0.05, 0.05, 0.05]

    # Test 1: Retryable error succeeds on 3rd attempt
    counter = [0]

    async def flaky_fn():
        counter[0] += 1
        if counter[0] < 3:
            raise Exception("429 RESOURCE_EXHAUSTED")
        return "success"

    result = asyncio.run(with_retry(flaky_fn, fallback="fallback"))
    assert result == "success", f"Expected 'success', got: {result}"
    assert counter[0] == 3, f"Expected 3 calls, got {counter[0]}"
    report("Exponential backoff (retryable error)", True)

    # Test 2: Non-retryable error raises immediately
    counter2 = [0]

    async def auth_error():
        counter2[0] += 1
        raise ValueError("Authentication failed")

    try:
        asyncio.run(with_retry(auth_error, fallback="fallback"))
        report("Non-retryable error propagation", False, "Should have raised")
    except ValueError:
        assert counter2[0] == 1, f"Should only call once, called {counter2[0]}"
        report("Non-retryable error propagation", True)

    # Test 3: All retries exhausted -> fallback returned
    async def always_fails():
        raise Exception("503 service unavailable")

    result3 = asyncio.run(with_retry(always_fails, fallback="fallback_value"))
    assert result3 == "fallback_value", f"Expected fallback, got: {result3}"
    report("Fallback on exhaustion", True)

    retry_mod.RETRY_DELAYS = original_delays

except Exception as e:
    report("Retry tests", False, str(e))

# --- Step 5: Tool Registry ---
print("\n--- Step 5: Tool Registry ---")
try:
    from backend.tools.registry import registry

    tools = registry.list_tools()
    tool_names = ", ".join(t["name"] for t in tools[:5])
    report(f"Tools registered: {len(tools)}", len(tools) > 0, tool_names)

    system_schemas = registry.get_schemas(category="system")
    report("Category filter (system)", True, f"{len(system_schemas)} schemas")

    multi_schemas = registry.get_schemas(categories=["system", "search"])
    report("Multi-category filter", True, f"{len(multi_schemas)} schemas")

    async def test_tool_exec():
        result = await registry.execute("nonexistent_tool", {})
        assert not result["success"]
        return result

    exec_result = asyncio.run(test_tool_exec())
    report("Unknown tool returns error", True)

except Exception as e:
    report("Tool Registry tests", False, str(e))

# --- Step 6: Skill Data Model ---
print("\n--- Step 6: Skill Data Model ---")
try:
    from backend.skills import Skill

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
    report("Skill creation", True)

    graph = skill.instantiate({"topic": "quantum computing"})
    assert "Research quantum computing" in [t.goal for t in graph.tasks.values()]
    assert "Summarize quantum computing" in [t.goal for t in graph.tasks.values()]
    report("Skill instantiation with parameter substitution", True)

    d = skill.to_dict()
    skill2 = Skill.from_dict(d)
    assert skill2.name == "test-skill"
    report("Skill serialization round-trip", True)

except Exception as e:
    report("Skill tests", False, str(e))

# --- Step 7: Agent Profiles ---
print("\n--- Step 7: Agent Profiles ---")
try:
    from backend.agents.specialists import AGENT_PROFILES, get_profile_for_intent
    from backend.agents import Intent

    assert "RESEARCHER" in AGENT_PROFILES
    assert "EXECUTOR" in AGENT_PROFILES
    assert "ANALYST" in AGENT_PROFILES
    assert "CODER" in AGENT_PROFILES
    assert "DEFAULT" in AGENT_PROFILES
    report(f"All profiles present ({len(AGENT_PROFILES)})", True)

    p = get_profile_for_intent(Intent.WEB_SEARCH, confidence=0.9)
    assert p is not None
    report("Intent -> profile mapping (high confidence)", True)

    p2 = get_profile_for_intent(Intent.WEB_SEARCH, confidence=0.3)
    assert p2 is None
    report("Intent -> profile mapping (low confidence -> None)", True)

except Exception as e:
    report("Agent profile tests", False, str(e))

# --- Summary ---
print("\n" + "=" * 60)
passed = sum(1 for _, p in results if p)
total = len(results)
all_pass = passed == total
print(f"Results: {passed}/{total} tests passed")
if not all_pass:
    print("Failed:")
    for name, p in results:
        if not p:
            print(f"  X {name}")
print("=" * 60)

sys.exit(0 if all_pass else 1)
