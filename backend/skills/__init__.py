from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Skill:
    name: str
    description: str
    trigger_phrases: list[str]
    parameters: list[str]
    task_template: dict
    avg_duration_s: float = 0.0
    success_rate: float = 1.0
    times_used: int = 0

    def instantiate(self, params: dict) -> Any:
        from backend.agents.task_graph import TaskGraph, Task
        graph = TaskGraph(root_goal=self.description)
        for t in self.task_template.get("tasks", []):
            goal = t["goal"]
            for param_name, param_value in params.items():
                goal = goal.replace(f"{{{param_name}}}", str(param_value))
            graph.add(Task(
                id=t["id"],
                goal=goal,
                agent_profile=t.get("agent_profile", "DEFAULT"),
                dependencies=t.get("dependencies", []),
            ))
        return graph

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "trigger_phrases": self.trigger_phrases,
            "parameters": self.parameters,
            "task_template": self.task_template,
            "avg_duration_s": self.avg_duration_s,
            "success_rate": self.success_rate,
            "times_used": self.times_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        return cls(**data)
