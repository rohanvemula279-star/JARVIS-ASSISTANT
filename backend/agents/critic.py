import json
from dataclasses import dataclass
from google import genai
from google.genai.types import GenerateContentConfig
from backend.agents import StepEvent

CRITIC_PROMPT = """
You are a strict quality evaluator for an AI assistant.

Given the original request and the assistant's response, score on:
1. COMPLETENESS (0-10): Did it fully address the request?
2. ACCURACY (0-10): Is the information correct and verifiable?
3. ACTIONABILITY (0-10): Can the user act on this immediately?
4. EFFICIENCY (0-10): Did it use the minimum steps needed?

Then decide:
- PASS: overall score >= 7.0, return to user
- RETRY_SAME: score 5-7, try again with same approach  
- RETRY_DIFFERENT: score < 5, fundamental strategy problem

Return JSON: {
  "scores": {"completeness": 0, "accuracy": 0, "actionability": 0, "efficiency": 0},
  "overall": 0.0,
  "decision": "PASS",
  "failure_reason": "",
  "retry_instruction": ""
}
"""

@dataclass
class CriticResult:
    scores: dict
    overall: float
    decision: str
    failure_reason: str = ""
    retry_instruction: str = ""

class CriticAgent:
    PASS_THRESHOLD = 7.0
    MAX_RETRIES = 2
    
    def __init__(self):
        from backend.config.settings import get_settings
        settings = get_settings()
        from google.api_core import client_options
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1"}
        )
        self.model = settings.gemini_model
    
    async def evaluate(self, request: str, response: str, 
                       tool_calls: list) -> CriticResult:
        from backend.utils.retry import with_retry
        res = await with_retry(
            self.client.aio.models.generate_content,
            model=self.model,
            contents=[CRITIC_PROMPT, f"Request: {request}\nResponse: {response}\nTools used: {tool_calls}"],
            config=GenerateContentConfig(),
            fallback=CriticResult(scores={}, overall=7.5, decision="PASS")
        )
        if isinstance(res, CriticResult):
            return res
        try:
            raw = res.text.strip()
            if raw.startswith("```json"): raw = raw[7:]
            elif raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            data = json.loads(raw.strip())
            return CriticResult(**data)
        except:
            return CriticResult(scores={}, overall=10.0, decision="PASS")
    
    async def evaluate_and_retry(
        self,
        request: str,
        generator_fn,  # Callable[[str], AsyncGenerator[StepEvent, None]]
        session_id: str
    ):
        from backend.utils.retry import with_retry
        retry_instruction = ""

        async def consume_generator(instruction):
            events = []
            ans = ""
            async for ev in generator_fn(additional_instruction=instruction):
                events.append(ev)
                if ev.type == "answer":
                    ans = ev.content
            t_calls = [e.tool_name for e in events if e.type == "action"]
            return {"answer": ans, "tool_calls": t_calls, "events": events}

        for attempt in range(self.MAX_RETRIES + 1):
            result = await with_retry(
                consume_generator,
                instruction=retry_instruction,
                fallback={"answer": "Unable to generate response at this time.", "tool_calls": []}
            )

            if result.get("answer") == "Unable to generate response at this time.":
                yield StepEvent(type="answer", content=result["answer"])
                return

            critique = await with_retry(
                self.evaluate,
                request, result["answer"], result.get("tool_calls", []),
                fallback=CriticResult(decision="PASS", overall=7.5, scores={}, failure_reason="", retry_instruction="")
            )

            yield StepEvent(
                type="critique",
                content=f"Quality score: {critique.overall:.1f}/10 — {critique.decision}",
                iteration=attempt
            )

            if critique.decision == "PASS" or attempt == self.MAX_RETRIES:
                yield StepEvent(type="answer", content=result["answer"])
                return

            retry_instruction = critique.retry_instruction
            yield StepEvent(
                type="retry",
                content=f"Retrying: {critique.failure_reason}"
            )
