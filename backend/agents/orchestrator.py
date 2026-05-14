"""
ReAct Orchestrator — The cognitive core of JARVIS Mark-XL.

Implements the ReAct (Reason + Act) loop with Gemini function calling:
  THINK → ACT (tool call) → OBSERVE (result) → repeat until done.

Uses the new google-genai SDK with automatic function calling.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from google import genai
from google.genai.types import (
    Content,
    FunctionDeclaration,
    GenerateContentConfig,
    Part,
    Tool,
)

from backend.agents import AgentResult, Intent, RouteDecision, StepEvent
from backend.config.settings import get_settings
from backend.memory.chroma_store import VectorMemory
from backend.memory.working_memory import WorkingMemory
from backend.tools.registry import ToolRegistry
from backend.context.context_service import LiveContextService

logger = logging.getLogger("agents.orchestrator")

ORCHESTRATOR_SYSTEM_PROMPT = """You are JARVIS, an advanced personal AI assistant operating on the user's desktop.
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
- Address the user respectfully ("sir" is appropriate)
- When reporting system info, format numbers clearly

CURRENT CONTEXT:
{context}

RELEVANT MEMORIES:
{memories}
"""


class ReActOrchestrator:
    """The central brain of JARVIS — drives autonomous multi-step task execution."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        vector_memory: VectorMemory,
        working_memory: WorkingMemory,
        context_service: LiveContextService,
        max_iterations: int = 8,
    ):
        self.tools = tool_registry
        self.vector_memory = vector_memory
        self.working_memory = working_memory
        self.context_service = context_service
        self.max_iterations = max_iterations

        settings = get_settings()
        from google.api_core import client_options
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1"}
        )
        self.model = settings.gemini_model

    def _build_tool_declarations(self) -> Optional[List[Tool]]:
        """Convert registry tools to Gemini Tool declarations."""
        schemas = self.tools.get_schemas()
        if not schemas:
            return None

        declarations = []
        for schema in schemas:
            params = schema.get("parameters", {})
            # Convert property types to lowercase for the new SDK
            properties = {}
            for name, prop in params.get("properties", {}).items():
                prop_copy = dict(prop)
                if "type" in prop_copy:
                    prop_copy["type"] = prop_copy["type"].upper()
                properties[name] = prop_copy

            fd = FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters={
                    "type": "OBJECT",
                    "properties": properties,
                    "required": params.get("required", []),
                } if properties else None,
            )
            declarations.append(fd)

        return [Tool(function_declarations=declarations)]

    async def process_stream(
        self,
        prompt: str,
        session_id: str,
        route: Optional[RouteDecision] = None,
    ) -> AsyncGenerator[StepEvent, None]:
        """Stream ReAct loop steps back to the frontend."""
        start_time = time.time()

        # 1. Gather context
        memories = await self.vector_memory.recall(prompt, top_k=3)
        context = self.context_service.get_current()
        history = await self.working_memory.get_history(session_id)

        # 2. Build system instruction with live context
        system_instruction = ORCHESTRATOR_SYSTEM_PROMPT.format(
            context=json.dumps(context, indent=2, default=str) if context else "No live context available.",
            memories=json.dumps(memories, indent=2) if memories else "No relevant memories."
        )

        # 3. Build conversation history
        gemini_history = self._build_gemini_history(history)

        # 4. Build tool declarations
        tool_decls = self._build_tool_declarations()

        # 5. Save user turn
        await self.working_memory.push_turn(session_id, "user", prompt)

        # 6. ReAct loop
        full_response = ""
        iteration = 0
        contents = gemini_history + [Content(role="user", parts=[Part(text=prompt)])]

        try:
            while iteration < self.max_iterations:
                iteration += 1

                from backend.utils.retry import with_retry
                response = await with_retry(
                    self.client.aio.models.generate_content,
                    model=self.model,
                    contents=contents,
                    config=GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=tool_decls,
                        temperature=0.7,
                    ),
                    fallback=None
                )

                if not response.candidates or not response.candidates[0].content.parts:
                    break

                parts = response.candidates[0].content.parts
                has_function_call = any(p.function_call for p in parts if p.function_call)

                # Add model response to conversation
                contents.append(response.candidates[0].content)

                function_responses = []

                for part in parts:
                    if part.function_call and part.function_call.name:
                        fc = part.function_call
                        tool_input = dict(fc.args) if fc.args else {}

                        # Emit action event
                        yield StepEvent(
                            type="action",
                            content=f"Using tool: {fc.name}",
                            tool_name=fc.name,
                            tool_input=tool_input,
                            iteration=iteration,
                        )

                        # Execute tool
                        tool_result = await self.tools.execute(fc.name, tool_input)

                        # Phase 7: Screen Perception Verification
                        if fc.name in ["launch_application", "click_element", "navigate_to_url"]:
                            await asyncio.sleep(1.5)  # Wait for UI to settle
                            try:
                                from backend.tools.computer_use import screen_perception
                                verification = await asyncio.wait_for(
                                    screen_perception.verify_action(
                                        f"The result of {fc.name} with input {tool_input}"
                                    ),
                                    timeout=8.0
                                )
                                tool_result["verified"] = verification.get("matches", False)
                                tool_result["screen_state"] = verification.get("actual_state", "")
                                
                                if not verification.get("matches", False):
                                    # Feed visual mismatch back to model
                                    tool_result["error"] = f"Visual verification failed. Screen shows: {verification.get('actual_state', '')} instead of expected state."
                            except asyncio.TimeoutError:
                                tool_result["verify_error"] = "Screen capture timed out"
                            except Exception as verify_err:
                                tool_result["verify_error"] = str(verify_err)


                        # Emit observation event
                        result_preview = json.dumps(tool_result, indent=2, default=str)
                        if len(result_preview) > 2000:
                            result_preview = result_preview[:2000] + "\n... (truncated)"

                        yield StepEvent(
                            type="observation",
                            content=result_preview,
                            tool_name=fc.name,
                            iteration=iteration,
                        )

                        function_responses.append(
                            Part.from_function_response(
                                name=fc.name,
                                response={"result": tool_result}
                            )
                        )

                    elif part.text:
                        full_response = part.text

                # If we had function calls, send responses back
                if function_responses:
                    contents.append(Content(role="user", parts=function_responses))
                    continue  # Loop back for model to process results

                # If no function calls and we have text, this is the final answer
                if full_response and not has_function_call:
                    yield StepEvent(
                        type="answer",
                        content=full_response,
                        iteration=iteration,
                    )
                    await self._save_interaction(session_id, prompt, full_response, route, iteration)
                    return

        except Exception as e:
            logger.error(f"ReAct loop error at iteration {iteration}: {e}", exc_info=True)
            yield StepEvent(
                type="error",
                content=f"I encountered an issue processing your request: {str(e)}",
                iteration=iteration,
            )
            return

        # Fallback
        if full_response:
            yield StepEvent(type="answer", content=full_response, iteration=iteration)
        else:
            yield StepEvent(
                type="answer",
                content="I was unable to complete this task within the step limit. Could you try rephrasing?",
                iteration=iteration,
            )
        await self._save_interaction(session_id, prompt, full_response, route, iteration)

    async def process(self, prompt: str, session_id: str = "default") -> AgentResult:
        """Non-streaming version — collects all steps and returns final result."""
        steps = []
        final_answer = ""
        start = time.time()

        async for event in self.process_stream(prompt, session_id):
            steps.append(event)
            if event.type == "answer":
                final_answer = event.content
            elif event.type == "error":
                final_answer = event.content

        latency = (time.time() - start) * 1000
        return AgentResult(
            agent="orchestrator",
            success=bool(final_answer),
            result=final_answer,
            latency_ms=round(latency, 2),
            steps=steps,
        )

    async def _save_interaction(
        self,
        session_id: str,
        prompt: str,
        response: str,
        route: Optional[RouteDecision],
        iterations: int,
    ) -> None:
        """Save completed interaction to both working and vector memory."""
        try:
            await self.working_memory.push_turn(session_id, "assistant", response)
            await self.vector_memory.save({
                "user": prompt,
                "assistant": response,
                "intent": route.intent.value if route else "conversation",
                "session_id": session_id,
                "iterations": iterations,
            })
        except Exception as e:
            logger.warning(f"Memory save error (non-fatal): {e}")

    def _build_gemini_history(self, history: List[Dict[str, Any]]) -> List[Content]:
        """Convert working memory history to Gemini Content format."""
        gemini_history = []
        for turn in history[-10:]:
            role = "user" if turn["role"] == "user" else "model"
            gemini_history.append(
                Content(role=role, parts=[Part(text=turn["content"])])
            )

        # Ensure alternating user/model pattern
        cleaned = []
        last_role = None
        for item in gemini_history:
            if item.role != last_role:
                cleaned.append(item)
                last_role = item.role

        return cleaned
