"""
Vector Memory Store — ChromaDB-backed long-term semantic memory.
Includes in-memory keyword-based fallback if ChromaDB is unavailable.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory.chroma")

try:
    import chromadb  # type: ignore[import-not-found]
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction  # type: ignore[import-not-found]
    CHROMA_AVAILABLE = True
except Exception as e:
    CHROMA_AVAILABLE = False
    logger.warning(f"ChromaDB unavailable ({type(e).__name__}: {e}), using keyword fallback")


class VectorMemory:
    """Long-term semantic memory storage with ChromaDB and keyword fallback."""

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        self._client = None
        self._collection = None
        self._persist_dir = persist_dir
        self._initialized = False
        self._fallback_store = []

        if CHROMA_AVAILABLE:
            try:
                self._client = chromadb.PersistentClient(path=persist_dir)
                self._embedding_fn = SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                self._collection = self._client.get_or_create_collection(
                    name="jarvis_memory",
                    embedding_function=self._embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
                self._initialized = True
                self._use_fallback = False
                logger.info(f"ChromaDB vector memory initialized. {self._collection.count()} entries.")
            except Exception as e:
                logger.warning(f"ChromaDB unavailable ({type(e).__name__}: {e}), using keyword fallback")
                self._initialized = False
                self._use_fallback = True
        else:
            logger.info("ChromaDB not available, using keyword fallback.")
            self._use_fallback = True

    async def save(self, interaction: Dict[str, Any]) -> str:
        """Save an interaction to long-term memory."""
        user_msg = interaction.get("user", "")
        assistant_msg = interaction.get("assistant", "")
        intent = interaction.get("intent", "conversation")
        content = f"User: {user_msg}\nJARVIS: {assistant_msg}"
        doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        if self._initialized:
            try:
                self._collection.upsert(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[{
                        "timestamp": datetime.utcnow().isoformat(),
                        "intent": intent,
                        "importance": str(self._score_importance(interaction)),
                        "user_message": user_msg[:200]
                    }]
                )
                return doc_id
            except Exception as e:
                logger.error(f"ChromaDB save error, using fallback: {e}")

        # Fallback save
        self._fallback_store.append({
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "intent": intent,
            "importance": self._score_importance(interaction),
            "user_message": user_msg[:200]
        })
        if len(self._fallback_store) > 100:
            self._fallback_store = self._fallback_store[-100:]
        return "fallback"

    async def recall(self, query: str, top_k: int = 5, intent_filter: str = None) -> List[Dict[str, Any]]:
        """Semantic recall with keyword-matching fallback."""
        if self._initialized:
            try:
                where_filter = {"intent": {"$eq": intent_filter}} if intent_filter else None
                results = self._collection.query(
                    query_texts=[query],
                    n_results=min(top_k, self._collection.count()) if self._collection.count() > 0 else 0,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
                memories = []
                if results["documents"] and results["documents"][0]:
                    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                        relevance = 1 - dist
                        if relevance > 0.4:
                            memories.append({
                                "content": doc,
                                "relevance": round(relevance, 3),
                                "timestamp": meta.get("timestamp", ""),
                                "intent": meta.get("intent", "")
                            })
                    return sorted(memories, key=lambda x: x["relevance"], reverse=True)
            except Exception as e:
                logger.error(f"ChromaDB recall error, using fallback: {e}")

        # Fallback: simple keyword matching
        query_lower = query.lower()
        query_words = set(query_lower.split()[:5])
        results = []
        for entry in reversed(self._fallback_store):
            content_lower = entry.get("content", "").lower()
            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                relevance = min(overlap / max(len(query_words), 1), 0.8)
                results.append({
                    "content": entry["content"],
                    "relevance": relevance,
                    "timestamp": entry["timestamp"],
                    "intent": entry["intent"]
                })
                if len(results) >= top_k:
                    break
        return sorted(results, key=lambda x: x["relevance"], reverse=True)

    def _score_importance(self, interaction: Dict[str, Any]) -> float:
        """Heuristic importance scoring."""
        score = 0.5
        user_msg = interaction.get("user", "")
        if len(user_msg) > 100:
            score += 0.1
        if interaction.get("intent") not in ("conversation",):
            score += 0.2
        correction_signals = ["no", "wrong", "actually", "i meant", "correct that"]
        if any(s in user_msg.lower() for s in correction_signals):
            score += 0.3
        return min(score, 1.0)

    @property
    def count(self) -> int:
        if self._initialized:
            return self._collection.count()
        return len(self._fallback_store)

    @property
    def is_available(self) -> bool:
        return self._initialized
