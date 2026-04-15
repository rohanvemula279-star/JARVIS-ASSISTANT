import json
import os
import uuid
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
NOTES_PATH = BASE_DIR / "memory" / "notes"


@dataclass
class Note:
    id: str
    title: str
    content: str
    tags: list[str]
    folder: str
    created_at: str
    updated_at: str
    linked_notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class KnowledgeBase:
    """Personal knowledge base with semantic search."""

    def __init__(self):
        self._lock = threading.Lock()
        self._index_file = NOTES_PATH / "index.json"
        self._embeddings_file = NOTES_PATH / "embeddings.json"
        self._ensure_storage()
        self._client = None
        self._index_cache = None

    def _ensure_storage(self):
        NOTES_PATH.mkdir(parents=True, exist_ok=True)
        if not self._index_file.exists():
            self._save_index({})
        if not self._embeddings_file.exists():
            self._save_embeddings({})

    def _load_index(self) -> dict:
        if self._index_cache is not None:
            return self._index_cache
        try:
            data = json.loads(self._index_file.read_text(encoding="utf-8"))
            self._index_cache = data
            return data
        except:
            return {}

    def _save_index(self, data: dict):
        self._index_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._index_cache = data

    def _load_embeddings(self) -> dict:
        try:
            return json.loads(self._embeddings_file.read_text(encoding="utf-8"))
        except:
            return {}

    def _save_embeddings(self, data: dict):
        self._embeddings_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _get_embedding_client(self):
        if self._client is None:
            from memory.config_manager import get_gemini_key
            import google.generativeai as genai

            genai.configure(api_key=get_gemini_key())
            self._client = genai
        return self._client

    def _generate_id(self) -> str:
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:12]

    def create_note(
        self, title: str, content: str, tags: list[str] = None, folder: str = "general"
    ) -> Note:
        """Create a new note."""
        with self._lock:
            note_id = self._generate_id()
            now = datetime.now().isoformat()

            note = Note(
                id=note_id,
                title=title,
                content=content,
                tags=tags or [],
                folder=folder,
                created_at=now,
                updated_at=now,
                linked_notes=[],
            )

            index = self._load_index()
            index[note_id] = note.to_dict()
            self._save_index(index)

            self._index_and_link(note_id, title, content, tags or [])

            print(f"[KnowledgeBase] ✅ Created note: {note_id}")
            return note

    def _index_and_link(self, note_id: str, title: str, content: str, tags: list[str]):
        """Index note for semantic search and auto-link."""
        try:
            client = self._get_embedding_client()
            text_to_embed = f"{title}. {content}"
            result = client.embed_content(
                model="gemini-embedding-001",
                content=text_to_embed,
                task_type="semantic_similarity",
            )
            embedding = result.embedding
        except Exception as e:
            print(f"[KnowledgeBase] ⚠️ Embedding failed: {e}")
            embedding = []

        embeddings = self._load_embeddings()
        embeddings[note_id] = {
            "title": title,
            "content": content,
            "tags": tags,
            "embedding": embedding,
        }
        self._save_embeddings(embeddings)

        self._auto_link_notes(note_id, title, content, tags)

    def _auto_link_notes(self, note_id: str, title: str, content: str, tags: list[str]):
        """Automatically link related notes."""
        embeddings = self._load_embeddings()
        if not embeddings:
            return

        text_to_embed = f"{title}. {content}"
        try:
            client = self._get_embedding_client()
            result = client.embed_content(
                model="gemini-embedding-001",
                content=text_to_embed,
                task_type="semantic_similarity",
            )
            query_embedding = result.embedding
        except:
            return

        similarities = []
        for nid, emb_data in embeddings.items():
            if nid == note_id:
                continue
            emb = emb_data.get("embedding", [])
            if not emb:
                continue
            sim = self._cosine_similarity(query_embedding, emb)
            if sim > 0.7:
                similarities.append((nid, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        linked = [nid for nid, _ in similarities[:5]]

        index = self._load_index()
        if note_id in index:
            index[note_id]["linked_notes"] = linked
            self._save_index(index)

    def _cosine_similarity(self, a: list, b: list) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_note(self, note_id: str) -> Optional[Note]:
        """Get a note by ID."""
        index = self._load_index()
        if note_id in index:
            return Note(**index[note_id])
        return None

    def update_note(
        self,
        note_id: str,
        title: str = None,
        content: str = None,
        tags: list[str] = None,
        folder: str = None,
    ) -> Optional[Note]:
        """Update an existing note."""
        with self._lock:
            index = self._load_index()
            if note_id not in index:
                return None

            note_data = index[note_id]
            if title is not None:
                note_data["title"] = title
            if content is not None:
                note_data["content"] = content
            if tags is not None:
                note_data["tags"] = tags
            if folder is not None:
                note_data["folder"] = folder

            note_data["updated_at"] = datetime.now().isoformat()

            index[note_id] = note_data
            self._save_index(index)

            self._index_and_link(
                note_id, note_data["title"], note_data["content"], note_data["tags"]
            )

            print(f"[KnowledgeBase] ✅ Updated note: {note_id}")
            return Note(**note_data)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        with self._lock:
            index = self._load_index()
            if note_id in index:
                del index[note_id]
                self._save_index(index)

                embeddings = self._load_embeddings()
                if note_id in embeddings:
                    del embeddings[note_id]
                    self._save_embeddings(embeddings)

                return True
            return False

    def search(
        self, query: str, top_k: int = 5, folder: str = None, tags: list[str] = None
    ) -> list[dict]:
        """Semantic search for notes."""
        try:
            client = self._get_embedding_client()
            result = client.embed_content(
                model="gemini-embedding-001",
                content=query,
                task_type="semantic_similarity",
            )
            query_embedding = result.embedding
        except Exception as e:
            print(f"[KnowledgeBase] ⚠️ Query embedding failed: {e}")
            return []

        index = self._load_index()
        embeddings = self._load_embeddings()

        results = []
        for note_id, note_data in index.items():
            if folder and note_data.get("folder") != folder:
                continue
            if tags:
                note_tags = set(note_data.get("tags", []))
                if not note_tags.intersection(set(tags)):
                    continue

            emb_data = embeddings.get(note_id, {})
            emb = emb_data.get("embedding", [])
            if not emb:
                continue

            sim = self._cosine_similarity(query_embedding, emb)
            results.append(
                {
                    "id": note_id,
                    "title": note_data["title"],
                    "content": note_data["content"],
                    "tags": note_data.get("tags", []),
                    "folder": note_data.get("folder", "general"),
                    "score": sim,
                    "updated_at": note_data.get("updated_at", ""),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_all_notes(self, folder: str = None, tags: list[str] = None) -> list[Note]:
        """Get all notes, optionally filtered."""
        index = self._load_index()
        results = []

        for note_data in index.values():
            if folder and note_data.get("folder") != folder:
                continue
            if tags:
                note_tags = set(note_data.get("tags", []))
                if not note_tags.intersection(set(tags)):
                    continue
            results.append(Note(**note_data))

        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    def get_folders(self) -> list[str]:
        """Get all unique folders."""
        index = self._load_index()
        folders = set()
        for note_data in index.values():
            if note_data.get("folder"):
                folders.add(note_data["folder"])
        return sorted(folders)

    def get_tags(self) -> list[str]:
        """Get all unique tags."""
        index = self._load_index()
        tags = set()
        for note_data in index.values():
            for tag in note_data.get("tags", []):
                tags.add(tag)
        return sorted(tags)

    def link_notes(self, note_id: str, linked_note_id: str) -> bool:
        """Manually link two notes."""
        index = self._load_index()
        if note_id not in index or linked_note_id not in index:
            return False

        linked = index[note_id].get("linked_notes", [])
        if linked_note_id not in linked:
            linked.append(linked_note_id)
            index[note_id]["linked_notes"] = linked

        linked2 = index[linked_note_id].get("linked_notes", [])
        if note_id not in linked2:
            linked2.append(note_id)
            index[linked_note_id]["linked_notes"] = linked2

        self._save_index(index)
        return True

    def get_linked_notes(self, note_id: str) -> list[Note]:
        """Get notes linked to this note."""
        index = self._load_index()
        if note_id not in index:
            return []

        linked_ids = index[note_id].get("linked_notes", [])
        linked_notes = []
        for lid in linked_ids:
            if lid in index:
                linked_notes.append(Note(**index[lid]))
        return linked_notes


_kb: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
