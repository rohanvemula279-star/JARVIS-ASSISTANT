import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator, Optional

from backend.memory.chroma_store import VectorMemory
from backend.skills import Skill

logger = logging.getLogger("skills.registry")

SKILLS_FILE = Path(__file__).parent.parent.parent / "data" / "learned_skills.json"


class SkillRegistry:
    def __init__(self, vector_memory: VectorMemory):
        self.memory = vector_memory
        self._skills: dict[str, Skill] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        if SKILLS_FILE.exists():
            try:
                with open(SKILLS_FILE) as f:
                    data = json.load(f)
                for item in data:
                    skill = Skill.from_dict(item)
                    self._skills[skill.name] = skill
                logger.info(f"Loaded {len(self._skills)} learned skills from disk")
            except Exception as e:
                logger.warning(f"Failed to load skills from disk: {e}")

    def _save_to_disk(self):
        SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [s.to_dict() for s in self._skills.values()]
            with open(SKILLS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save skills to disk: {e}")

    async def register(self, skill: Skill):
        existing = self._skills.get(skill.name)
        if existing:
            skill.times_used = existing.times_used
            skill.success_rate = existing.success_rate
            skill.avg_duration_s = existing.avg_duration_s

        self._skills[skill.name] = skill

        for phrase in skill.trigger_phrases:
            try:
                await self.memory.save({
                    "user": phrase,
                    "assistant": f"SKILL:{skill.name}",
                    "intent": "skill_trigger",
                    "metadata": {"skill_name": skill.name},
                })
            except Exception as e:
                logger.warning(f"Failed to index skill trigger phrase: {e}")

        self._save_to_disk()
        logger.info(f"Registered skill: {skill.name}")

    async def match(self, prompt: str, threshold: float = 0.75) -> Optional[Skill]:
        try:
            results = await self.memory.recall(
                query=prompt,
                top_k=3,
                intent_filter="skill_trigger",
            )
        except Exception:
            results = []

        if not results:
            clean_results = []
            query_lower = prompt.lower()
            for skill in self._skills.values():
                for phrase in skill.trigger_phrases:
                    if any(word in query_lower for word in phrase.lower().split()):
                        clean_results.append({
                            "content": f"SKILL:{skill.name}",
                            "relevance": 0.8,
                        })
                        break
            results = clean_results

        if not results:
            return None

        best = results[0]
        relevance = best.get("relevance", 0)
        if relevance < threshold and not any(
            w in prompt.lower() for s in self._skills.values()
            for w in s.name.replace("-", " ").split()
        ):
            return None

        matched_response = best.get("content", "").split("SKILL:")[-1].strip()
        skill = self._skills.get(matched_response)
        if skill and skill.success_rate > 0.7:
            return skill
        return None

    async def execute_skill(
        self,
        skill: Skill,
        prompt: str,
        coordinator,
        session_id: str,
    ):
        from backend.utils.retry import with_retry
        from google import genai
        from google.genai.types import GenerateContentConfig

        settings_type = __import__("backend.config.settings", fromlist=["get_settings"])
        settings = settings_type.get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        model = "gemini-2.0-flash"

        params_prompt = (
            f"Extract these parameters from the user input: {skill.parameters}\n"
            f"User said: {prompt}\n"
            f"Return JSON with parameter names as keys."
        )

        try:
            response = await with_retry(
                client.aio.models.generate_content,
                model=model,
                contents=params_prompt,
                config=GenerateContentConfig(
                    temperature=0.1,
                ),
                fallback=None,
            )
            if response and response.text:
                raw = response.text.strip()
                if raw.startswith("```json"): raw = raw[7:]
                elif raw.startswith("```"): raw = raw[3:]
                if raw.endswith("```"): raw = raw[:-3]
                params = json.loads(raw.strip())
            else:
                params = {}
        except Exception as e:
            logger.warning(f"Skill parameter extraction failed: {e}")
            params = {}

        graph = skill.instantiate(params)

        async for event in coordinator.execute_plan(graph, session_id):
            yield event

        skill.times_used += 1
        self._save_to_disk()

    def list_skills(self) -> list[dict]:
        return [s.to_dict() for s in self._skills.values()]

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def delete_skill(self, name: str) -> bool:
        if name in self._skills:
            del self._skills[name]
            self._save_to_disk()
            return True
        return False
