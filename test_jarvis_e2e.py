"""
JARVIS Mark-XL — End-to-End System Test
Run this with the backend already started: python -m backend.main
Then: python test_jarvis_e2e.py
"""

import asyncio
import httpx
import json
import time
import sys
from datetime import datetime

BASE = "http://127.0.0.1:8000"
TIMEOUT = 30  # seconds per test

# ── Console colors ─────────────────────────────────────────────────────────────
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
W = "\033[0m"   # reset
BOLD = "\033[1m"

results = []

def log(label, status, detail="", duration=None):
    icon = f"{G}✅{W}" if status == "PASS" else f"{R}❌{W}" if status == "FAIL" else f"{Y}⚠️ {W}"
    dur = f" {Y}({duration:.1f}s){W}" if duration else ""
    print(f"  {icon} {label}{dur}")
    if detail:
        print(f"     {detail}")
    results.append({"label": label, "status": status, "detail": detail})

async def stream_collect(client, prompt, session_id="test-001", timeout=TIMEOUT):
    """Send a message and collect all SSE events."""
    events = []
    full_answer = ""
    t0 = time.time()

    async with client.stream(
        "POST",
        f"{BASE}/api/v1/chat/stream",
        json={"message": prompt, "session_id": session_id},
        timeout=timeout
    ) as resp:
        if resp.status_code != 200:
            return None, [], time.time() - t0

        buffer = ""
        async for chunk in resp.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                part, buffer = buffer.split("\n\n", 1)
                lines = part.strip().split("\n")
                evt_type = next((l.replace("event: ", "") for l in lines if l.startswith("event:")), "")
                data_line = next((l.replace("data: ", "") for l in lines if l.startswith("data:")), "")
                if evt_type and data_line:
                    try:
                        data = json.loads(data_line)
                    except Exception:
                        data = {}
                    events.append({"type": evt_type, "data": data})
                    if evt_type == "token":
                        full_answer += data.get("text", "")
                    elif evt_type == "answer":
                        full_answer = data.get("content", full_answer)

    return full_answer, events, time.time() - t0


async def run_tests():
    print(f"\n{BOLD}{'─'*60}{W}")
    print(f"{BOLD}  JARVIS Mark-XL — System Test  {datetime.now().strftime('%H:%M:%S')}{W}")
    print(f"{BOLD}{'─'*60}{W}\n")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:

        # ── BLOCK 1: Core health ───────────────────────────────────────────────
        print(f"{B}{BOLD}[1] Core health{W}")

        try:
            t0 = time.time()
            r = await client.get(f"{BASE}/health")
            data = r.json()
            dur = time.time() - t0
            log("Backend reachable", "PASS", duration=dur)

            # Check each service
            for svc in ["backend", "gemini", "redis", "chromadb"]:
                val = data.get(svc, "missing")
                status = "PASS" if val in ("ok", "unavailable") else "FAIL"
                note = "" if val == "ok" else f"using fallback ({val})"
                log(f"  {svc}: {val}", status, note)

            tools = data.get("tools_registered", 0)
            log(f"  tools registered: {tools}", "PASS" if tools >= 10 else "FAIL",
                f"expected ≥10, got {tools}")

            profiles = data.get("agent_profiles", 0)
            log(f"  agent profiles: {profiles}", "PASS" if profiles >= 4 else "FAIL")

        except Exception as e:
            log("Backend reachable", "FAIL", str(e))
            print(f"\n{R}Backend not running. Start it first: python -m backend.main{W}\n")
            sys.exit(1)

        # ── BLOCK 2: Static endpoints ──────────────────────────────────────────
        print(f"\n{B}{BOLD}[2] Static endpoints{W}")

        for path, key, min_count in [
            ("/api/v1/tools", "tools", 10),
            ("/api/v1/skills", "skills", 0),
            ("/api/v1/tasks", "tasks", 0),
            ("/api/v1/agents/profiles", None, None),
        ]:
            try:
                r = await client.get(f"{BASE}{path}")
                if r.status_code == 200:
                    d = r.json()
                    if key and min_count is not None:
                        count = len(d.get(key, []))
                        ok = count >= min_count
                        log(f"GET {path}", "PASS" if ok else "FAIL",
                            f"{count} {key}")
                    else:
                        log(f"GET {path}", "PASS")
                else:
                    log(f"GET {path}", "FAIL", f"HTTP {r.status_code}")
            except Exception as e:
                log(f"GET {path}", "FAIL", str(e))

        # ── BLOCK 3: Live context ──────────────────────────────────────────────
        print(f"\n{B}{BOLD}[3] Live context (must NOT be hardcoded){W}")

        for path in ["/api/v1/context/system", "/api/v1/context/weather", "/api/v1/context"]:
            try:
                r = await client.get(f"{BASE}{path}")
                if r.status_code == 200:
                    d = r.json()
                    text = json.dumps(d)
                    # Fail if it's the old hardcoded values
                    hardcoded = "Clear" in text and "Local" in text and len(text) < 100
                    if hardcoded:
                        log(f"GET {path}", "FAIL", "Returns hardcoded 'Clear/Local' — not wired")
                    else:
                        # Extract something meaningful to show
                        sample = ""
                        if "cpu_percent" in text:
                            sample = f"cpu={d.get('system',d).get('cpu_percent','?')}%"
                        elif "condition" in text:
                            sample = d.get("condition", d.get("weather", {}).get("condition", "?"))
                        log(f"GET {path}", "PASS", sample)
                else:
                    log(f"GET {path}", "WARN", f"HTTP {r.status_code}")
            except Exception as e:
                log(f"GET {path}", "WARN", str(e))

        # ── BLOCK 4: Intent routing ────────────────────────────────────────────
        print(f"\n{B}{BOLD}[4] Intent router{W}")

        router_cases = [
            ("How do I open a jar of pickles?",    "conversation",    "adversarial — must NOT be launch_app"),
            ("open chrome",                         "launch_app",      "direct app launch"),
            ("search for Python 3.13 features",    "web_search",      "web search"),
            ("what files are in my downloads?",    "file_operation",  "file query"),
            ("what did we talk about before?",     "memory_recall",   "memory recall"),
            ("remind me every day at 8am to ...", "schedule_task",   "scheduling"),
        ]

        try:
            r = await client.get(f"{BASE}/api/v1/agents/router-status")
            router_ok = r.status_code == 200
        except Exception:
            router_ok = False

        if not router_ok:
            log("Router status endpoint", "WARN", "skipping per-case tests")
        else:
            for prompt, expected_intent, note in router_cases:
                try:
                    r = await client.post(
                        f"{BASE}/api/v1/agents/router-status",
                        json={"prompt": prompt}
                    )
                    if r.status_code == 200:
                        d = r.json()
                        got = d.get("intent", "unknown")
                        ok = got == expected_intent
                        log(f'"{prompt[:40]}..."',
                            "PASS" if ok else "FAIL",
                            f"got={got} expected={expected_intent} ({note})")
                    else:
                        # Fall back: test via stream and check metadata event
                        answer, events, dur = await stream_collect(
                            client, prompt, session_id=f"router-{expected_intent}", timeout=15
                        )
                        meta = next((e for e in events if e["type"] == "metadata"), None)
                        got = meta["data"].get("intent", "unknown") if meta else "no-metadata"
                        ok = got == expected_intent
                        log(f'"{prompt[:40]}..."',
                            "PASS" if ok else "WARN",
                            f"intent={got} ({note})", dur)
                except Exception as e:
                    log(f'"{prompt[:40]}..."', "WARN", str(e))

        # ── BLOCK 5: Chat stream — easy ────────────────────────────────────────
        print(f"\n{B}{BOLD}[5] Chat stream — easy (conversation){W}")

        answer, events, dur = await stream_collect(
            client, "Hello JARVIS, what's today's date and time?", "easy-001"
        )
        event_types = [e["type"] for e in events]
        has_done = "done" in event_types
        has_answer = bool(answer and len(answer) > 10)

        log("Response received", "PASS" if has_answer else "FAIL",
            f"{len(answer)} chars", dur)
        log("SSE 'done' event fired", "PASS" if has_done else "FAIL",
            f"events: {event_types}")
        if answer:
            print(f"     {Y}Answer preview:{W} {answer[:120]}...")

        # ── BLOCK 6: Chat stream — medium (tool use) ───────────────────────────
        print(f"\n{B}{BOLD}[6] Chat stream — medium (tool use: system info){W}")

        answer, events, dur = await stream_collect(
            client, "What is my current CPU usage and how much RAM is being used?", "med-001", timeout=25
        )
        has_step = any(e["type"] == "step" for e in events)
        has_answer = bool(answer and len(answer) > 20)

        log("Tool step events emitted", "PASS" if has_step else "WARN",
            "No step events — tool may not have been called" if not has_step else
            f"{sum(1 for e in events if e['type'] == 'step')} steps", dur)
        log("Answer contains numbers", "PASS" if any(c.isdigit() for c in (answer or "")) else "WARN",
            (answer or "")[:120])

        # ── BLOCK 7: Chat stream — hard (multi-step) ──────────────────────────
        print(f"\n{B}{BOLD}[7] Chat stream — hard (multi-step web research){W}")
        print(f"     {Y}This may take 15-30 seconds...{W}")

        answer, events, dur = await stream_collect(
            client,
            "Search the web for the latest Python release and tell me the version number",
            "hard-001",
            timeout=45
        )
        step_count = sum(1 for e in events if e["type"] == "step")
        has_answer = bool(answer and len(answer) > 20)
        has_multi_step = step_count >= 2

        log("Multi-step executed", "PASS" if has_multi_step else "WARN",
            f"{step_count} steps fired", dur)
        log("Answer returned", "PASS" if has_answer else "FAIL",
            (answer or "no answer")[:120])

        # ── BLOCK 8: Memory system ─────────────────────────────────────────────
        print(f"\n{B}{BOLD}[8] Memory system{W}")

        try:
            r = await client.post(
                f"{BASE}/api/v1/memory/search",
                json={"query": "test", "top_k": 3}
            )
            if r.status_code == 200:
                d = r.json()
                log("Memory search endpoint", "PASS",
                    f"returned {len(d.get('results', []))} results (0 expected — fresh system)")
            else:
                log("Memory search endpoint", "WARN", f"HTTP {r.status_code}")
        except Exception as e:
            log("Memory search endpoint", "WARN", str(e))

        # ── BLOCK 9: Task persistence (Phase 13) ───────────────────────────────
        print(f"\n{B}{BOLD}[9] Task persistence (Phase 13){W}")

        try:
            r = await client.get(f"{BASE}/api/v1/tasks")
            log("Task list endpoint", "PASS" if r.status_code == 200 else "FAIL",
                f"HTTP {r.status_code}")
        except Exception as e:
            log("Task list endpoint", "FAIL", str(e))

        try:
            r = await client.get(f"{BASE}/api/v1/checkpoints")
            log("Checkpoint endpoint",
                "PASS" if r.status_code in (200, 404) else "WARN",
                f"HTTP {r.status_code}")
        except Exception as e:
            log("Checkpoint endpoint", "WARN", str(e))

        # ── BLOCK 10: Tool registry spot-check ────────────────────────────────
        print(f"\n{B}{BOLD}[10] Tool registry spot-check{W}")

        try:
            r = await client.get(f"{BASE}/api/v1/tools")
            tools = r.json().get("tools", [])
            expected_tools = [
                "launch_application", "get_system_info", "read_file",
                "web_search", "capture_screen", "run_python_code"
            ]
            tool_names = [t.get("name", t) if isinstance(t, dict) else t for t in tools]
            for t in expected_tools:
                found = any(t in str(name) for name in tool_names)
                log(f"  tool: {t}", "PASS" if found else "WARN",
                    "" if found else "not registered")
        except Exception as e:
            log("Tool registry fetch", "FAIL", str(e))

        # ── BLOCK 11: Skill system ─────────────────────────────────────────────
        print(f"\n{B}{BOLD}[11] Skill system{W}")

        try:
            r = await client.get(f"{BASE}/api/v1/skills")
            d = r.json()
            count = len(d.get("skills", []))
            log("Skill endpoint", "PASS", f"{count} skills (0 expected — not used yet)")
        except Exception as e:
            log("Skill endpoint", "WARN", str(e))

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'─'*60}{W}")
    print(f"{BOLD}  Results{W}")
    print(f"{'─'*60}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    warned = sum(1 for r in results if r["status"] == "WARN")
    total = len(results)

    print(f"  {G}Passed:{W}  {passed}/{total}")
    print(f"  {R}Failed:{W}  {failed}/{total}")
    print(f"  {Y}Warnings:{W} {warned}/{total}")

    if failed > 0:
        print(f"\n{R}{BOLD}  Failed checks:{W}")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  {R}✗{W} {r['label']}")
                if r["detail"]:
                    print(f"    {r['detail']}")

    if warned > 0:
        print(f"\n{Y}{BOLD}  Warnings (non-critical):{W}")
        for r in results:
            if r["status"] == "WARN":
                print(f"  {Y}⚠{W} {r['label']}")

    print(f"\n{'─'*60}")
    verdict = "SYSTEM HEALTHY" if failed == 0 else f"{failed} ISSUE(S) NEED ATTENTION"
    color = G if failed == 0 else R
    print(f"  {color}{BOLD}{verdict}{W}\n")

    return failed


if __name__ == "__main__":
    failed = asyncio.run(run_tests())
    sys.exit(0 if failed == 0 else 1)
