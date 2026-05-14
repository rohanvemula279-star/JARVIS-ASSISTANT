"""
LLM-Based Intent Router
Replaces keyword-dict routing with Gemini structured output classification.
Uses the new google-genai SDK.
"""

import json
import logging
from typing import Optional, List, Dict

from google import genai
from google.genai.types import GenerateContentConfig

from backend.config.settings import get_settings
from backend.agents import Intent, RouteDecision

logger = logging.getLogger("agents.router")

ROUTER_SYSTEM_PROMPT = """
You are a precise intent classification system for a desktop AI assistant named JARVIS.

Your job is to analyze user input and return a JSON object with:
- intent: one of the defined categories
- confidence: 0.0-1.0 how certain you are
- extracted_entities: key entities from the request (app names, URLs, file paths, search queries, etc.)
- requires_planning: true if this needs multiple sequential steps
- reasoning: brief one-sentence explanation of your classification

Intent categories:
- launch_app: Opening, starting, or closing desktop applications (e.g., "open Chrome", "launch VS Code")
- web_search: Searching for information online (e.g., "search for latest AI news", "look up Python docs")
- file_operation: Creating, reading, moving, or deleting files/folders
- browser_automation: Interacting with web pages (filling forms, clicking buttons, scraping)
- system_query: Questions about system status, running processes, hardware (e.g., "how much RAM is free?")
- memory_recall: Asking about past conversations or remembered information (e.g., "what did we talk about yesterday?")
- conversation: General chat, questions, explanations, creative tasks (no tool needed)
- code_execution: Running scripts, code analysis, or programming tasks
- schedule_task: Setting reminders, calendar events, scheduling
- multi_step: Complex tasks requiring multiple different tool types (e.g., "find info and save to a file")

CRITICAL RULES:
1. If the sentence contains an action verb but is clearly conversational (e.g., "How do I open a jar?"), classify as 'conversation', NOT 'launch_app'.
2. If a task needs 2+ different tool types, classify as 'multi_step' with requires_planning=true.
3. Only set confidence > 0.9 if you are absolutely certain.
4. Use reasoning to justify boundary cases.

Return ONLY valid JSON matching this exact schema:
{
    "intent": "<intent_category>",
    "confidence": <float>,
    "extracted_entities": {},
    "requires_planning": <boolean>,
    "reasoning": "<string>"
}
"""


class IntentRouter:
    """LLM-powered intent classification using Gemini structured output."""

    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for the IntentRouter")

        from google.api_core import client_options
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1"}
        )
        self.model = settings.gemini_model

    async def classify(
        self,
        prompt: str,
        conversation_context: Optional[List[Dict]] = None
    ) -> RouteDecision:
        """Classify user intent using Gemini JSON mode."""
        context_str = ""
        if conversation_context:
            recent = conversation_context[-3:]
            context_str = f"\nRecent conversation context: {json.dumps(recent)}\n"

        try:
            from backend.utils.retry import with_retry
            fallback_decision = RouteDecision(
                intent=Intent.CONVERSATION,
                confidence=0.5,
                reasoning="Quota exceeded fallback"
            )

            response = await with_retry(
                self.client.aio.models.generate_content,
                model=self.model,
                contents=f"{context_str}User input: {prompt}",
                config=GenerateContentConfig(
                    system_instruction=ROUTER_SYSTEM_PROMPT,
                    temperature=0.1,
                ),
                fallback=fallback_decision
            )

            if isinstance(response, RouteDecision):
                return response

            raw = response.text.strip()
            if raw.startswith("```json"): raw = raw[7:]
            elif raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            data = json.loads(raw.strip())

            return RouteDecision(
                intent=Intent(data.get("intent", "conversation")),
                confidence=float(data.get("confidence", 0.5)),
                extracted_entities=data.get("extracted_entities", {}),
                requires_planning=bool(data.get("requires_planning", False)),
                reasoning=data.get("reasoning", "")
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Router JSON parse error: {e}")
            return RouteDecision(
                intent=Intent.CONVERSATION,
                confidence=0.3,
                reasoning="JSON parse failure, defaulting to conversation"
            )
        except Exception as e:
            logger.error(f"Router classification error: {e}")
            return RouteDecision(
                intent=Intent.CONVERSATION,
                confidence=0.3,
                reasoning=f"Classification error: {str(e)}"
            )


# Global router instance
_router: Optional[IntentRouter] = None


def get_router() -> IntentRouter:
    """Get or create the global router instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
