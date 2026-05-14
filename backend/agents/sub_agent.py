import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

from google import genai
from google.genai.types import (
    Content,
    GenerateContentConfig,
    Part,
)

from backend.agents import StepEvent
from backend.agents.specialists import AGENT_PROFILES
from backend.agents.task_graph import Task
from backend.memory.shared_workspace import SharedWorkspace
from backend.tools.registry import ToolRegistry
from backend.memory.chroma_store import VectorMemory

logger = logging.getLogger("agents.sub_agent")

SYSTEM_PROMPT_CORE = """You are JARVIS, an advanced personal AI assistant operating on the user's desktop.
You are formal, precise, and proactive — like a senior executive assistant.

CAPABILITIES:
You have access to tools to help complete tasks. When given a task:
1. THINK about what steps are needed
2. Use your tools to gather information or take actions
3. OBSERVE the results
4. Continue reasoning until the task is complete, then give a final answer

GUIDELINES:
- For simple questions or conversation, answer directly WITHOUT using tools
- For tasks requiring real-world interaction, use the appropriate tool
- If a tool fails, explain why and try an alternative approach
- Be concise in thinking but thorough in your final answer

You have access to the shared workspace — a whiteboard where ALL agents
contributing to this task write their findings. Read it to avoid redundant work.
Write your own findings using the write_to_workspace tool.
"""


class SubAgent:
    def __init__(
        self,
        agent_id: str,
        profile: str,
        workspace: SharedWorkspace,
        tool_registry: ToolRegistry,
        memory: VectorMemory,
    ):
        self.id = agent_id
        self.profile = AGENT_PROFILES.get(profile, AGENT_PROFILES.get("DEFAULT", {}))
        self.profile_name = profile
        self.workspace = workspace
        self.tools = tool_registry
        self.memory = memory
        self.max_iterations = self.profile.get("max_iterations", 6)

        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def run(self, task: Task) -> dict:
        workspace_context = self.workspace.read_all()

        profile_addon = self.profile.get("system_prompt_addon", "")
        system_prompt = SYSTEM_PROMPT_CORE + f"""

YOUR PROFILE: {self.profile_name}
{profile_addon}

SHARED WORKSPACE (what other agents have found so far):
{json.dumps(workspace_context, indent=2)}

When you discover information useful to other agents, call the
write_to_workspace tool with a descriptive key.
"""

        tool_schemas = self.tools.get_schemas(
            categories=self.profile.get("tool_categories")
        )
        tool_decls = self.tools.get_gemini_tools(
            categories=self.profile.get("tool_categories")
        )

        extra_tool = self._workspace_write_schema()
        if extra_tool:
            from google.genai.types import FunctionDeclaration, Tool
            fd = FunctionDeclaration(
                name=extra_tool["name"],
                description=extra_tool["description"],
                parameters=extra_tool.get("parameters"),
            )
            if tool_decls:
                tool_decls[0].function_declarations.append(fd)
            else:
                tool_decls = [Tool(function_declarations=[fd])]

        result = await self._react_loop(task.goal, system_prompt, tool_decls)

        self.workspace.write(
            key=f"task_{task.id}_result",
            value=result,
            agent_name=self.id
        )

        return result

    async def _react_loop(
        self,
        goal: str,
        system_prompt: str,
        tool_decls,
    ) -> dict:
        from backend.utils.retry import with_retry

        contents = [Content(role="user", parts=[Part(text=goal)])]
        full_response = ""
        tools_used = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            response = await with_retry(
                self.client.aio.models.generate_content,
                model=self.model,
                contents=contents,
                config=GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=tool_decls,
                    temperature=0.7,
                ),
                fallback=None
            )

            if not response or not response.candidates or not response.candidates[0].content.parts:
                break

            parts = response.candidates[0].content.parts
            contents.append(response.candidates[0].content)

            function_responses = []
            for part in parts:
                if part.function_call and part.function_call.name:
                    fc = part.function_call
                    tool_input = dict(fc.args) if fc.args else {}
                    tools_used.append(fc.name)

                    if fc.name == "write_to_workspace":
                        key = tool_input.get("key", "unknown")
                        value = tool_input.get("value", "")
                        self.workspace.write(key=key, value=value, agent_name=self.id)
                        function_responses.append(
                            Part.from_function_response(
                                name=fc.name,
                                response={"result": f"Written to workspace key '{key}'"}
                            )
                        )
                        continue

                    tool_result = await self.tools.execute(fc.name, tool_input)
                    result_preview = json.dumps(tool_result, default=str)
                    if len(result_preview) > 2000:
                        result_preview = result_preview[:2000] + "\n... (truncated)"

                    function_responses.append(
                        Part.from_function_response(
                            name=fc.name,
                            response={"result": tool_result}
                        )
                    )
                elif part.text:
                    full_response = part.text

            if function_responses:
                contents.append(Content(role="user", parts=function_responses))
                continue

            if full_response:
                break

        return {
            "answer": full_response or "No response generated.",
            "tools_used": tools_used,
            "iterations": iteration,
        }

    def _workspace_write_schema(self) -> dict:
        return {
            "name": "write_to_workspace",
            "description": "Store a finding in the shared workspace so other agents can use it",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "key": {"type": "STRING", "description": "Descriptive key (e.g. 'python_version', 'competitor_prices')"},
                    "value": {"type": "STRING", "description": "The information to store"}
                },
                "required": ["key", "value"]
            }
        }
