"""
JARVIS Mark-XL Agent Base Classes
Defines foundational types for the multi-agent system.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("agents")


class Intent(str, Enum):
    """All classifiable user intents."""
    LAUNCH_APP = "launch_app"
    WEB_SEARCH = "web_search"
    FILE_OPERATION = "file_operation"
    BROWSER_AUTOMATION = "browser_automation"
    SYSTEM_QUERY = "system_query"
    MEMORY_RECALL = "memory_recall"
    CONVERSATION = "conversation"
    CODE_EXECUTION = "code_execution"
    SCHEDULE_TASK = "schedule_task"
    MULTI_STEP = "multi_step"


@dataclass
class RouteDecision:
    """Result of intent classification."""
    intent: Intent
    confidence: float  # 0.0 - 1.0
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    requires_planning: bool = False
    reasoning: str = ""


@dataclass
class StepEvent:
    """A single step in the ReAct loop, streamed to frontend."""
    type: str  # "thought" | "action" | "observation" | "answer" | "error"
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    iteration: int = 0


@dataclass
class AgentResult:
    """Final result from an agent execution."""
    agent: str
    success: bool
    result: Any
    latency_ms: float
    steps: List[StepEvent] = field(default_factory=list)
    fallback_used: bool = False


class BaseAgent:
    """Base class for all agents"""

    def __init__(self, name: str):
        self.name = name
        self.stats = {"invocations": 0, "total_latency_ms": 0}

    async def execute(self, prompt: str, context: Optional[Dict] = None) -> AgentResult:
        """Execute agent task with timing."""
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
        invocations = max(1, self.stats["invocations"])
        return {
            **self.stats,
            "avg_latency_ms": round(self.stats["total_latency_ms"] / invocations, 2)
        }
