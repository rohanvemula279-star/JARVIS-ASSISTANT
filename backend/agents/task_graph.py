from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"  # Waiting on dependency

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    agent_profile: str = "DEFAULT"  # Which specialist handles this
    tool_hint: Optional[str] = None  # Suggested tool
    dependencies: list[str] = field(default_factory=list)  # Task IDs
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    
    def is_ready(self, completed_ids: set[str]) -> bool:
        return all(dep in completed_ids for dep in self.dependencies)

@dataclass
class TaskGraph:
    root_goal: str = ""
    tasks: dict[str, Task] = field(default_factory=dict)
    session_id: str = ""
    
    def add(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task
    
    def get_ready_tasks(self) -> list[Task]:
        completed = {tid for tid, t in self.tasks.items() 
                     if t.status == TaskStatus.COMPLETE}
        return [t for t in self.tasks.values() 
                if t.status == TaskStatus.PENDING and t.is_ready(completed)]
    
    def is_complete(self) -> bool:
        return all(t.status == TaskStatus.COMPLETE for t in self.tasks.values())
    
    def summary(self) -> dict:
        return {
            "total": len(self.tasks),
            "complete": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETE),
            "failed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
            "pending": sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING),
        }

    def to_dict(self) -> dict:
        """Serialize TaskGraph to dictionary for storage."""
        return {
            "root_goal": self.root_goal,
            "session_id": self.session_id,
            "tasks": [
                {
                    "id": t.id,
                    "goal": t.goal,
                    "agent_profile": t.agent_profile,
                    "tool_hint": t.tool_hint,
                    "dependencies": t.dependencies,
                    "status": t.status.value if isinstance(t.status, TaskStatus) else t.status,
                    "result": t.result,
                    "error": t.error,
                }
                for t in self.tasks.values()
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskGraph":
        """Deserialize TaskGraph from dictionary."""
        graph = cls(
            root_goal=data.get("root_goal", ""),
            session_id=data.get("session_id", "")
        )
        for t_data in data.get("tasks", []):
            task = Task(
                id=t_data.get("id", ""),
                goal=t_data.get("goal", ""),
                agent_profile=t_data.get("agent_profile", "DEFAULT"),
                tool_hint=t_data.get("tool_hint"),
                dependencies=t_data.get("dependencies", []),
                status=TaskStatus(t_data.get("status", "pending")),
                result=t_data.get("result"),
                error=t_data.get("error"),
            )
            graph.add(task)
        return graph
