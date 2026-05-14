import json
import logging
from typing import Optional

from google import genai
from google.genai.types import GenerateContentConfig

from backend.agents.task_graph import TaskGraph
from backend.skills import Skill

logger = logging.getLogger("skills.extractor")

EXTRACTION_PROMPT = """
You are analyzing a completed AI agent task to extract a reusable skill.

Given:
- The original goal
- The task graph that was generated  
- Each sub-agent's actions and results
- The final output quality score

Extract a SKILL if:
1. The task succeeded (all tasks COMPLETE)
2. The quality score was >= 7.5
3. The pattern is generalizable (not too specific to one-time data)

A skill has:
- name: Short verb phrase (e.g. "research-and-summarize", "find-and-open-file")
- description: One sentence of what it does
- trigger_phrases: 3-5 example user inputs that would invoke this skill
- parameters: What varies between invocations (e.g. "topic", "filename", "app_name")
- task_template: The TaskGraph structure with parameters as placeholders
- avg_duration_s: How long it took
- success_rate: Start at 1.0, decay on failures

Return null if the task doesn't warrant skill extraction.
Return JSON matching this schema:
{
    "name": "string",
    "description": "string",
    "trigger_phrases": ["string"],
    "parameters": ["string"],
    "task_template": {"tasks": [{"id": "string", "goal": "string", "agent_profile": "string", "dependencies": ["string"]}]}
}
"""


class SkillExtractor:
    def __init__(self):
        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def try_extract(
        self,
        goal: str,
        graph: TaskGraph,
        quality_score: float,
    ) -> Optional[Skill]:

        if quality_score < 7.5:
            return None

        task_summary = [
            {
                "id": t.id, "goal": t.goal, "profile": t.agent_profile,
                "tools_used": t.result.get("tools_used", []) if t.result else [],
            }
            for t in graph.tasks.values()
        ]

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[
                    EXTRACTION_PROMPT,
                    f"Goal: {goal}\nTasks: {json.dumps(task_summary)}\nScore: {quality_score}",
                ],
                config=GenerateContentConfig(
                    temperature=0.2,
                ),
            )

            if not response or not response.text:
                return None

            raw = response.text.strip()
            if raw.startswith("```json"): raw = raw[7:]
            elif raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            data = json.loads(raw.strip())
            
            if not data or "name" not in data:
                return None

            return Skill(
                name=data["name"],
                description=data["description"],
                trigger_phrases=data.get("trigger_phrases", []),
                parameters=data.get("parameters", []),
                task_template=data.get("task_template", {"tasks": []}),
            )
        except Exception as e:
            logger.warning(f"Skill extraction failed: {e}")
            return None
