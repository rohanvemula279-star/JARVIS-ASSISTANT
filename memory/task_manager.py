import json
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass, asdict
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
TASKS_PATH = BASE_DIR / "memory" / "tasks.json"

TaskStatus = Literal["pending", "in_progress", "completed", "overdue", "postponed"]
TaskCategory = Literal[
    "study", "startup", "money", "personal", "health", "career", "hackathon", "general"
]
TaskPriority = Literal["low", "normal", "high", "urgent"]


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    category: TaskCategory
    deadline: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    tags: list[str]
    subtasks: list[dict]
    linked_notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class TaskManager:
    """Task management with categories, deadlines, and priority tracking."""

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks_cache = None

    def _load_tasks(self) -> dict:
        if self._tasks_cache is not None:
            return self._tasks_cache
        try:
            if TASKS_PATH.exists():
                data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
                self._tasks_cache = data
                return data
        except:
            pass
        return {"tasks": {}, "categories": [], "tags": []}

    def _save_tasks(self, data: dict):
        TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        TASKS_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._tasks_cache = data

    def _generate_id(self) -> str:
        import hashlib

        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:12]

    def create_task(
        self,
        title: str,
        description: str = "",
        category: TaskCategory = "general",
        priority: TaskPriority = "normal",
        deadline: str = None,
        tags: list[str] = None,
    ) -> Task:
        """Create a new task."""
        with self._lock:
            task_id = self._generate_id()
            now = datetime.now().isoformat()

            task = Task(
                id=task_id,
                title=title,
                description=description,
                status="pending",
                priority=priority,
                category=category,
                deadline=deadline,
                created_at=now,
                updated_at=now,
                completed_at=None,
                tags=tags or [],
                subtasks=[],
                linked_notes=[],
            )

            data = self._load_tasks()
            data["tasks"][task_id] = task.to_dict()
            self._save_tasks(data)

            self._update_categories_and_tags(category, tags or [])

            print(f"[TaskManager] ✅ Created task: {task_id}")
            return task

    def _update_categories_and_tags(self, category: TaskCategory, tags: list[str]):
        """Track all categories and tags."""
        data = self._load_tasks()
        cats = set(data.get("categories", []))
        cats.add(category)
        data["categories"] = sorted(cats)

        tg = set(data.get("tags", []))
        for t in tags:
            tg.add(t)
        data["tags"] = sorted(tg)

        self._save_tasks(data)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        data = self._load_tasks()
        if task_id in data["tasks"]:
            return Task(**data["tasks"][task_id])
        return None

    def update_task(
        self,
        task_id: str,
        title: str = None,
        description: str = None,
        status: TaskStatus = None,
        priority: TaskPriority = None,
        category: TaskCategory = None,
        deadline: str = None,
        tags: list[str] = None,
        subtasks: list[dict] = None,
    ) -> Optional[Task]:
        """Update an existing task."""
        with self._lock:
            data = self._load_tasks()
            if task_id not in data["tasks"]:
                return None

            task_data = data["tasks"][task_id]

            if title is not None:
                task_data["title"] = title
            if description is not None:
                task_data["description"] = description
            if status is not None:
                task_data["status"] = status
                if status == "completed":
                    task_data["completed_at"] = datetime.now().isoformat()
            if priority is not None:
                task_data["priority"] = priority
            if category is not None:
                task_data["category"] = category
            if deadline is not None:
                task_data["deadline"] = deadline
            if tags is not None:
                task_data["tags"] = tags
            if subtasks is not None:
                task_data["subtasks"] = subtasks

            task_data["updated_at"] = datetime.now().isoformat()

            data["tasks"][task_id] = task_data
            self._save_tasks(data)

            print(f"[TaskManager] ✅ Updated task: {task_id}")
            return Task(**task_data)

    def complete_task(self, task_id: str) -> Optional[Task]:
        """Mark a task as completed."""
        return self.update_task(task_id, status="completed")

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with self._lock:
            data = self._load_tasks()
            if task_id in data["tasks"]:
                del data["tasks"][task_id]
                self._save_tasks(data)
                return True
            return False

    def get_tasks(
        self,
        status: TaskStatus = None,
        category: TaskCategory = None,
        priority: TaskPriority = None,
        tags: list[str] = None,
        include_overdue: bool = True,
    ) -> list[Task]:
        """Get tasks with optional filters."""
        data = self._load_tasks()
        results = []
        now = datetime.now()

        for task_data in data["tasks"].values():
            if status and task_data["status"] != status:
                continue
            if category and task_data["category"] != category:
                continue
            if priority and task_data["priority"] != priority:
                continue
            if tags:
                task_tags = set(task_data.get("tags", []))
                if not task_tags.intersection(set(tags)):
                    continue

            if include_overdue and task_data["deadline"]:
                try:
                    deadline = datetime.fromisoformat(task_data["deadline"])
                    if deadline < now and task_data["status"] == "pending":
                        task_data["status"] = "overdue"
                except:
                    pass

            results.append(Task(**task_data))

        return sorted(
            results,
            key=lambda x: (
                {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(x.priority, 4),
                x.deadline or "9999",
            ),
        )

    def get_pending_tasks(self, category: TaskCategory = None) -> list[Task]:
        """Get pending tasks, optionally by category."""
        return self.get_tasks(status="pending", category=category)

    def get_overdue_tasks(self) -> list[Task]:
        """Get all overdue tasks."""
        data = self._load_tasks()
        results = []
        now = datetime.now()

        for task_data in data["tasks"].values():
            if task_data["status"] in ("completed", "postponed"):
                continue
            if task_data["deadline"]:
                try:
                    deadline = datetime.fromisoformat(task_data["deadline"])
                    if deadline < now:
                        results.append(Task(**task_data))
                except:
                    pass
            elif task_data["status"] == "overdue":
                results.append(Task(**task_data))

        return sorted(results, key=lambda x: x.deadline or "")

    def get_today_tasks(self) -> list[Task]:
        """Get tasks due today."""
        data = self._load_tasks()
        results = []
        today = datetime.now().date()

        for task_data in data["tasks"].values():
            if task_data["status"] in ("completed", "postponed"):
                continue
            if task_data["deadline"]:
                try:
                    deadline = datetime.fromisoformat(task_data["deadline"]).date()
                    if deadline == today:
                        results.append(Task(**task_data))
                except:
                    pass

        return sorted(results, key=lambda x: x.priority)

    def get_week_tasks(self) -> list[Task]:
        """Get tasks due this week."""
        data = self._load_tasks()
        results = []
        now = datetime.now()
        week_end = now + timedelta(days=7)

        for task_data in data["tasks"].values():
            if task_data["status"] in ("completed", "postponed"):
                continue
            if task_data["deadline"]:
                try:
                    deadline = datetime.fromisoformat(task_data["deadline"])
                    if now <= deadline <= week_end:
                        results.append(Task(**task_data))
                except:
                    pass

        return sorted(results, key=lambda x: x.deadline or "")

    def add_subtask(self, task_id: str, title: str, completed: bool = False) -> bool:
        """Add a subtask to a task."""
        data = self._load_tasks()
        if task_id not in data["tasks"]:
            return False

        subtasks = data["tasks"][task_id].get("subtasks", [])
        subtasks.append(
            {"id": self._generate_id(), "title": title, "completed": completed}
        )

        data["tasks"][task_id]["subtasks"] = subtasks
        data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
        self._save_tasks(data)
        return True

    def toggle_subtask(self, task_id: str, subtask_id: str) -> bool:
        """Toggle subtask completion."""
        data = self._load_tasks()
        if task_id not in data["tasks"]:
            return False

        subtasks = data["tasks"][task_id].get("subtasks", [])
        for st in subtasks:
            if st["id"] == subtask_id:
                st["completed"] = not st["completed"]
                data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
                self._save_tasks(data)
                return True
        return False

    def get_categories(self) -> list[str]:
        """Get all task categories."""
        data = self._load_tasks()
        return data.get("categories", [])

    def get_tags(self) -> list[str]:
        """Get all task tags."""
        data = self._load_tasks()
        return data.get("tags", [])

    def get_stats(self) -> dict:
        """Get task statistics."""
        data = self._load_tasks()
        tasks = data.get("tasks", {})

        total = len(tasks)
        completed = sum(1 for t in tasks.values() if t["status"] == "completed")
        pending = sum(1 for t in tasks.values() if t["status"] == "pending")
        overdue = 0

        now = datetime.now()
        for t in tasks.values():
            if t["status"] == "pending" and t.get("deadline"):
                try:
                    if datetime.fromisoformat(t["deadline"]) < now:
                        overdue += 1
                except:
                    pass

        by_category = {}
        for t in tasks.values():
            cat = t.get("category", "general")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "by_category": by_category,
        }

    def extract_tasks_from_text(self, text: str) -> list[dict]:
        """Extract potential tasks from text using LLM."""
        from memory.config_manager import get_gemini_key
        import google.generativeai as genai

        genai.configure(api_key=get_gemini_key())
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        prompt = f"""Extract tasks from this text. Return ONLY valid JSON array.
For each task, extract: title, category (study/startup/money/personal/health/career/hackathon/general), priority (low/normal/high/urgent), deadline (ISO date if mentioned, else null).

Text: {text[:1000]}

Return format:
[{{"title": "...", "category": "study", "priority": "normal", "deadline": null}}]"""

        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            raw = raw.strip("```json").strip("```").strip()
            return json.loads(raw)
        except:
            return []


_tm: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    global _tm
    if _tm is None:
        _tm = TaskManager()
    return _tm
