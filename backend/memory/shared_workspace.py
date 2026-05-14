from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class WorkspaceEntry:
    key: str
    value: Any
    written_by: str
    written_at: str
    read_by: list[str] = field(default_factory=list)


class SharedWorkspace:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._store: dict[str, WorkspaceEntry] = {}

    def write(self, key: str, value: Any, agent_name: str):
        self._store[key] = WorkspaceEntry(
            key=key, value=value, written_by=agent_name,
            written_at=datetime.utcnow().isoformat()
        )

    def read(self, key: str, reader_agent: str) -> Any:
        if key in self._store:
            self._store[key].read_by.append(reader_agent)
            return self._store[key].value
        return None

    def read_all(self) -> dict:
        return {k: v.value for k, v in self._store.items()}

    def get_provenance(self) -> list[dict]:
        return [
            {"key": e.key, "agent": e.written_by,
             "at": e.written_at, "read_by": e.read_by}
            for e in self._store.values()
        ]
