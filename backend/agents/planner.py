import json
from google import genai
from google.genai.types import GenerateContentConfig
from backend.agents.task_graph import Task, TaskGraph

PLANNER_PROMPT = """
You are a task decomposition expert. Given a complex goal, break it into 
atomic subtasks that can be executed by an AI agent.

For each subtask, specify:
- id: short unique string (e.g. "t1", "t2")
- goal: what this subtask accomplishes (be specific)
- agent_profile: one of RESEARCHER, EXECUTOR, ANALYST, CODER, DEFAULT
- dependencies: list of task IDs that must complete before this one

Rules:
- Maximum 8 subtasks for any goal
- Each subtask must be completable with a single tool or a 3-step ReAct loop
- Identify which tasks can run in PARALLEL (no shared dependencies)
- The final task should aggregate all results

Return ONLY valid JSON: {"tasks": [...], "can_parallelize": bool}
"""

class TaskPlanner:
    def __init__(self):
        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"
        
    async def decompose(self, goal: str, context: dict) -> TaskGraph:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[PLANNER_PROMPT, f"Goal: {goal}\nContext: {context}"],
            config=GenerateContentConfig()
        )
        
        try:
            raw = response.text.strip()
            if raw.startswith("```json"): raw = raw[7:]
            elif raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            data = json.loads(raw.strip())
        except:
            data = {"tasks": []}
            
        graph = TaskGraph(root_goal=goal)
        for t in data.get("tasks", []):
            graph.add(Task(
                id=t.get("id", ""), 
                goal=t.get("goal", ""),
                agent_profile=t.get("agent_profile", "DEFAULT"),
                dependencies=t.get("dependencies", [])
            ))
        return graph
