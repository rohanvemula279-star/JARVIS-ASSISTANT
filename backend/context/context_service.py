"""
Live Context Service — Background polling for system + weather context.
Caches results for fast access by the orchestrator.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from backend.context.system_context import SystemContextProvider
from backend.context.weather_context import WeatherContextProvider

logger = logging.getLogger("context.service")


class LiveContextService:
    """Background service that periodically refreshes system and weather context."""

    def __init__(self):
        self.system = SystemContextProvider()
        self.weather = WeatherContextProvider()
        self._cache: Dict[str, Any] = {}
        self._running = False
        self._tasks: list = []

    async def start(self) -> None:
        """Start background polling tasks."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._poll_system()),
            asyncio.create_task(self._poll_weather()),
        ]
        logger.info("LiveContextService started")

    async def stop(self) -> None:
        """Stop all background polling."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("LiveContextService stopped")

    async def _poll_system(self) -> None:
        """Refresh system context every 5 seconds."""
        while self._running:
            try:
                self._cache["system"] = await self.system.get_full_context()
            except Exception as e:
                logger.debug(f"System context poll error: {e}")
            await asyncio.sleep(5)

    async def _poll_weather(self) -> None:
        """Refresh weather every 30 minutes."""
        while self._running:
            try:
                self._cache["weather"] = await self.weather.get_weather()
            except Exception as e:
                logger.debug(f"Weather poll error: {e}")
            await asyncio.sleep(1800)  # 30 minutes

    def get_current(self) -> Dict[str, Any]:
        """Get the latest cached context (fast, non-blocking)."""
        return self._cache.copy()

    async def get_fresh(self) -> Dict[str, Any]:
        """Force-refresh all context (slower, for on-demand use)."""
        self._cache["system"] = await self.system.get_full_context()
        self._cache["weather"] = await self.weather.get_weather()
        return self._cache.copy()
