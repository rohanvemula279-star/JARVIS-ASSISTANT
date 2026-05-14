"""
JARVIS Daemon Adapter
Integrates with vierisid/jarvis Bun daemon when available

Reference: https://github.com/vierisid/jarvis
Requires: Bun runtime installed, daemon running on port 3142
"""

import os
import logging
from typing import Optional, Dict
import httpx

from .base import BaseAdapter

logger = logging.getLogger("adapters.jarvis")

class JarvisAdapter(BaseAdapter):
    """Adapter for vierisid/jarvis daemon"""

    name = "jarvis"
    description = "vierisid/jarvis - Always-on autonomous AI daemon with desktop awareness"
    version = "1.0.0"

    def __init__(self, url: str = None):
        self.url = url or os.environ.get("JARVIS_URL", "http://127.0.0.1:3142")
        self.timeout = 5.0
        self._available = None  # Cache availability check

    async def is_available(self) -> bool:
        """Check if JARVIS daemon is running"""
        if self._available is not None:
            return self._available

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.url}/health")
                self._available = response.status_code == 200
        except Exception as e:
            logger.debug(f"JARVIS not available: {e}")
            self._available = False

        return self._available

    async def proxy(self, prompt: str) -> Optional[Dict]:
        """Send request to JARVIS daemon"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try common JARVIS API endpoints
                endpoints = [
                    f"{self.url}/api/chat",
                    f"{self.url}/api/message",
                    f"{self.url}/chat",
                ]

                for endpoint in endpoints:
                    try:
                        response = await client.post(
                            endpoint,
                            json={"message": prompt, "type": "text"}
                        )
                        if response.status_code == 200:
                            result = response.json()
                            return {
                                "source": "jarvis-daemon",
                                "answer": result.get("answer", result.get("response", "Processed")),
                                "daemon": "vierisid/jarvis"
                            }
                    except Exception:
                        continue

                logger.warning("JARVIS endpoints not responding")
                return None

        except Exception as e:
            logger.error(f"JARVIS proxy error: {e}")
            return None

    async def health_check(self) -> Dict:
        """Return JARVIS adapter health status"""
        available = await self.is_available()
        return {
            "adapter": self.name,
            "available": available,
            "url": self.url,
            "type": "bun-daemon",
            "features": ["wake-word", "voice", "multi-agent", "desktop-awareness"] if available else []
        }

    async def get_capabilities(self) -> Dict:
        """Return JARVIS capabilities when available"""
        if not await self.is_available():
            return {"available": False}

        return {
            "available": True,
            "capabilities": [
                "ultra-low-latency-responses",
                "wake-word-detection",
                "voice-synthesis",
                "desktop-awareness",
                "multi-agent-orchestration",
                "workflow-automation"
            ]
        }