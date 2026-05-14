"""
System Context Provider — Real-time system state via psutil.
Replaces hardcoded "Clear" / "Local" context values.
"""

import logging
import platform
from datetime import datetime
from typing import Any, Dict

import psutil

logger = logging.getLogger("context.system")


class SystemContextProvider:
    """Provides real-time system state information."""

    async def get_active_window(self) -> Dict[str, str]:
        """Get the currently focused application window title."""
        system = platform.system()

        if system == "Windows":
            try:
                import win32gui  # type: ignore[import]
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                return {"title": title or "Desktop", "platform": "windows"}
            except ImportError:
                logger.debug("pywin32 not installed — active window detection unavailable")
                return {"title": "Unknown (pywin32 not installed)", "platform": "windows"}
            except Exception as e:
                return {"title": f"Error: {e}", "platform": "windows"}

        elif system == "Linux":
            try:
                import subprocess
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=2,
                    shell=False  # SAFE: no user input in command
                )
                return {"title": result.stdout.strip() or "Unknown", "platform": "linux"}
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return {"title": "Unknown (xdotool not found)", "platform": "linux"}

        elif system == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2,
                    shell=False
                )
                return {"title": result.stdout.strip() or "Unknown", "platform": "macos"}
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return {"title": "Unknown", "platform": "macos"}

        return {"title": "Unknown", "platform": system.lower()}

    async def get_full_context(self) -> Dict[str, Any]:
        """Get complete system context snapshot."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_used_gb": round(mem.used / (1024**3), 1),
                "memory_total_gb": round(mem.total / (1024**3), 1),
                "memory_percent": mem.percent,
                "disk_percent": round(disk.percent, 1),
                "platform": platform.system(),
                "hostname": platform.node(),
            },
            "active_window": await self.get_active_window(),
            "processes": len(psutil.pids()),
        }
