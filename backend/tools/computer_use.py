import base64
import io
import json
try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except Exception:
    MSS_AVAILABLE = False
from google import genai
from google.genai.types import GenerateContentConfig
from backend.tools.registry import registry, ToolDefinition, ToolParameter

class ScreenPerception:
    def __init__(self):
        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def _capture_primary_monitor(self):
        if not MSS_AVAILABLE:
            return b"mock_image_data", None
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            screenshot = sct.grab(monitor)
            img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
        return img_bytes, monitor

    async def capture_and_analyze(self, question: str) -> dict:
        """Take screenshot, send to Gemini Vision, return structured analysis."""
        img_bytes, _ = await self._capture_primary_monitor()
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[question, {"mime_type": "image/png", "data": img_bytes}],
            config=GenerateContentConfig(response_mime_type="application/json")
        )
        
        try:
            return json.loads(response.text)
        except:
            return {"description": response.text, "ui_elements": [], "answer_to_question": "", "confidence": 0.0}

    async def find_element(self, description: str) -> dict:
        """Find a UI element by natural language description."""
        img_bytes, monitor = await self._capture_primary_monitor()
        prompt = f"Find the element matching: {description}. Return JSON with 'found' (boolean), 'x' (integer, center x coordinate relative to image), 'y' (integer, center y coordinate relative to image) and 'confidence' (float 0-1)."
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[prompt, {"mime_type": "image/png", "data": img_bytes}],
            config=GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            result = json.loads(response.text)
            return result
        except:
            return {"found": False, "x": 0, "y": 0, "confidence": 0.0}

    async def verify_action(self, expected_state: str) -> dict:
        """After performing an action, verify the screen matches expected state."""
        img_bytes, _ = await self._capture_primary_monitor()
        prompt = f"Does the screen show: {expected_state}? Return JSON with 'matches' (boolean), 'actual_state' (string description), and 'difference' (string description if it doesn't match)."
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[prompt, {"mime_type": "image/png", "data": img_bytes}],
            config=GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            return json.loads(response.text)
        except:
            return {"matches": False, "actual_state": response.text, "difference": "Unknown format"}

screen_perception = ScreenPerception()

registry.register(ToolDefinition(
    name="capture_screen",
    description="Take a screenshot and ask a question about its contents.",
    parameters=[ToolParameter(name="question", type="string", description="Question to ask about the screen")],
    handler=screen_perception.capture_and_analyze,
    category="vision"
))

registry.register(ToolDefinition(
    name="verify_screen_state",
    description="Verify if the screen matches a specific state description.",
    parameters=[ToolParameter(name="expected_state", type="string", description="The expected visual state of the screen")],
    handler=screen_perception.verify_action,
    category="vision"
))