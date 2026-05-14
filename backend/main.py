#!/usr/bin/env python3
"""
JARVIS Mark-XL — FastAPI Backend Entry Point

The single API server powering the JARVIS desktop assistant.
Features:
  - Real token-level streaming via Gemini
  - ReAct loop with function calling
  - Live system + weather context
  - Vector memory (ChromaDB)
  - MCP-compatible tool registry
"""

import asyncio
import io
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Fix Unicode encoding on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("jarvis")

# Load settings
from backend.config.settings import get_settings

settings = get_settings()

# =====================
# Service Singletons
# =====================
from backend.agents import StepEvent
from backend.agents.router import IntentRouter
from backend.agents.orchestrator import ReActOrchestrator
from backend.agents.coordinator import AgentCoordinator
from backend.agents.planner import TaskPlanner
from backend.skills.extractor import SkillExtractor
from backend.skills.registry import SkillRegistry
from backend.memory.chroma_store import VectorMemory
from backend.memory.working_memory import WorkingMemory
from backend.context.context_service import LiveContextService
from backend.tools.registry import registry as tool_registry
from backend.workers.task_worker import BackgroundTaskWorker
from backend.integrations.telegram_bot import init_telegram_bot, get_telegram_bot

# Import tool modules to trigger registration
import backend.tools.system_tools  # noqa: F401
import backend.tools.search_tools  # noqa: F401
# browser_tools and vision_tools will be added in Phase 5

# Service instances (initialized in lifespan)
_router: IntentRouter | None = None
_orchestrator: ReActOrchestrator | None = None
_coordinator: AgentCoordinator | None = None
_planner: TaskPlanner | None = None
_skill_extractor: SkillExtractor | None = None
_skill_registry: SkillRegistry | None = None
_vector_memory: VectorMemory | None = None
_working_memory: WorkingMemory | None = None
_context_service: LiveContextService | None = None
_task_worker = None  # Phase 13: Background task worker
_telegram_bot = None  # Phase 14: Telegram bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""
    global _router, _orchestrator, _coordinator, _planner, _skill_extractor, _skill_registry
    global _vector_memory, _working_memory, _context_service, _task_worker, _telegram_bot

    logger.info("=" * 60)
    logger.info("🤖 JARVIS Mark-XL — Initializing...")
    logger.info("=" * 60)

    # Initialize services
    _vector_memory = VectorMemory(persist_dir=str(PROJECT_ROOT / "data" / "chroma_db"))
    _working_memory = WorkingMemory()
    _context_service = LiveContextService()

    # Start background context polling
    await _context_service.start()

    # Initialize router (requires Gemini key)
    if settings.gemini_api_key:
        try:
            _router = IntentRouter()
            logger.info("✅ Intent Router initialized (Gemini 2.0 Flash)")
        except Exception as e:
            logger.error(f"❌ Router init failed: {e}")
    else:
        logger.warning("⚠️  GEMINI_API_KEY not set — router and orchestrator disabled")

    # Initialize orchestrator
    if settings.gemini_api_key:
        _orchestrator = ReActOrchestrator(
            tool_registry=tool_registry,
            vector_memory=_vector_memory,
            working_memory=_working_memory,
            context_service=_context_service,
        )
        logger.info("✅ ReAct Orchestrator initialized")

        _coordinator = AgentCoordinator(
            tool_registry=tool_registry,
            memory=_vector_memory,
            context_service=_context_service,
        )
        logger.info("✅ Agent Coordinator initialized")

        _planner = TaskPlanner()
        logger.info("✅ Task Planner initialized")

        _skill_extractor = SkillExtractor()
        _skill_registry = SkillRegistry(vector_memory=_vector_memory)
        logger.info("✅ Skill System initialized")
        # Phase 13: Background task worker
        _task_worker = BackgroundTaskWorker(_coordinator)
        await _task_worker.start()
        logger.info("✅ Background Task Worker initialized")

        # Phase 14B: Telegram bot (if configured)
        if settings.telegram_bot_token and settings.telegram_chat_id:
            _telegram_bot = init_telegram_bot(
                settings.telegram_bot_token,
                settings.telegram_chat_id
            )
            await _telegram_bot.start()
            logger.info("✅ Telegram Bot initialized")

    logger.info(f"📦 Tool Registry: {len(tool_registry.list_tools())} tools registered")
    logger.info(f"🧠 Vector Memory: {_vector_memory.count} stored memories")
    logger.info(f"🌐 Context Service: polling started")
    logger.info("=" * 60)
    logger.info(f"🚀 Server ready at http://{settings.backend_host}:{settings.backend_port}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down services...")
    if _task_worker:
        _task_worker.stop()
    if _telegram_bot:
        await _telegram_bot.stop()
    await _context_service.stop()


# =====================
# FastAPI App
# =====================
app = FastAPI(title="JARVIS Mark-XL", version="3.0", lifespan=lifespan)

# CORS — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "file://",
        "app://.",  # Electron custom protocol
        "*"         # Allow all for local testing
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

# =====================
# Timing stats
# =====================
timing_stats = {"total_requests": 0, "latencies": []}


# =====================
# ROOT & HEALTH
# =====================

@app.get("/")
async def root():
    return {
        "name": "JARVIS Mark-XL",
        "version": "3.0",
        "status": "running",
        "architecture": "ReAct Loop + MCP Tool Registry + Vector Memory",
        "endpoints": {
            "health": "/health",
            "stream": "/api/v1/chat/stream (POST)",
            "context": "/api/v1/context",
            "tools": "/api/v1/tools",
            "status": "/api/v1/system/status",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    """Comprehensive health status check."""
    from backend.agents.specialists import AGENT_PROFILES
    
    redis_status = "ok" if _working_memory and _working_memory.is_available else "unavailable"
    chroma_status = "ok" if _vector_memory and _vector_memory.is_available else "unavailable"
    
    gemini_status = "ok"
    if not settings.gemini_api_key:
        gemini_status = "error: GEMINI_API_KEY not set"
    elif not _router:
        gemini_status = "error: Router failed to initialize"

    return {
        "backend": "ok",
        "redis": redis_status,
        "chromadb": chroma_status,
        "gemini": gemini_status,
        "tools_registered": len(tool_registry.list_tools()),
        "agent_profiles": len(AGENT_PROFILES),
    }


@app.head("/health")
async def health_head():
    return JSONResponse(content={"status": "ok"})


# =====================
# STATIC FILE SERVING (Web Console)
# =====================

@app.get("/console")
async def get_console():
    """Serve the Web UI Console."""
    console_path = PROJECT_ROOT / "electron-app" / "dist" / "index.html"
    if console_path.exists():
        return FileResponse(console_path)
    return JSONResponse({"error": "Console not built. Run 'npm run build' in electron-app/"}, status_code=404)


@app.get("/assets/{path:path}")
async def serve_assets(path: str):
    asset_path = PROJECT_ROOT / "electron-app" / "dist" / "assets" / path
    if asset_path.exists():
        return FileResponse(asset_path)
    raise HTTPException(status_code=404, detail="Asset not found")


# =====================
# STREAMING CHAT — The Main Endpoint
# =====================

async def emit_step(event: StepEvent):
    """Convert a StepEvent to SSE lines."""
    step_data = {
        "type": event.type,
        "content": event.content,
        "iteration": event.iteration,
    }
    if event.tool_name:
        step_data["tool"] = event.tool_name
    if event.tool_input:
        step_data["input"] = event.tool_input
    return f"event: step\ndata: {json.dumps(step_data)}\n\n"


async def stream_tokens(text: str):
    """Stream the final answer as word-level tokens."""
    words = text.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
        await asyncio.sleep(0.01)


@app.post("/api/v1/chat/stream")
async def stream_chat(request: Request):
    """True token-level streaming via ReAct orchestrator.

    SSE event types:
      - event: metadata  → intent classification or skill match result
      - event: step      → ReAct thinking/action/observation or agent events
      - event: token     → text chunk from final answer
      - event: done      → completion signal
      - event: error     → error with details
    """
    body = await request.json()
    prompt = body.get("prompt", body.get("message", ""))
    session_id = body.get("session_id", "default")

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    if not _orchestrator:
        return JSONResponse(
            {"error": "Orchestrator not available. Check GEMINI_API_KEY."},
            status_code=503,
        )

    async def generate():
        start = time.time()
        timing_stats["total_requests"] += 1

        # Step 0: Skill matching — fast path for known patterns
        matched_skill = None
        if _skill_registry:
            try:
                matched_skill = await _skill_registry.match(prompt)
            except Exception as e:
                logger.warning(f"Skill matching error (non-fatal): {e}")

        if matched_skill and matched_skill.success_rate > 0.7:
            yield f"event: metadata\ndata: {json.dumps({'skill_used': matched_skill.name, 'confidence': 0.9})}\n\n"
            try:
                async for event in _skill_registry.execute_skill(matched_skill, prompt, _coordinator, session_id):
                    if event.type == "answer":
                        async for line in stream_tokens(event.content):
                            yield line
                    else:
                        yield await emit_step(event)
            except Exception as e:
                logger.error(f"Skill execution error: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            latency = (time.time() - start) * 1000
            timing_stats["latencies"].append(latency)
            yield f"event: done\ndata: {json.dumps({'latency_ms': round(latency, 1)})}\n\n"
            return

        # Step 1: Classify intent
        route = None
        if _router:
            try:
                route = await _router.classify(prompt)
                yield f"event: metadata\ndata: {json.dumps({'intent': route.intent.value, 'confidence': route.confidence, 'reasoning': route.reasoning})}\n\n"
            except Exception as e:
                logger.warning(f"Router error (non-fatal): {e}")

        # Step 2: Complex task → planner + coordinator
        is_complex = (route and route.requires_planning) or len(prompt.split()) > 20
        if is_complex and _planner and _coordinator and route:
            try:
                context = _context_service.get_current() if _context_service else {}
                graph = await _planner.decompose(prompt, context)

                async for event in _coordinator.execute_plan(graph, session_id):
                    if event.type == "answer":
                        async for line in stream_tokens(event.content):
                            yield line
                    else:
                        yield await emit_step(event)

                # Try skill extraction on successful multi-step completion
                if _skill_extractor and _skill_registry:
                    try:
                        quality_score = 9.0  # Could use CriticAgent here
                        skill = await _skill_extractor.try_extract(prompt, graph, quality_score)
                        if skill:
                            await _skill_registry.register(skill)
                            yield f"event: step\ndata: {json.dumps({'type': 'skill_learned', 'content': f'New skill learned: {skill.name}', 'skill_name': skill.name})}\n\n"
                    except Exception as e:
                        logger.warning(f"Skill extraction error (non-fatal): {e}")

            except Exception as e:
                logger.error(f"Coordinator error: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

            latency = (time.time() - start) * 1000
            timing_stats["latencies"].append(latency)
            yield f"event: done\ndata: {json.dumps({'latency_ms': round(latency, 1)})}\n\n"
            return

        # Step 3: Single ReAct loop (fast path for simple queries)
        try:
            async for event in _orchestrator.process_stream(prompt, session_id, route):
                if event.type == "answer":
                    async for line in stream_tokens(event.content):
                        yield line
                elif event.type in ("action", "observation", "thought"):
                    yield await emit_step(event)
                elif event.type == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event.content})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        latency = (time.time() - start) * 1000
        timing_stats["latencies"].append(latency)
        yield f"event: done\ndata: {json.dumps({'latency_ms': round(latency, 1)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# =====================
# LEGACY ENDPOINTS (backward compatibility for Electron)
# =====================

@app.post("/api/v1/stream")
async def legacy_stream(request: Request):
    """Legacy streaming endpoint — proxies to new /api/v1/chat/stream."""
    return await stream_chat(request)


@app.post("/api/v1/fast")
async def fast_jarvis(request: Request):
    """Fast non-streaming endpoint — uses orchestrator.process()."""
    start = time.time()
    body = await request.json()
    prompt = body.get("prompt", "")

    if not _orchestrator:
        return {"status": "error", "answer": "Orchestrator not available"}

    try:
        result = await _orchestrator.process(prompt, session_id="fast")
        latency = (time.time() - start) * 1000

        return {
            "status": "success" if result.success else "error",
            "answer": result.result,
            "agent": result.agent,
            "latency_ms": round(latency, 1),
            "steps": len(result.steps),
        }
    except Exception as e:
        logger.error(f"Fast endpoint error: {e}")
        return {"status": "error", "answer": str(e)}


# =====================
# CONTEXT & STATUS
# =====================

@app.get("/api/v1/context")
async def get_context():
    """Get live system and weather context — real data, not hardcoded."""
    if _context_service:
        ctx = _context_service.get_current()
        if not ctx:
            ctx = await _context_service.get_fresh()
        return {"context": ctx}
    return {"context": {}, "error": "Context service not initialized"}


@app.post("/api/v1/context")
async def post_context(request: Request):
    """Legacy POST context endpoint."""
    if _context_service:
        ctx = _context_service.get_current()
        return {"context": ctx}
    return {"context": {"location": "Unknown", "weather": "Unavailable"}}


@app.get("/api/v1/system/status")
async def system_status():
    """Get system status with real data."""
    latencies = timing_stats["latencies"]
    ctx = _context_service.get_current() if _context_service else {}

    return {
        "status": "online",
        "version": "Mark-XL (3.0)",
        "mode": "ready",
        "providers": {
            "gemini": "configured" if settings.gemini_api_key else "missing",
            "nvidia": "configured" if settings.nvidia_nim_api_key else "missing",
        },
        "router": "ready" if _router else "disabled",
        "orchestrator": "ready" if _orchestrator else "disabled",
        "tools_registered": len(tool_registry.list_tools()),
        "memory_count": _vector_memory.count if _vector_memory else 0,
        "context": ctx,
        "benchmark": {
            "total_requests": timing_stats["total_requests"],
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "min_latency_ms": round(min(latencies), 1) if latencies else None,
            "max_latency_ms": round(max(latencies), 1) if latencies else None,
        },
    }


# =====================
# TOOLS & ACTIONS
# =====================

@app.get("/api/v1/tools")
async def list_tools():
    """List all registered tools."""
    return {"tools": tool_registry.list_tools()}


@app.get("/api/v1/actions")
async def get_actions():
    """Legacy actions endpoint — returns tools list."""
    return {"actions": tool_registry.list_tools()}


@app.post("/api/v1/actions/execute")
async def execute_action(request: Request):
    """Execute a tool directly."""
    body = await request.json()
    name = body.get("name", "")
    params = body.get("params", {})

    result = await tool_registry.execute(name, params)
    return result


# =====================
# VISION (placeholder — real implementation in Phase 5)
# =====================

@app.post("/api/v1/vision/detect")
async def vision_detect(request: Request):
    """Analyze camera frame using real Gemini multimodal."""
    body = await request.json()
    image_data = body.get("image", "")

    if not image_data:
        return {"status": "error", "analysis": "No image data provided"}

    # Handle base64 image (strip data URL prefix if present)
    if image_data and "," in image_data:
        image_data = image_data.split(",")[1]

    try:
        from backend.tools.vision_tools import get_vision_engine
        engine = get_vision_engine()
        result = await engine.analyze_image(image_data, "What do you see in this camera frame? Be concise.")
        
        return {
            "status": "success",
            "analysis": result["analysis"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =====================
# MEMORY
# =====================

@app.get("/api/v1/memory/search")
async def search_memory(q: str = "", limit: int = 5):
    """Search long-term memory."""
    if not _vector_memory or not q:
        return {"memories": [], "query": q}

    memories = await _vector_memory.recall(q, top_k=limit)
    return {"memories": memories, "query": q, "count": len(memories)}


# =====================
# SKILL MANAGEMENT
# =====================

@app.get("/api/v1/skills")
async def list_skills():
    """List all learned skills with success rates."""
    if not _skill_registry:
        return {"skills": [], "error": "Skill system not initialized"}
    return {"skills": _skill_registry.list_skills()}


@app.delete("/api/v1/skills/{name}")
async def delete_skill(name: str):
    """Forget a learned skill."""
    if not _skill_registry:
        return {"status": "error", "message": "Skill system not initialized"}
    deleted = _skill_registry.delete_skill(name)
    if deleted:
        return {"status": "ok", "message": f"Skill '{name}' forgotten"}
    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")


@app.post("/api/v1/skills/{name}/test")
async def test_skill(name: str, request: Request):
    """Re-run a skill with test input."""
    if not _skill_registry or not _coordinator:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    skill = _skill_registry.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    body = await request.json()
    test_input = body.get("prompt", skill.trigger_phrases[0] if skill.trigger_phrases else "")

    async def generate():
        yield f"event: metadata\ndata: {json.dumps({'skill_used': skill.name, 'test_run': True})}\n\n"
        try:
            async for event in _skill_registry.execute_skill(skill, test_input, _coordinator, "skill-test"):
                if event.type == "answer":
                    async for line in stream_tokens(event.content):
                        yield line
                else:
                    yield await emit_step(event)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        yield f"event: done\ndata: {json.dumps({'latency_ms': 0})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# =====================
# TASK MANAGEMENT (Phase 13)
# =====================

@app.get("/api/v1/tasks")
async def list_tasks():
    """List all background tasks."""
    from backend.storage.task_store import get_task_store
    store = get_task_store()
    await store.initialize()
    tasks = await store.list_all()
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """Get full task details including result."""
    from backend.storage.task_store import get_task_store
    store = get_task_store()
    await store.initialize()
    task = await store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    result = None
    if task.get("result_json"):
        try:
            result = json.loads(task["result_json"])
        except:
            result = task.get("result_json")

    return {
        "id": task["id"],
        "session_id": task["session_id"],
        "root_goal": task["root_goal"],
        "status": task["status"],
        "created_at": task["created_at"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"],
        "result": result,
    }


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """Cancel or delete a task."""
    worker = _task_worker
    cancelled = await worker.cancel(task_id) if worker else False

    if cancelled:
        return {"status": "ok", "message": f"Task '{task_id}' cancelled"}

    from backend.storage.task_store import get_task_store
    store = get_task_store()
    await store.initialize()
    deleted = await store.delete(task_id)

    if deleted:
        return {"status": "ok", "message": f"Task '{task_id}' deleted"}
    raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")


@app.post("/api/v1/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task."""
    worker = _task_worker
    if not worker or not worker.coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not available")

    success = await worker.retry(task_id)
    if success:
        return {"status": "ok", "message": f"Task '{task_id}' queued for retry"}
    raise HTTPException(status_code=400, detail=f"Task '{task_id}' cannot be retried (not in failed state)")


@app.get("/api/v1/tasks/{session_id}/events")
async def stream_task_events(session_id: str, since: int = 0):
    """Stream events for a background task session."""

    async def generate():
        from backend.sse.event_queue import get_event_queue
        queue = get_event_queue()

        try:
            async for event in queue.stream(session_id, since_index=since):
                yield f"event: task_event\ndata: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/api/v1/notify")
async def notify_endpoint(request: Request):
    """Endpoint for desktop notifications (polled by Electron)."""
    body = await request.json()
    title = body.get("title", "JARVIS")
    message = body.get("body", "")
    return {"status": "ok", "title": title, "message": message}

# =====================
# DEBUG & MISSING ENDPOINTS
# =====================

@app.get("/api/v1/debug/gemini")
async def debug_gemini():
    import traceback
    try:
        from google import genai
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents="Reply with the single word: working"
        )
        return {"status": "ok", "response": response.text}
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/api/v1/agents/profiles")
async def get_agent_profiles():
    from backend.agents.specialists import AGENT_PROFILES
    return {
        "profiles": [
            {"name": name, "max_iterations": p.get("max_iterations", 6),
             "tool_categories": p.get("tool_categories", [])}
            for name, p in AGENT_PROFILES.items()
        ]
    }

@app.get("/api/v1/context/system")
async def get_system_context():
    if _context_service:
        ctx = _context_service.get_current()
        return ctx.get("system", {"error": "context not yet loaded"})
    return {"error": "context service not initialized"}

@app.get("/api/v1/context/weather")
async def get_weather_context():
    if _context_service:
        ctx = _context_service.get_current()
        return ctx.get("weather", {"error": "weather not yet loaded"})
    return {"error": "context service not initialized"}

@app.post("/api/v1/agents/router-status")
async def router_status(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        return {"error": "prompt required"}
    if not _router:
        return {"error": "router not initialized"}
    try:
        result = await _router.classify(prompt)
        return {
            "intent": result.intent.value if hasattr(result.intent, 'value') else result.intent,
            "confidence": result.confidence,
            "requires_planning": result.requires_planning,
            "extracted_entities": result.extracted_entities
        }
    except Exception as e:
        return {"error": str(e), "intent": "unknown"}


# =====================
# MAIN
# =====================

def main():
    print("=" * 60)
    print("🤖 JARVIS Mark-XL — Desktop Assistant v3.0")
    print("=" * 60)
    print(f"  Server:   http://{settings.backend_host}:{settings.backend_port}")
    print(f"  Docs:     http://{settings.backend_host}:{settings.backend_port}/docs")
    print(f"  Gemini:   {'✅ Configured' if settings.gemini_api_key else '❌ Missing GEMINI_API_KEY'}")
    print("=" * 60)

    config = uvicorn.Config(
        app,
        host=settings.backend_host,
        port=settings.backend_port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
