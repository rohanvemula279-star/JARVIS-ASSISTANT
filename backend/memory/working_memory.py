"""
Redis Working Memory - Short-term conversation context
Falls back to in-memory if Redis unavailable
"""

import json
import logging
from typing import List, Dict, Any, Optional

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis-py not installed — Redis memory fallback to in-memory only.")

from backend.config.settings import get_settings

logger = logging.getLogger("memory.working")

class WorkingMemory:
    """Working memory store for active conversation context and scratchpad."""

    def __init__(self, ttl: int = 7200):
        settings = get_settings()
        self._redis_url = settings.redis_url
        self._redis = None
        self._connected = False
        self._ttl = ttl
        self._memory_store = {}
        self._scratchpad_store = {}

    async def _get_redis(self):
        if not REDIS_AVAILABLE:
            return None
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)
                await self._redis.ping()
                self._connected = True
                logger.info("Connected to Redis for working memory.")
            except Exception as e:
                logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
                self._connected = False
                self._redis = None
        return self._redis

    async def push_turn(self, session_id: str, role: str, content: str) -> None:
        redis = await self._get_redis()
        turn = json.dumps({"role": role, "content": content})
        if redis:
            try:
                key = f"session:{session_id}:history"
                await redis.rpush(key, turn)
                await redis.expire(key, self._ttl)
                await redis.ltrim(key, -20, -1)
                return
            except Exception as e:
                logger.error(f"Redis push_turn error: {e}")

        # Fallback
        if session_id not in self._memory_store:
            self._memory_store[session_id] = []
        self._memory_store[session_id].append(turn)
        if len(self._memory_store[session_id]) > 20:
            self._memory_store[session_id] = self._memory_store[session_id][-20:]

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:history"
                raw = await redis.lrange(key, 0, -1)
                return [json.loads(r) for r in raw]
            except Exception as e:
                logger.error(f"Redis get_history error: {e}")

        # Fallback
        return [json.loads(r) for r in self._memory_store.get(session_id, [])]

    async def set_scratchpad(self, session_id: str, data: Dict[str, Any]) -> None:
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:scratchpad"
                await redis.setex(key, self._ttl, json.dumps(data))
                return
            except Exception as e:
                logger.error(f"Redis set_scratchpad error: {e}")

        # Fallback
        self._scratchpad_store[session_id] = data

    async def get_scratchpad(self, session_id: str) -> Dict[str, Any]:
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:scratchpad"
                raw = await redis.get(key)
                return json.loads(raw) if raw else {}
            except Exception as e:
                logger.error(f"Redis get_scratchpad error: {e}")

        # Fallback
        return self._scratchpad_store.get(session_id, {})

    async def clear_session(self, session_id: str) -> None:
        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(f"session:{session_id}:history")
                await redis.delete(f"session:{session_id}:scratchpad")
            except Exception as e:
                logger.error(f"Redis clear_session error: {e}")
        self._memory_store.pop(session_id, None)
        self._scratchpad_store.pop(session_id, None)

    @property
    def is_available(self) -> bool:
        return self._connected
