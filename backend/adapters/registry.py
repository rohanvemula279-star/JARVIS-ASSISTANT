"""
Adapter Registry
Manages all external daemon adapters
"""

import logging
from typing import Dict, Optional

from .base import BaseAdapter
from .jarvis import JarvisAdapter

logger = logging.getLogger("adapters")

class AdapterRegistry:
    """Registry for external daemon adapters"""

    def __init__(self):
        self.adapters: Dict[str, BaseAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self):
        """Register built-in adapters"""
        # JARVIS daemon adapter
        self.register("jarvis", JarvisAdapter())
        logger.info("Registered default adapters: jarvis")

    def register(self, name: str, adapter: BaseAdapter):
        """Register an adapter"""
        self.adapters[name] = adapter
        logger.info(f"Registered adapter: {name}")

    async def is_available(self, name: str) -> bool:
        """Check if adapter is available"""
        if name not in self.adapters:
            return False
        return await self.adapters[name].is_available()

    async def proxy(self, name: str, prompt: str) -> Optional[Dict]:
        """Proxy request through named adapter"""
        if name not in self.adapters:
            logger.warning(f"Unknown adapter: {name}")
            return None
        return await self.adapters[name].proxy(prompt)

    async def health_check_all(self) -> Dict:
        """Get health status of all adapters"""
        results = {}
        for name, adapter in self.adapters.items():
            try:
                results[name] = await adapter.health_check()
            except Exception as e:
                results[name] = {"adapter": name, "available": False, "error": str(e)}
        return results

    def get_all(self) -> Dict[str, BaseAdapter]:
        """Get all registered adapters"""
        return self.adapters

# Global registry instance
_registry = None

def get_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry