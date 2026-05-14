import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional

from google import genai
from google.genai.types import GenerateContentConfig

from backend.agents import StepEvent
from backend.agents.sub_agent import SubAgent
from backend.agents.task_graph import TaskGraph, TaskStatus
from backend.memory.shared_workspace import SharedWorkspace
from backend.tools.registry import ToolRegistry
from backend.memory.chroma_store import VectorMemory
from backend.context.context_service import LiveContextService

logger = logging.getLogger("agents.coordinator")

SYNTHESIS_PROMPT = """
You are JARVIS, synthesizing results from multiple specialized agents.

Original goal: {goal}

Results from all agents:
{results}

Synthesize a clear, complete final answer that addresses the original goal.
Combine insights from each agent into a cohesive response.
"""


class AgentCoordinator:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        memory: VectorMemory,
        context_service: LiveContextService,
    ):
        self.tools = tool_registry
        self.memory = memory
        self.context = context_service

        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def execute_plan(
        self,
        graph: TaskGraph,
        session_id: str,
    ) -> AsyncGenerator[StepEvent, None]:

        workspace = SharedWorkspace(session_id)
        completed_ids = set()

        while not graph.is_complete():
            ready_tasks = graph.get_ready_tasks()

            if not ready_tasks:
                all_done = all(
                    t.status in (TaskStatus.COMPLETE, TaskStatus.FAILED)
                    for t in graph.tasks.values()
                )
                if all_done:
                    break
                logger.warning("No ready tasks but graph not complete — possible dependency deadlock")
                break

            agent_runs = []
            for task in ready_tasks:
                task.status = TaskStatus.RUNNING

                agent = SubAgent(
                    agent_id=f"{task.agent_profile}_{task.id}",
                    profile=task.agent_profile,
                    workspace=workspace,
                    tool_registry=self.tools,
                    memory=self.memory,
                )

                yield StepEvent(
                    type="agent_spawned",
                    content=f"Spawning {task.agent_profile} agent for: {task.goal[:80]}",
                    tool_name=task.agent_profile,
                    tool_input={"task_id": task.id, "goal": task.goal},
                    iteration=len(completed_ids),
                )

                agent_runs.append((task, agent.run(task)))

            results = await asyncio.gather(
                *[run for _, run in agent_runs],
                return_exceptions=True
            )

            for (task, _), result in zip(agent_runs, results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                    yield StepEvent(
                        type="agent_failed",
                        content=f"{task.id} ({task.agent_profile}) failed: {result}",
                        tool_name=task.agent_profile,
                        tool_input={"task_id": task.id},
                        iteration=len(completed_ids),
                    )
                else:
                    task.status = TaskStatus.COMPLETE
                    task.result = result
                    completed_ids.add(task.id)
                    yield StepEvent(
                        type="agent_complete",
                        content=f"{task.id} ({task.agent_profile}) done",
                        tool_name=task.agent_profile,
                        tool_input={"task_id": task.id},
                        iteration=len(completed_ids),
                    )

        final = await self._run_synthesis(graph, workspace, session_id)
        yield StepEvent(type="answer", content=final)

    async def _run_synthesis(
        self,
        graph: TaskGraph,
        workspace: SharedWorkspace,
        session_id: str,
    ) -> str:
        from backend.utils.retry import with_retry

        final_context = workspace.read_all()
        prompt = SYNTHESIS_PROMPT.format(
            goal=graph.root_goal,
            results=json.dumps(final_context, indent=2),
        )

        response = await with_retry(
            self.client.aio.models.generate_content,
            model=self.model,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.5),
            fallback=None,
        )

        if response and response.candidates and response.candidates[0].content.parts:
            return "".join(
                p.text for p in response.candidates[0].content.parts if p.text
            )
        return "Synthesis complete. I was unable to generate a final answer."
