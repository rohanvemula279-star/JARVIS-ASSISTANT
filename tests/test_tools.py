import pytest
from backend.tools.registry import ToolRegistry, ToolDefinition, ToolParameter

@pytest.mark.asyncio
async def test_tool_registration():
    registry = ToolRegistry()
    
    async def mock_handler(val: str):
        return {"val": val}
    
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters=[ToolParameter(name="val", type="string", description="A value")],
        handler=mock_handler,
        category="test"
    )
    
    registry.register(tool)
    assert "test_tool" in registry.list_tools()
    
    result = await registry.execute("test_tool", {"val": "hello"})
    assert result["success"] is True
    assert result["result"]["val"] == "hello"

@pytest.mark.asyncio
async def test_invalid_tool():
    registry = ToolRegistry()
    result = await registry.execute("non_existent", {})
    assert result["success"] is False
    assert "Unknown tool" in result["error"]
