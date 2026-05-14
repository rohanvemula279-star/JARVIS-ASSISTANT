import asyncio
import logging
from .registry import registry, ToolDefinition, ToolParameter

logger = logging.getLogger("tools.browser")

try:
    from playwright.async_api import async_playwright, Page, Browser  # type: ignore[import-not-found]
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None  # type stubs
    Browser = None
    logger.warning("Playwright not installed — browser tools disabled")

class BrowserEngine:
    """Persistent browser instance for multi-step web automation."""
    
    def __init__(self):
        self._browser: Browser = None
        self._page: Page = None
        self._playwright = None
    
    async def initialize(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        if self._playwright: return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,  # Keep visible so user can see what agent does
            slow_mo=100  # Slight delay makes actions visible and debuggable
        )
        self._page = await self._browser.new_page()
    
    async def navigate(self, url: str) -> dict:
        await self.initialize()
        await self._page.goto(url, wait_until="domcontentloaded")
        title = await self._page.title()
        return {"url": self._page.url, "title": title}
    
    async def get_page_content(self) -> dict:
        """Extract readable content from current page for LLM processing."""
        await self.initialize()
        content = await self._page.evaluate("""() => {
            // Remove scripts, styles, nav, ads
            const remove = document.querySelectorAll('script,style,nav,header,footer,aside,[class*="ad-"]');
            remove.forEach(el => el.remove());
            return {
                title: document.title,
                url: window.location.href,
                text: document.body.innerText.slice(0, 8000), // Limit for LLM context
                links: Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 20)
                    .map(a => ({ text: a.innerText.trim(), href: a.href }))
            }
        }""")
        return content
    
    async def click_element(self, selector: str = None, text: str = None) -> dict:
        """Click by CSS selector or by visible text."""
        await self.initialize()
        if text:
            await self._page.get_by_text(text, exact=False).first.click()
        elif selector:
            await self._page.click(selector)
        await self._page.wait_for_load_state("networkidle", timeout=5000)
        return {"clicked": selector or text, "url": self._page.url}
    
    async def fill_form(self, selector: str, value: str) -> dict:
        """Type into an input field."""
        await self.initialize()
        await self._page.fill(selector, value)
        return {"filled": selector, "value": value[:50] + "..." if len(value) > 50 else value}
    
    async def search_web(self, query: str, engine: str = "duckduckgo") -> dict:
        """Perform a web search and return results."""
        await self.initialize()
        if engine == "duckduckgo":
            await self._page.goto(f"https://duckduckgo.com/?q={query}&ia=web")
        elif engine == "google":
            await self._page.goto(f"https://www.google.com/search?q={query}")
        
        content = await self.get_page_content()
        return content
    
    async def take_screenshot(self) -> bytes:
        await self.initialize()
        return await self._page.screenshot(full_page=False)

# Register browser tools
browser_engine = BrowserEngine()

registry.register(ToolDefinition(
    name="navigate_to_url",
    description="Open a URL in the browser",
    parameters=[ToolParameter(name="url", type="string", description="Full URL to navigate to")],
    handler=browser_engine.navigate,
    category="browser"
))

registry.register(ToolDefinition(
    name="search_web",
    description="Search the web for information",
    parameters=[
        ToolParameter(name="query", type="string", description="Search query"),
        ToolParameter(name="engine", type="string", description="Search engine to use (duckduckgo or google)", required=False, enum=["duckduckgo", "google"])
    ],
    handler=browser_engine.search_web,
    category="browser"
))

registry.register(ToolDefinition(
    name="read_page_content",
    description="Read the text content of the currently open webpage",
    parameters=[],
    handler=browser_engine.get_page_content,
    category="browser"
))

registry.register(ToolDefinition(
    name="click_element",
    description="Click an element on the webpage by selector or text",
    parameters=[
        ToolParameter(name="selector", type="string", description="CSS selector of the element", required=False),
        ToolParameter(name="text", type="string", description="Visible text of the element", required=False)
    ],
    handler=browser_engine.click_element,
    category="browser"
))

registry.register(ToolDefinition(
    name="fill_form",
    description="Type text into an input field on the webpage",
    parameters=[
        ToolParameter(name="selector", type="string", description="CSS selector of the input field"),
        ToolParameter(name="value", type="string", description="Text to type into the field")
    ],
    handler=browser_engine.fill_form,
    category="browser"
))
