"""
System Tools - App launch, file operations, system info.
Registered into the global tool registry.
"""

import asyncio
import logging
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from backend.tools.registry import registry, ToolDefinition, ToolParameter

logger = logging.getLogger("tools.system")

# ============================================================
# Allowlist of permitted executables for safe app launching
# ============================================================
ALLOWED_EXECUTABLES: Dict[str, List[str]] = {
    "chrome": ["chrome", "google-chrome", "chromium", "msedge"],
    "google chrome": ["chrome", "google-chrome"],
    "edge": ["msedge"],
    "firefox": ["firefox"],
    "vscode": ["code"],
    "code": ["code"],
    "notepad": ["notepad.exe"],
    "notepad++": ["notepad++"],
    "discord": ["Discord"],
    "spotify": ["Spotify"],
    "telegram": ["Telegram"],
    "slack": ["Slack"],
    "explorer": ["explorer"],
    "file explorer": ["explorer"],
    "terminal": ["wt", "cmd", "powershell"],
    "powershell": ["powershell"],
    "cmd": ["cmd"],
    "calculator": ["calc"],
    "paint": ["mspaint"],
    "snipping tool": ["SnippingTool"],
    "task manager": ["taskmgr"],
    "settings": ["ms-settings:"],
}

# Web shortcuts
WEB_SHORTCUTS: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "twitter": "https://twitter.com",
    "reddit": "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com",
}


# ============================================================
# Tool handler implementations
# ============================================================

async def launch_application_handler(
    app_name: str,
    args: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Launch applications safely without shell injection risk."""
    normalized = app_name.lower().strip()
    extra_args = args or []

    # Check web shortcuts first
    if normalized in WEB_SHORTCUTS:
        import webbrowser
        url = WEB_SHORTCUTS[normalized]
        webbrowser.open(url)
        return {"launched": True, "type": "web", "url": url, "message": f"Opening {app_name}, sir."}

    if normalized not in ALLOWED_EXECUTABLES:
        return {
            "launched": False,
            "error": f"Application '{app_name}' is not in the approved launch list. "
                     f"Available: {', '.join(sorted(ALLOWED_EXECUTABLES.keys()))}"
        }

    executables = ALLOWED_EXECUTABLES[normalized]
    system = platform.system()

    for exe in executables:
        try:
            kwargs: Dict[str, Any] = {
                "shell": False,  # NEVER shell=True
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if system == "Windows" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen([exe] + extra_args, **kwargs)
            return {
                "launched": True,
                "type": "desktop",
                "app": exe,
                "pid": proc.pid,
                "message": f"Opening {app_name}, sir."
            }
        except FileNotFoundError:
            continue
        except OSError as e:
            logger.warning(f"Failed to launch {exe}: {e}")
            continue

    return {"launched": False, "error": f"Could not find executable for '{app_name}'"}


async def get_system_info_handler() -> Dict[str, Any]:
    """Get current system resource usage."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu = psutil.cpu_percent(interval=0.5)

    return {
        "cpu_percent": cpu,
        "memory_used_gb": round(mem.used / (1024**3), 1),
        "memory_total_gb": round(mem.total / (1024**3), 1),
        "memory_percent": mem.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_percent": round(disk.percent, 1),
        "running_processes": len(psutil.pids()),
        "platform": platform.system(),
        "python_version": platform.python_version(),
    }


async def read_file_handler(path: str) -> Dict[str, Any]:
    """Read the contents of a file from the filesystem."""
    try:
        p = Path(path).expanduser().resolve()
    except (ValueError, OSError) as e:
        return {"error": f"Invalid path: {e}"}

    if not p.exists():
        return {"error": f"File not found: {path}"}
    if not p.is_file():
        return {"error": f"Path is not a file: {path}"}
    if p.stat().st_size > 1_000_000:  # 1MB limit
        return {"error": f"File too large ({p.stat().st_size:,} bytes). Limit is 1MB."}

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "content": content,
        }
    except PermissionError:
        return {"error": f"Permission denied: {path}"}


async def list_directory_handler(path: str) -> Dict[str, Any]:
    """List the contents of a directory."""
    try:
        p = Path(path).expanduser().resolve()
    except (ValueError, OSError) as e:
        return {"error": f"Invalid path: {e}"}

    if not p.exists():
        return {"error": f"Directory not found: {path}"}
    if not p.is_dir():
        return {"error": f"Path is not a directory: {path}"}

    entries = []
    try:
        for item in sorted(p.iterdir()):
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_file():
                try:
                    entry["size_bytes"] = item.stat().st_size
                except OSError:
                    pass
            entries.append(entry)
    except PermissionError:
        return {"error": f"Permission denied: {path}"}

    return {"path": str(p), "count": len(entries), "entries": entries[:100]}  # Limit to 100


# ============================================================
# Register all system tools
# ============================================================

registry.register(ToolDefinition(
    name="launch_application",
    description="Launch or open a desktop application or website by name. Examples: 'chrome', 'vscode', 'notepad', 'youtube', 'github'",
    parameters=[
        ToolParameter("app_name", "string", "Name of the application or website to launch"),
        ToolParameter("args", "array", "Optional command line arguments", required=False),
    ],
    handler=launch_application_handler,
    category="system",
))

registry.register(ToolDefinition(
    name="get_system_info",
    description="Get current system resource usage including CPU, memory, disk, and process count",
    parameters=[],
    handler=get_system_info_handler,
    category="system",
))

registry.register(ToolDefinition(
    name="read_file",
    description="Read the text contents of a file from the filesystem. Maximum 1MB.",
    parameters=[
        ToolParameter("path", "string", "Absolute or ~ relative path to the file"),
    ],
    handler=read_file_handler,
    category="file",
))

registry.register(ToolDefinition(
    name="list_directory",
    description="List files and subdirectories in a directory",
    parameters=[
        ToolParameter("path", "string", "Absolute or ~ relative path to the directory"),
    ],
    handler=list_directory_handler,
    category="file",
))
