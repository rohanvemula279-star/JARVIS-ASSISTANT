"""
MCP-Compatible Tool Registry
Defines tool schemas compatible with Gemini function calling (google-genai SDK).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("tools.registry")


@dataclass
class ToolParameter:
    """Definition of a single tool parameter."""
    name: str
    type: str  # "string" | "number" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """Full definition of a registered tool."""
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Callable[..., Coroutine]
    category: str  # "system" | "browser" | "search" | "file" | "vision"
    requires_confirmation: bool = False

    def to_gemini_schema(self) -> dict:
        """Convert to schema dict for Gemini function calling."""
        props = {}
        required = []
        for p in self.parameters:
            prop_def: Dict[str, Any] = {
                "type": p.type.upper(),
                "description": p.description,
            }
            if p.type.lower() == "array":
                prop_def["items"] = {"type": "STRING"}
            if p.enum:
                prop_def["enum"] = p.enum
            props[p.name] = prop_def
            if p.required:
                required.append(p.name)

        schema: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
        }

        if props:
            schema["parameters"] = {
                "type": "OBJECT",
                "properties": props,
            }
            if required:
                schema["parameters"]["required"] = required

        return schema


class ToolRegistry:
    """Central registry for all JARVIS tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> "ToolRegistry":
        """Register a tool definition. Returns self for chaining."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} [{tool.category}]")
        return self

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    def get_schemas(self, category: Optional[str] = None, categories: Optional[List[str]] = None) -> List[dict]:
        """Get Gemini function-calling schemas for all (or filtered) tools."""
        tools = list(self._tools.values())
        if categories:
            tools = [t for t in tools if t.category in categories]
        elif category:
            tools = [t for t in tools if t.category == category]
        return [t.to_gemini_schema() for t in tools]

    def get_gemini_tools(self, categories: Optional[List[str]] = None):
        """Get tool declarations formatted for Gemini's tools= parameter (new SDK)."""
        from google.genai.types import FunctionDeclaration, Tool

        declarations = []
        for tool in self._tools.values():
            if categories and tool.category not in categories:
                continue
            schema = tool.to_gemini_schema()
            params = schema.pop("parameters", None)
            fd = FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=params,
            )
            declarations.append(fd)

        if not declarations:
            return None

        return [Tool(function_declarations=declarations)]

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """List all registered tools as simple dicts."""
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [
            {"name": t.name, "description": t.description, "category": t.category}
            for t in tools
        ]

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with the given input."""
        if tool_name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        tool = self._tools[tool_name]

        if tool.requires_confirmation:
            logger.warning(f"Tool {tool_name} requires confirmation (auto-approved for now)")

        try:
            result = await tool.handler(**tool_input)
            return {"success": True, "result": result}
        except TypeError as e:
            return {"success": False, "error": f"Invalid arguments for {tool_name}: {e}"}
        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            return {"success": False, "error": str(e), "tool": tool_name}


# Global registry instance
registry = ToolRegistry()
