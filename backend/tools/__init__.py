# Tools package — lazy imports with graceful fallback
# Each module self-registers its tools on import; missing deps are non-fatal.

import logging

logger = logging.getLogger("tools")

_TOOL_MODULES = [
    "backend.tools.system_tools",
    "backend.tools.search_tools",
    "backend.tools.computer_use",
    "backend.tools.input_controller",
    "backend.tools.code_tools",
    "backend.tools.browser_tools",
    "backend.tools.vision_tools",
]

for _mod in _TOOL_MODULES:
    try:
        __import__(_mod)
    except Exception as e:
        logger.warning(f"Could not load {_mod}: {type(e).__name__}: {e}")
