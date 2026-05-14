"""
Base Adapter Interface
External daemon adapters should implement this interface
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseAdapter(ABC):
    """Base class for external daemon adapters"""

    name: str = "base"
    description: str = ""
    version: str = "1.0.0"

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the external daemon is running and reachable"""
        pass

    @abstractmethod
    async def proxy(self, prompt: str) -> Optional[Dict]:
        """Proxy a request to the external daemon"""
        pass

    @abstractmethod
    async def health_check(self) -> Dict:
        """Return health status of the adapter"""
        pass

    def get_info(self) -> Dict:
        """Return adapter metadata"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "available": asyncio.get_event_loop().run_until_complete(self.is_available())
        }