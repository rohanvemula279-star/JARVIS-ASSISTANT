"""
JARVIS Multi-Agent Core
Agents: Commander, Avenger, Browser, Desktop, Memory, Planner, Voice
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("agents")

class AgentType(Enum):
    COMMANDER = "commander"
    AVENGER = "avenger"
    BROWSER = "browser"
    DESKTOP = "desktop"
    MEMORY = "memory"
    PLANNER = "planner"
    VOICE = "voice"

class TaskType(Enum):
    CHAT = "chat"           # Conversation / Q&A
    ACTION = "action"       # Fast execution (open app, type, etc)
    WORKFLOW = "workflow"   # Multi-step task
    MEMORY = "memory"       # Remember/recall
    EXTERNAL = "external"   # Route to external daemon

@dataclass
class AgentResult:
    agent: str
    success: bool
    result: Any
    latency_ms: float
    fallback_used: bool = False

class BaseAgent:
    """Base class for all agents"""

    def __init__(self, name: str, agent_type: AgentType):
        self.name = name
        self.agent_type = agent_type
        self.stats = {"invocations": 0, "total_latency_ms": 0}

    async def execute(self, prompt: str, context: Optional[Dict] = None) -> AgentResult:
        """Execute agent task"""
        import time
        start = time.time()
        self.stats["invocations"] += 1

        try:
            result = await self._execute(prompt, context or {})
            latency = (time.time() - start) * 1000
            self.stats["total_latency_ms"] += latency
            return AgentResult(
                agent=self.name,
                success=True,
                result=result,
                latency_ms=round(latency, 2)
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"{self.name} error: {e}")
            return AgentResult(
                agent=self.name,
                success=False,
                result=str(e),
                latency_ms=round(latency, 2)
            )

    async def _execute(self, prompt: str, context: Dict) -> Any:
        """Override in subclasses"""
        raise NotImplementedError

    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "avg_latency_ms": round(self.stats["total_latency_ms"] / max(1, self.stats["invocations"]), 2)
        }