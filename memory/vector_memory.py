import json
import os
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_PATH = BASE_DIR / "memory" / "long_term.json"
VECTOR_DB_PATH = BASE_DIR / "memory" / "vector_store"
_lock = threading.Lock()

MAX_VALUE_LENGTH = 300


def _empty_memory() -> dict:
    return {"identity": {}, "preferences": {}, "relationships": {}, "notes": {}}


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()

    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()


def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False

    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            if isinstance(value, dict) and "value" in value:
                entry = {"value": _truncate_value(str(value["value"]))}
            else:
                entry = {"value": _truncate_value(str(value))}

            if key not in target or target[key] != entry:
                target[key] = entry
                changed = True

    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()

    memory = load_memory()

    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")

    return memory


def format_memory_for_prompt(memory: dict | None) -> str:
    if not memory:
        return ""

    lines = []

    identity = memory.get("identity", {})
    name = identity.get("name", {}).get("value")
    age = identity.get("age", {}).get("value")
    bday = identity.get("birthday", {}).get("value")
    city = identity.get("city", {}).get("value")
    if name:
        lines.append(f"Name: {name}")
    if age:
        lines.append(f"Age: {age}")
    if bday:
        lines.append(f"Birthday: {bday}")
    if city:
        lines.append(f"City: {city}")

    prefs = memory.get("preferences", {})
    for i, (key, entry) in enumerate(prefs.items()):
        if i >= 5:
            break
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    for i, (key, entry) in enumerate(rels.items()):
        if i >= 5:
            break
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.title()}: {val}")

    notes = memory.get("notes", {})
    for i, (key, entry) in enumerate(notes.items()):
        if i >= 5:
            break
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key}: {val}")

    if not lines:
        return ""

    result = "[USER MEMORY]\n" + "\n".join(f"- {line}" for line in lines)
    if len(result) > 800:
        result = result[:797] + "…"

    return result + "\n"


class VectorMemoryStore:
    """Vector-based semantic memory store using Google embeddings."""

    def __init__(self):
        self.embeddings_file = VECTOR_DB_PATH / "embeddings.json"
        self._ensure_storage()
        self._embeddings_cache = None
        self._client = None

    def _ensure_storage(self):
        VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        if not self.embeddings_file.exists():
            self._save_embeddings({})

    def _load_embeddings(self) -> dict:
        if self._embeddings_cache is not None:
            return self._embeddings_cache
        try:
            data = json.loads(self.embeddings_file.read_text(encoding="utf-8"))
            self._embeddings_cache = data
            return data
        except:
            return {}

    def _save_embeddings(self, data: dict):
        self.embeddings_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._embeddings_cache = data

    def _get_embedding_client(self):
        if self._client is None:
            from memory.config_manager import get_gemini_key
            import google.generativeai as genai

            genai.configure(api_key=get_gemini_key())
            self._client = genai
        return self._client

    def _generate_id(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def add_memory(
        self, content: str, memory_type: str = "general", metadata: dict = None
    ) -> str:
        """Add a memory with semantic embedding."""
        mem_id = self._generate_id(content)

        try:
            client = self._get_embedding_client()
            result = client.embed_content(
                model="gemini-embedding-001",
                content=content,
                task_type="semantic_similarity",
            )
            embedding = result.embedding
        except Exception as e:
            print(f"[VectorMemory] ⚠️ Embedding failed: {e}")
            embedding = []

        memories = self._load_embeddings()
        memories[mem_id] = {
            "content": content,
            "type": memory_type,
            "embedding": embedding,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

        self._save_embeddings(memories)
        print(f"[VectorMemory] ✅ Added: {mem_id}")
        return mem_id

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search for similar memories."""
        try:
            client = self._get_embedding_client()
            result = client.embed_content(
                model="gemini-embedding-001",
                content=query,
                task_type="semantic_similarity",
            )
            query_embedding = result.embedding
        except Exception as e:
            print(f"[VectorMemory] ⚠️ Query embedding failed: {e}")
            return []

        memories = self._load_embeddings()
        if not memories:
            return []

        similarities = []
        for mem_id, mem_data in memories.items():
            emb = mem_data.get("embedding", [])
            if not emb:
                continue

            sim = self._cosine_similarity(query_embedding, emb)
            similarities.append(
                {
                    "id": mem_id,
                    "content": mem_data["content"],
                    "type": mem_data.get("type", "general"),
                    "metadata": mem_data.get("metadata", {}),
                    "score": sim,
                    "created_at": mem_data.get("created_at", ""),
                }
            )

        similarities.sort(key=lambda x: x["score"], reverse=True)
        return similarities[:top_k]

    def _cosine_similarity(self, a: list, b: list) -> float:
        if not a or not b:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_all(self, memory_type: str = None) -> list[dict]:
        """Get all memories, optionally filtered by type."""
        memories = self._load_embeddings()
        results = []

        for mem_id, mem_data in memories.items():
            if memory_type and mem_data.get("type") != memory_type:
                continue
            results.append(
                {
                    "id": mem_id,
                    "content": mem_data["content"],
                    "type": mem_data.get("type", "general"),
                    "metadata": mem_data.get("metadata", {}),
                    "created_at": mem_data.get("created_at", ""),
                }
            )

        return results

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        memories = self._load_embeddings()
        if memory_id in memories:
            del memories[memory_id]
            self._save_embeddings(memories)
            return True
        return False


_vector_store: Optional[VectorMemoryStore] = None


def get_vector_store() -> VectorMemoryStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorMemoryStore()
    return _vector_store
