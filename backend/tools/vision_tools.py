"""
Vision Tools — Gemini-powered image analysis.
Uses google.genai (production SDK), with PIL graceful fallback.
"""

import base64
import io
import logging
import os

from google import genai
from google.genai.types import GenerateContentConfig

logger = logging.getLogger("tools.vision")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed — vision size metadata unavailable")

from .registry import registry, ToolDefinition, ToolParameter


class VisionEngine:

    def __init__(self):
        from backend.config.settings import get_settings
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def analyze_image(self, image_base64: str, prompt: str = "Describe what you see in detail.") -> dict:
        """Send actual image data to Gemini Vision."""
        image_bytes = base64.b64decode(image_base64)

        size_str = "unknown"
        if PIL_AVAILABLE:
            image = Image.open(io.BytesIO(image_bytes))
            size_str = f"{image.width}x{image.height}"

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[prompt, {"mime_type": "image/png", "data": image_bytes}],
            config=GenerateContentConfig(temperature=0.3),
        )

        text = ""
        if response and response.candidates and response.candidates[0].content.parts:
            text = "".join(p.text for p in response.candidates[0].content.parts if p.text)

        return {
            "analysis": text or "No analysis generated.",
            "model": self.model,
            "image_size": size_str,
        }

    async def analyze_screen_region(self, region: dict = None) -> dict:
        """Take a screenshot and analyze it."""
        try:
            import mss
            import mss.tools
        except ImportError:
            return {"analysis": "mss not installed — cannot capture screen", "model": self.model, "image_size": "N/A"}

        with mss.mss() as sct:
            if region:
                monitor = region
            else:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            screenshot = sct.grab(monitor)
            img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

        img_b64 = base64.b64encode(img_bytes).decode()
        return await self.analyze_image(
            img_b64,
            "What is shown on this screen? Be specific about any text, windows, or UI elements visible.",
        )


vision_engine = VisionEngine()


def get_vision_engine():
    return vision_engine


if not os.getenv("DISABLE_VISION_TOOLS"):
    registry.register(ToolDefinition(
        name="analyze_screen",
        description="Take a screenshot of the user's current screen and analyze it to see what they are looking at.",
        parameters=[],
        handler=vision_engine.analyze_screen_region,
        category="vision",
    ))
