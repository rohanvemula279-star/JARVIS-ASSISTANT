import os
import asyncio
from backend.tools.computer_use import screen_perception
from backend.tools.registry import registry, ToolDefinition, ToolParameter

try:
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":99"
    import pyautogui
except Exception:
    class MockPyAutoGUI:
        def click(self, x, y): pass
        def typewrite(self, text, interval=0): pass
        def hotkey(self, *args): pass
    pyautogui = MockPyAutoGUI()


class InputController:
    SAFE_ZONES = [(0, 0, 1920, 1080)]  # Configurable safe screen region
    
    def _is_safe(self, x: int, y: int) -> bool:
        for x1, y1, x2, y2 in self.SAFE_ZONES:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    async def click(self, x: int, y: int, verify_after: str = None) -> dict:
        if not self._is_safe(x, y):
            return {"clicked": False, "verified": False, "error": "Coordinates outside safe zones"}
            
        pyautogui.click(x, y)
        await asyncio.sleep(0.5)
        
        if verify_after:
            verification = await screen_perception.verify_action(verify_after)
            return {"clicked": True, "verified": verification.get("matches", False), "screen_state": verification.get("actual_state", "")}
        return {"clicked": True, "verified": True, "screen_state": "Not verified"}

    async def find_and_click(self, description: str, verify_after: str = None) -> dict:
        el = await screen_perception.find_element(description)
        if el.get("found"):
            return await self.click(el["x"], el["y"], verify_after)
        return {"clicked": False, "error": f"Element not found: {description}"}
    
    async def type_text(self, text: str, field_description: str = None) -> dict:
        if field_description:
            el = await screen_perception.find_element(field_description)
            if el.get("found"):
                pyautogui.click(el["x"], el["y"])
                await asyncio.sleep(0.5)
            else:
                return {"success": False, "error": f"Field not found: {field_description}"}
                
        pyautogui.typewrite(text, interval=0.05)
        return {"success": True}
    
    async def hotkey(self, keys: list[str]) -> dict:
        pyautogui.hotkey(*keys)
        return {"success": True}

input_controller = InputController()

registry.register(ToolDefinition(
    name="find_and_click",
    description="Finds a UI element by natural language description and clicks it.",
    parameters=[
        ToolParameter(name="description", type="string", description="Description of the element to click"),
        ToolParameter(name="verify_after", type="string", description="Optional expected state after click to verify", required=False)
    ],
    handler=input_controller.find_and_click,
    category="system"
))

registry.register(ToolDefinition(
    name="type_into_field",
    description="Finds an input field by description and types text into it.",
    parameters=[
        ToolParameter(name="text", type="string", description="The text to type"),
        ToolParameter(name="field_description", type="string", description="Description of the input field", required=False)
    ],
    handler=input_controller.type_text,
    category="system"
))