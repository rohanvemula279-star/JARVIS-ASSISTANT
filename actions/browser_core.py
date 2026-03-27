import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

class BrowserEngine:
    """
    Singleton browser engine. One browser, one context, multiple tabs.
    Visible on screen. Persistent across all commands.
    """
    
    _instance = None
    
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.pages: dict = {}          # tab_id -> Page
        self.active_tab_id: str = None
        self.action_log: list = []     # every action recorded
        self.sessions: dict = {}       # named sessions for restore
    
    @classmethod
    async def get_instance(cls) -> 'BrowserEngine':
        """Get or create the singleton browser instance."""
        if cls._instance is None or cls._instance.browser is None:
            cls._instance = cls()
            await cls._instance._launch()
        return cls._instance
    
    async def _launch(self):
        """Launch visible Chromium browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,           # VISIBLE on your screen
            args=['--start-maximized']
        )
        self.context = await self.browser.new_context(
            viewport=None,            # use full screen
            no_viewport=True
        )
        # Create first tab
        page = await self.context.new_page()
        tab_id = "tab_0"
        self.pages[tab_id] = page
        self.active_tab_id = tab_id
    
    def get_active_page(self) -> Page:
        """Return the currently active tab's Page object."""
        return self.pages.get(self.active_tab_id)
    
    def log_action(self, action: str, params: dict, result: str):
        """Log every action for transparency."""
        self.action_log.append({
            "action": action,
            "params": params,
            "result": result
        })
    
    async def shutdown(self):
        """Close everything."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        BrowserEngine._instance = None
